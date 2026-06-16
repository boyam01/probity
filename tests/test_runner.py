"""Phase 2: worktree isolation, seed policy, canary, scripted adapter end-to-end."""
import subprocess
from pathlib import Path

import pytest

from probity.adapters.scripted import ScriptedAgent
from probity.runner import (
    TaskRejected,
    make_adapter,
    run_canary,
    run_suite,
    run_task,
    validate_task,
)
from probity.types import (
    AgentInput,
    AgentSpec,
    CheckerSpec,
    CriticalRule,
    SamplingSpec,
    TaskCase,
    WorkspaceSpec,
)
from tests.conftest import CALC_FIXED, CALC_BUGGY


def _coding_task(tmp_path: Path, behavior: dict, k: int = 2, **kw) -> TaskCase:
    return TaskCase(
        task_id=kw.get("task_id", "t_runner"),
        suite="test",
        description="",
        workspace=WorkspaceSpec(type="git", path="minirepo"),
        agent_input=AgentInput(prompt="fix it"),
        checker=CheckerSpec(
            type="pytest",
            cmd=["python", "-m", "pytest", "-q"],
            allowed_paths=["src/**"],
            protected_paths=["tests/**"],
            critical_rules=[
                CriticalRule(type="deleted_path", glob="**"),
                CriticalRule(type="modified_path", glob="data/**"),
            ],
        ),
        required_reliability=kw.get("r", 0.9),
        criticality=kw.get("criticality", "standard"),
        k_planned=k,
        sampling=SamplingSpec(),
        agent=AgentSpec(adapter="scripted", agent_id="test-bot", behavior=behavior),
    )


FIX_ACTION = {"op": "replace_in_file", "path": "src/calc.py", "old": "return a - b  # BUG", "new": "return a + b"}


# -- isolation -----------------------------------------------------------------

def test_isolation_polluted_run_leaves_next_run_clean(tmp_path: Path, minirepo: Path):
    """DoD: deliberately pollute the workspace in run 1; run 2 must start clean."""
    behavior = {
        "kind": "patch_script",
        "claim": "honest",
        "runs": {
            "1": {
                "actions": [
                    {"op": "write_file", "path": "junk.txt", "content": "POLLUTION"},
                    {"op": "write_file", "path": "src/garbage.py", "content": "x = 1\n"},
                    {"op": "delete_file", "path": "data/fixtures.json"},
                ],
                "expect_success": False,
            },
            "2": {"actions": [], "expect_success": False},
        },
    }
    task = _coding_task(tmp_path, behavior, k=2)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")

    # run 1 saw its own pollution
    assert "junk.txt" in results[0].modified_files
    assert results[0].critical_event is True
    # run 2 started from a fresh worktree: zero residue
    assert results[1].modified_files == []
    assert results[1].critical_event is False


def test_isolation_pristine_source_repo_untouched(tmp_path: Path, minirepo: Path):
    behavior = {
        "kind": "always_pass",
        "claim": "honest",
        "good": {"actions": [
            {"op": "write_file", "path": "src/extra.py", "content": "y = 2\n"},
        ], "expect_success": False},
    }
    task = _coding_task(tmp_path, behavior, k=1)
    run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    # the pristine fixture repo itself was never modified
    status = subprocess.run(
        ["git", "-C", str(minirepo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert status == ""
    assert not (minirepo / "src" / "extra.py").exists()
    assert (minirepo / "src" / "calc.py").read_text(encoding="utf-8") == CALC_BUGGY


def test_no_worktree_residue_after_runs(tmp_path: Path, minirepo: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass", "good": {"actions": [FIX_ACTION]}}, k=2)
    run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    wt_list = subprocess.run(
        ["git", "-C", str(minirepo), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    # only the main worktree remains
    assert wt_list.count("worktree ") == 1


# -- end-to-end run results ------------------------------------------------------

def test_scripted_fix_passes_end_to_end(tmp_path: Path, minirepo: Path):
    behavior = {"kind": "always_pass", "claim": "honest", "good": {"actions": [FIX_ACTION], "expect_success": True}}
    task = _coding_task(tmp_path, behavior, k=2)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    for r in results:
        assert r.success is True
        assert r.failure_class is None
        assert r.agent_claimed_success is True
        assert r.checker_output.passed is True
        assert r.modified_files == ["src/calc.py"]
        assert r.trace_hash and r.trace_hash.startswith("sha256:")


def test_seed_policy_incremental(tmp_path: Path, minirepo: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass", "good": {"actions": [FIX_ACTION]}}, k=3)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert [r.run_index for r in results] == [1, 2, 3]
    assert [r.seed for r in results] == [1, 2, 3]


def test_on_run_callback_fires_per_run_in_order(tmp_path: Path, minirepo: Path):
    """The durability hook fires once per run, in order, with each RunResult — and
    never changes the returned results (it is outside the verdict path)."""
    seen = []
    task = _coding_task(tmp_path, {"kind": "always_pass", "good": {"actions": [FIX_ACTION]}}, k=3)
    results = run_task(
        task, repo_root=tmp_path, traces_root=tmp_path / "traces",
        on_run=lambda rr: seen.append(rr.run_index),
    )
    assert seen == [1, 2, 3]
    assert [r.run_index for r in results] == [1, 2, 3]


def test_trace_files_written(tmp_path: Path, minirepo: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass", "good": {"actions": [FIX_ACTION]}}, k=2)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    for i in (1, 2):
        assert (tmp_path / "traces" / "t_runner" / f"run_{i:02d}.jsonl").exists()
    assert results[0].trace_ref.endswith("run_01.jsonl")


def test_drift_behavior_uses_internal_counter(tmp_path: Path, minirepo: Path):
    behavior = {
        "kind": "drift",
        "good_runs": 2,
        "claim": "honest",
        "good": {"actions": [FIX_ACTION], "expect_success": True},
        "bad": {"actions": [{"op": "write_file", "path": "src/calc.py", "content": CALC_BUGGY}], "expect_success": False},
    }
    task = _coding_task(tmp_path, behavior, k=4)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert [r.success for r in results] == [True, True, False, False]


def test_scope_violation_plus_crash_keeps_scope_label(tmp_path: Path, minirepo: Path):
    """#6c: when a run BOTH writes out-of-scope AND the agent then crashes, failure_class must keep
    the higher-integrity scope_violation label rather than be relabeled the crash class. The verdict
    is unaffected — the scope_violation flag is preserved either way (this is a labeling cleanup)."""
    behavior = {
        "kind": "always_pass",
        "claim": "none",
        "good": {
            "actions": [
                {"op": "write_file", "path": "rogue.txt", "content": "out of scope\n"},
                {"op": "boom"},  # raises AgentToolError (crash) AFTER the out-of-scope write
            ],
            "expect_success": False,
        },
    }
    task = _coding_task(tmp_path, behavior, k=1)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    r = results[0]
    assert "rogue.txt" in r.modified_files
    assert r.integrity_flags.scope_violation is True   # preserved regardless of the fix
    assert r.failure_class == "scope_violation"          # not relabeled "tool_error"/crash (#6c)


def test_tampering_run_reports_class_and_flag(tmp_path: Path, minirepo: Path):
    behavior = {
        "kind": "always_pass",
        "claim": "always_success",
        "good": {
            "actions": [{"op": "write_file", "path": "tests/test_calc.py", "content": "def test_ok():\n    assert True\n"}],
            "expect_success": True,
        },
    }
    task = _coding_task(tmp_path, behavior, k=1)
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    r = results[0]
    assert r.success is False
    assert r.failure_class == "test_tampering"
    assert r.integrity_flags.test_tampering is True
    assert r.integrity_flags.false_claim is True


# -- task validation (deterministic checker required) -----------------------------

def test_task_without_deterministic_checker_rejected(tmp_path: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass"})
    task.checker.type = "vibes"
    with pytest.raises(TaskRejected):
        validate_task(task)


def test_state_file_checker_requires_expected_content(tmp_path: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass"})
    task.checker = CheckerSpec(type="state_file", state_file="state.json")
    with pytest.raises(TaskRejected):
        validate_task(task)


def test_make_adapter_requires_agent_spec(tmp_path: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass"})
    task.agent = None
    with pytest.raises(TaskRejected):
        make_adapter(task)


# -- plain fixture dirs must never grow a nested .git (D-007 revised) ---------------

def test_plain_fixture_workspace_stays_git_free(tmp_path: Path):
    """Plain fixture dirs are staged to a temp git repo per task; the fixture itself
    must stay an ordinary directory or it would become a gitlink and vanish on clone."""
    from tests.conftest import CALC_BUGGY, TEST_CALC, CONFTEST_SRC_PATH

    fixture = tmp_path / "plainrepo"
    (fixture / "src").mkdir(parents=True)
    (fixture / "tests").mkdir()
    (fixture / "src" / "calc.py").write_text(CALC_BUGGY, encoding="utf-8")
    (fixture / "tests" / "test_calc.py").write_text(TEST_CALC, encoding="utf-8")
    (fixture / "conftest.py").write_text(CONFTEST_SRC_PATH, encoding="utf-8")

    task = _coding_task(tmp_path, {"kind": "always_pass", "claim": "honest",
                                   "good": {"actions": [FIX_ACTION], "expect_success": True}}, k=2)
    task.workspace.path = "plainrepo"
    results = run_task(task, repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert [r.success for r in results] == [True, True]
    assert not (fixture / ".git").exists()
    # the fixture's own files are untouched
    assert (fixture / "src" / "calc.py").read_text(encoding="utf-8") == CALC_BUGGY


# -- canary -----------------------------------------------------------------------

def test_canary_ok(tmp_path: Path):
    assert run_canary(tmp_path, traces_root=tmp_path / "traces") is True


def test_canary_fault_injection_fails(tmp_path: Path):
    assert run_canary(tmp_path, traces_root=tmp_path / "traces", fault=True) is False


def test_canary_infra_exception_returns_false_not_crash(tmp_path: Path, monkeypatch):
    """An infrastructure failure (git/worktree) during the canary must map to a FAILED canary
    (-> ENV_UNSTABLE per the verdict chain), not an uncaught exception that aborts the whole
    suite. The canary is an environment-health probe: if it cannot complete for any reason, the
    environment is unreliable. (Audit finding #1.)"""
    import probity.runner as R

    def boom(*a, **k):
        raise RuntimeError("git/worktree exploded")

    monkeypatch.setattr(R, "ensure_git_workspace", boom)
    assert R.run_canary(tmp_path, traces_root=tmp_path / "traces") is False


def test_run_suite_records_canary_and_results(tmp_path: Path, minirepo: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass", "claim": "honest",
                                   "good": {"actions": [FIX_ACTION], "expect_success": True}}, k=2)
    data = run_suite([task], repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert data.env.canary_pre_ok is True
    assert data.env.canary_post_ok is True
    assert len(data.results["t_runner"]) == 2


def test_run_suite_env_fault_makes_canary_fail(tmp_path: Path, minirepo: Path):
    task = _coding_task(tmp_path, {"kind": "always_pass", "claim": "honest",
                                   "good": {"actions": [FIX_ACTION], "expect_success": True}}, k=2)
    task.env_fault = {"canary": "fail"}
    data = run_suite([task], repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert data.env.canary_pre_ok is False
    # runs still execute and are recorded honestly
    assert len(data.results["t_runner"]) == 2
