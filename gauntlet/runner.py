"""k-run executor: git-worktree isolation, incremental seed policy, pre/post canary.

v0.1 is strictly serial (reproducibility first — §4.3). Zero LLM anywhere.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from gauntlet.adapters.base import Adapter, AgentExecutionError, AgentRunOutcome
from gauntlet.adapters.scripted import ScriptedAgent
from gauntlet.adapters.subprocess import SubprocessAgent
from gauntlet.checker import check, parse_claim
from gauntlet.types import (
    CheckerOutput,
    CheckResult,
    CriticalEventRecord,
    EnvStatus,
    RunResult,
    TaskCase,
    TokenUsage,
    Trace,
)


class TaskRejected(Exception):
    """Tasks without a deterministic checker are rejected outright (§2.1)."""


def validate_task(task: TaskCase) -> None:
    spec = task.checker
    if spec.type == "pytest":
        if not spec.cmd:
            raise TaskRejected(f"{task.task_id}: pytest checker requires cmd")
    elif spec.type == "state_file":
        if spec.state_file is None or spec.expected_content is None:
            raise TaskRejected(f"{task.task_id}: state_file checker requires state_file + expected_content")
    elif spec.type == "script":
        if not spec.module:
            raise TaskRejected(f"{task.task_id}: script checker requires module")
    else:
        raise TaskRejected(
            f"{task.task_id}: no deterministic checker (type={spec.type!r}) — task rejected"
        )


def make_adapter(task: TaskCase) -> Adapter:
    if task.agent is None:
        raise TaskRejected(f"{task.task_id}: task json has no agent spec; cannot run")
    if task.agent.adapter == "scripted":
        return ScriptedAgent(task.agent.behavior, agent_id=task.agent.agent_id)
    if task.agent.adapter == "subprocess":
        return SubprocessAgent(task.agent.behavior, agent_id=task.agent.agent_id)
    raise TaskRejected(f"{task.task_id}: unknown adapter {task.agent.adapter!r}")


# ---------------------------------------------------------------------------
# git workspace / worktree isolation
# ---------------------------------------------------------------------------

def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
    )
    return proc


def _git_ok(cwd: Path, *args: str) -> None:
    proc = _git(cwd, *args)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")


_COMMIT_ARGS = (
    "-c", "user.name=gauntlet",
    "-c", "user.email=gauntlet@local",
    "-c", "commit.gpgsign=false",
)


def ensure_git_workspace(path: Path) -> None:
    """Turn a (temp) directory into a committed git repo with HEAD = pristine state."""
    if not path.is_dir():
        raise TaskRejected(f"workspace path does not exist: {path}")
    if not (path / ".git").exists():
        _git_ok(path, "init", "-q")
    if _git(path, "rev-parse", "--verify", "HEAD").returncode != 0:
        _git_ok(path, "add", "-A")
        _git_ok(path, *_COMMIT_ARGS, "commit", "-q", "--no-verify", "-m", "pristine")


class WorkspaceSource:
    """Resolve a task workspace to a git repo that worktrees can be spawned from.

    - Source dir already a git repo → use it in place; task pristine_ref applies.
    - Plain fixture dir (committed as ordinary files in the main repo) → copy to a
      temp staging area and git-init there. The fixture itself never grows a nested
      .git, which would turn it into a gitlink and vanish on clone (D-007 revised).
    """

    def __init__(self, src: Path, pristine_ref: str) -> None:
        if not src.is_dir():
            raise TaskRejected(f"workspace path does not exist: {src}")
        self.src = src
        self.pristine_ref = pristine_ref
        self._staging: str | None = None

    def __enter__(self) -> tuple[Path, str]:
        if (self.src / ".git").exists():
            return self.src, self.pristine_ref
        self._staging = tempfile.mkdtemp(prefix="gauntlet_stage_")
        dest = Path(self._staging) / "ws"
        shutil.copytree(self.src, dest, ignore=shutil.ignore_patterns(".git"))
        ensure_git_workspace(dest)
        return dest, "HEAD"

    def __exit__(self, *exc_info) -> None:
        if self._staging is not None:
            shutil.rmtree(self._staging, ignore_errors=True)


class Worktree:
    """One fresh worktree per run; destroyed afterwards. Zero residue between runs (§4.3)."""

    def __init__(self, source_repo: Path, pristine_ref: str) -> None:
        self.source_repo = source_repo
        self.pristine_ref = pristine_ref
        self._tmp_parent: str | None = None
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self._tmp_parent = tempfile.mkdtemp(prefix="gauntlet_wt_")
        self.path = Path(self._tmp_parent) / "wt"
        _git_ok(self.source_repo, "worktree", "add", "--detach", "-q", str(self.path), self.pristine_ref)
        return self.path

    def __exit__(self, *exc_info) -> None:
        if self.path is not None:
            proc = _git(self.source_repo, "worktree", "remove", "--force", str(self.path))
            if proc.returncode != 0:
                shutil.rmtree(self.path, ignore_errors=True)
                _git(self.source_repo, "worktree", "prune")
        if self._tmp_parent is not None:
            shutil.rmtree(self._tmp_parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# single run
# ---------------------------------------------------------------------------

def _seeds(task: TaskCase) -> list[int]:
    # v0.1 seed policy: "incremental" → seed = run_index (1-based)
    return list(range(1, task.k_planned + 1))


def run_one(
    task: TaskCase,
    adapter: Adapter,
    run_index: int,
    seed: int,
    source_repo: Path,
    pristine_ref: str,
    repo_root: Path,
    traces_root: Path,
) -> RunResult:
    with Worktree(source_repo, pristine_ref) as wt:
        agent_failure: str | None = None
        try:
            outcome = adapter.run(wt, task, seed)
        except AgentExecutionError as e:
            agent_failure = e.failure_class
            outcome = AgentRunOutcome(
                trace=Trace(events=[{"type": "agent_error", "detail": str(e)}], final_output="")
            )

        result: CheckResult = check(wt, outcome.trace, task)

    # primary failure_class: integrity tampering keeps priority; otherwise the
    # agent-side failure (timeout/crash/tool_error) is the primary cause.
    success = result.passed and agent_failure is None
    failure_class = result.failure_class
    # an integrity class (test_tampering / scope_violation) is the more security-relevant primary
    # cause and is kept even when the agent also crashed; otherwise the agent-side failure
    # (timeout/crash/tool_error) is the primary cause. The integrity *flags* are preserved either
    # way — this only sharpens the failure_class LABEL (#6c).
    if agent_failure is not None and failure_class not in ("test_tampering", "scope_violation"):
        failure_class = agent_failure
        success = False
    if success:
        failure_class = None

    trace_dir = traces_root / task.task_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"run_{run_index:02d}.jsonl"
    trace_file.write_text(outcome.trace.to_jsonl(), encoding="utf-8", newline="\n")
    try:
        trace_ref = trace_file.relative_to(repo_root).as_posix()
    except ValueError:
        trace_ref = str(trace_file)

    hits = [
        CriticalEventRecord(run_index=run_index, rule=h.rule, path=h.path)
        for h in result.critical_hits
    ]

    return RunResult(
        task_id=task.task_id,
        run_index=run_index,
        agent_id=adapter.agent_id,
        agent_config_hash=adapter.config_hash(),
        seed=seed,
        success=success,
        agent_claimed_success=parse_claim(outcome.trace),
        failure_class=failure_class,
        integrity_flags=result.integrity_flags,
        critical_event=result.critical_event,
        checker_output=CheckerOutput(passed=result.passed, detail=result.detail),
        modified_files=result.modified_files,
        steps=outcome.steps,
        tokens=outcome.tokens or TokenUsage(),
        cost_usd=outcome.cost_usd,
        latency_s=outcome.latency_s,
        trace_ref=trace_ref,
        trace_hash=outcome.trace.sha256(),
        critical_hits=hits,
    )


def run_task(
    task: TaskCase,
    repo_root: Path,
    traces_root: Path,
    adapter: Adapter | None = None,
    on_run=None,
) -> list[RunResult]:
    """Run the task k_planned times, serially, one fresh worktree per run.

    ``on_run`` (optional) is called with each ``RunResult`` immediately after that run
    completes — a durability hook for long batches that want per-run checkpointing
    (so a death mid-task does not lose the in-flight runs). It must not mutate the
    result and never participates in the verdict path; raising propagates.
    """
    validate_task(task)
    if adapter is None:
        adapter = make_adapter(task)
    workspace_src = (repo_root / task.workspace.path).resolve()
    results = []
    with WorkspaceSource(workspace_src, task.workspace.pristine_ref) as (source_repo, ref):
        for run_index, seed in enumerate(_seeds(task), start=1):
            rr = run_one(task, adapter, run_index, seed, source_repo, ref, repo_root, traces_root)
            results.append(rr)
            if on_run is not None:
                on_run(rr)
    return results


# ---------------------------------------------------------------------------
# canary (§4.3)
# ---------------------------------------------------------------------------

_CANARY_EXPECTED = "canary-ok"


def _canary_task(workspace_rel: str) -> TaskCase:
    from gauntlet.types import AgentInput, CheckerSpec, SamplingSpec, WorkspaceSpec

    return TaskCase(
        task_id="__canary__",
        suite="canary",
        description="environment canary: scripted always-correct agent on a fixed task",
        workspace=WorkspaceSpec(type="git", path=workspace_rel, pristine_ref="HEAD"),
        agent_input=AgentInput(prompt="write the canary state file"),
        checker=CheckerSpec(
            type="state_file",
            allowed_paths=["state.json"],
            state_file="state.json",
            expected_content=_CANARY_EXPECTED,
        ),
        required_reliability=0.99,
        criticality="standard",
        k_planned=1,
        sampling=SamplingSpec(),
    )


def run_canary(repo_root: Path, traces_root: Path, fault: bool = False) -> bool:
    """One run of the always-correct scripted agent on a fixed task. ``fault=True``
    swaps in a broken agent (calibration I1's injected environment fault) so the
    real canary code path executes and fails."""
    tmp = Path(tempfile.mkdtemp(prefix="gauntlet_canary_"))
    try:
        (tmp / "README.txt").write_text("canary workspace\n", encoding="utf-8")
        ensure_git_workspace(tmp)
        task = _canary_task(str(tmp))
        content = "canary-BROKEN" if fault else _CANARY_EXPECTED
        adapter = ScriptedAgent(
            {
                "kind": "always_pass",
                "claim": "honest",
                "good": {
                    "actions": [{"op": "write_file", "path": "state.json", "content": content}],
                    "expect_success": True,
                },
            },
            agent_id="canary-scripted-v1",
        )
        result = run_one(
            task, adapter, run_index=1, seed=1,
            source_repo=tmp, pristine_ref="HEAD",
            repo_root=Path("."), traces_root=traces_root,
        )
        return result.success
    except Exception:
        # The canary is an environment-health probe: any infrastructure failure (git/worktree/OS)
        # means the environment is unreliable → a FAILED canary → ENV_UNSTABLE (§3.1 rule 1, never
        # blame the agent), not an uncaught crash that aborts the whole suite (finding #1).
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# suite execution
# ---------------------------------------------------------------------------

@dataclass
class SuiteRunData:
    env: EnvStatus
    tasks: dict[str, TaskCase] = field(default_factory=dict)
    results: dict[str, list[RunResult]] = field(default_factory=dict)


def run_suite(tasks: list[TaskCase], repo_root: Path, traces_root: Path) -> SuiteRunData:
    """Serial suite execution with pre/post canary. A canary failure does NOT abort
    the runs — it is recorded and the verdict engine maps it to ENV_UNSTABLE (§3.1 rule 1)."""
    for task in tasks:
        validate_task(task)

    fault = any(
        (t.env_fault or {}).get("canary") == "fail" for t in tasks
    )
    data = SuiteRunData(env=EnvStatus())
    data.env.canary_pre_ok = run_canary(repo_root, traces_root, fault=fault)
    for task in tasks:
        data.tasks[task.task_id] = task
        data.results[task.task_id] = run_task(task, repo_root, traces_root)
    data.env.canary_post_ok = run_canary(repo_root, traces_root, fault=fault)
    return data
