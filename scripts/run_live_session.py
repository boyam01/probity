#!/usr/bin/env python3
"""Live audit session driver — mechanizes the LIVE_AUDIT_SPEC §3 session discipline.

Usage:
    python scripts/run_live_session.py --task tasks/live/task_live_openai.json \
        --out reports/live/<YYYY-MM-DD>-<model>

Provider (openai / anthropic) is derived from the task's agent command; per LIVE_AUDIT_SPEC
v0.2 §A4 each provider is an independent, separately-published session.

Enforced gates, in order:
  1. spec hash gate (SPEC_DRIFT refusal, as everywhere else)
  2. pre-registration: <out>/SESSION_MANIFEST.md must exist AND be committed (clean in git)
  3. live env present (provider key/model + prices) unless GAUNTLET_LIVE_DRYRUN=1
  4. run the suite serially (fresh worktree per run, pre/post scripted canary)
  5. transport-failure scan: any TRANSPORT_FAILURE in traces → the environment, not the
     agent, is at fault → env recorded as unstable → verdict rule 1 yields ENV_UNSTABLE
  6. budget gate: ledger total > GAUNTLET_LIVE_MAX_USD → DO NOT publish (log only, exit 4)
  7. secret scan over traces: any hit → DO NOT publish (exit 5)
  8. publish: audit_report.json + GAUNTLET_REPORT.md (stochastic disclaimer prepended)
     + scrubbed traces into <out>/traces/

The verdict path stays zero-LLM: this driver only feeds honest environment facts into the
frozen engine; it never edits a verdict.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from probity import HARNESS_VERSION  # noqa: E402
from probity.report import render_markdown  # noqa: E402
from probity.runner import run_suite  # noqa: E402
from probity.types import TaskCase  # noqa: E402
from probity.verdict import build_audit_report, decide, verify_spec  # noqa: E402

# §A4.5 wording is frozen: never "we audited GPT/Claude" — the wrapper is part of the
# measurement. §A4.3 paragraph is verbatim and template-generated (zero LLM).
def build_live_header(provider: str, model: str) -> str:
    if provider == "subagent":
        transport_line = (
            f"> **Subject under test:** a single-turn patch agent built on `{model}` "
            "(Claude Code **subagent transport**). The orchestrator obtained each patch from a "
            "subagent; the frozen checker → stats → verdict path then scored it deterministically "
            "(zero LLM). **This is NOT an API audit** — it does not exercise the model's hosted "
            "API and the subagent system envelope differs from a direct API call.\n>\n"
        )
    else:
        transport_line = (
            f"> **Subject under test:** a single-turn patch agent built on `{model}` "
            f"(provider: {provider}). The wrapper is part of what is being measured.\n>\n"
        )
    return (
        "> **Live audit disclaimer.** Live audits are stochastic and not bit-reproducible. "
        "The recorded traces and verdict below are from one pre-registered session; "
        "re-runs will differ.\n>\n"
        + transport_line
        + "> **Not a model comparison.** This report rules on one agent against its own "
        "pre-registered reliability claim. It is not a model comparison: k=10 on a single "
        "task cannot support cross-model ranking, and this harness deliberately refuses to "
        "produce one.\n\n"
    )


# Per-provider live env var names (must match agents/llm_patch_agent.py PROVIDER_CFG).
PROVIDER_VARS = {
    "openai": {"key": "OPENAI_API_KEY", "model": "OPENAI_MODEL"},
    "anthropic": {"key": "ANTHROPIC_API_KEY", "model": "ANTHROPIC_MODEL"},
}

# Catches OpenAI sk-/sk-proj-, Anthropic sk-ant-, the literal header/field words, AND
# high-entropy bearer-token shapes (Azure 32-hex, JWTs, long opaque gateway tokens).
SECRET_RE = re.compile(
    r"sk-ant-[A-Za-z0-9]"
    r"|sk-[A-Za-z0-9]"
    r"|api[_-]?key"
    r"|authorization"
    r"|x-api-key"
    r"|bearer\s+[A-Za-z0-9._\-]{16,}"
    r"|\b[A-Fa-f0-9]{32,}\b"
    r"|\beyJ[A-Za-z0-9._\-]{20,}",  # JWT
    re.IGNORECASE,
)


def task_provider_and_agent(task) -> tuple[str, str]:
    """Derive (provider, agent_script_rel) from the task's subprocess command, so the driver
    checks the ACTUAL agent file being run rather than a hardcoded path."""
    cmd = (task.agent.behavior or {}).get("cmd", []) if task.agent else []
    provider = "openai"
    agent_rel = "agents/llm_patch_agent.py"
    for i, a in enumerate(cmd):
        if a == "--provider" and i + 1 < len(cmd):
            provider = cmd[i + 1]
        if isinstance(a, str) and a.endswith(".py"):
            agent_rel = a.replace("{repo_root}/", "").replace("{repo_root}\\", "")
    return provider, agent_rel


def fail(msg: str, code: int) -> int:
    print(f"REFUSING: {msg}", file=sys.stderr)
    return code


def _git_clean(rel: str) -> bool:
    """True iff <rel> is tracked and has no uncommitted working-tree changes."""
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", rel],
        capture_output=True, text=True,
    ).returncode == 0
    dirty = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", rel],
        capture_output=True, text=True,
    ).stdout.strip()
    return tracked and not dirty


def _norm_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return __import__("hashlib").sha256(data).hexdigest()


def manifest_committed(out_dir: Path) -> bool:
    manifest = out_dir / "SESSION_MANIFEST.md"
    if not manifest.exists():
        return False
    return _git_clean(manifest.relative_to(REPO_ROOT).as_posix())


def manifest_binds_task(out_dir: Path, task_path: Path) -> bool:
    """§3.1 pre-registration must bind to the ACTUAL task being run: the manifest has to
    record the task file's newline-normalized sha256, and it must match the task on disk."""
    manifest_text = (out_dir / "SESSION_MANIFEST.md").read_text(encoding="utf-8")
    actual = _norm_hash(task_path)
    return actual in manifest_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True, help="reports/live/<date>-<model> directory")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dryrun = os.environ.get("GAUNTLET_LIVE_DRYRUN") == "1"
    # Anchor cwd to the repo so {repo_root} in the task command (→ Path.cwd()) can never
    # resolve to an attacker-controlled agents/llm_patch_agent.py under some other dir.
    os.chdir(REPO_ROOT)
    out_dir = (REPO_ROOT / args.out).resolve()
    task_path = (REPO_ROOT / args.task).resolve()

    # gate 1: spec
    spec_hash = verify_spec(REPO_ROOT)

    task = TaskCase.from_dict(json.loads(task_path.read_text(encoding="utf-8")))
    provider, agent_rel = task_provider_and_agent(task)
    is_subscription = provider == "subagent"
    pvars = PROVIDER_VARS.get(provider, PROVIDER_VARS["openai"])
    if dryrun:
        model = "dryrun"
    elif is_subscription:
        model = os.environ.get("GAUNTLET_SUBAGENT_MODEL", "subagent")
    else:
        model = os.environ.get(pvars["model"], "")

    # gate 2: pre-registration — manifest exists, committed, clean, AND binds this task
    if not manifest_committed(out_dir):
        return fail(
            f"{out_dir / 'SESSION_MANIFEST.md'} must exist and be committed BEFORE the "
            "session runs (§3.1 pre-registration)", 3,
        )
    if not manifest_binds_task(out_dir, task_path):
        return fail(
            "SESSION_MANIFEST.md does not record the current task file's sha256 — the "
            "manifest must be bound to the exact task being run (§3.1)", 3,
        )
    # the task file and the actual agent code must themselves be committed-clean, or a dirty
    # edit could ride on a stale pre-registration
    for rel in (task_path.relative_to(REPO_ROOT).as_posix(), agent_rel):
        if not _git_clean(rel):
            return fail(f"{rel} has uncommitted changes — commit before a pre-registered run (§3.1)", 3)

    # gate 3: live environment (provider-aware)
    if dryrun:
        pass
    elif is_subscription:
        # subagent transport: no API key/price — only the captured-responses file (D-032)
        rp = os.environ.get("GAUNTLET_SUBAGENT_RESPONSES")
        if not rp:
            return fail("GAUNTLET_SUBAGENT_RESPONSES not set (subagent transport needs the "
                        "captured patches to replay)", 3)
        # resolve to absolute: the agent runs with cwd=worktree, where a relative path
        # would not exist (it would crash the agent and spuriously fail every run).
        os.environ["GAUNTLET_SUBAGENT_RESPONSES"] = str((REPO_ROOT / rp).resolve())
    else:
        missing = [
            v for v in (pvars["key"], pvars["model"],
                        "GAUNTLET_LIVE_PRICE_IN", "GAUNTLET_LIVE_PRICE_OUT")
            if not os.environ.get(v)
        ]
        if missing:
            return fail(f"live env vars not set: {', '.join(missing)}", 3)

    usage_file = out_dir / "usage.jsonl"
    os.environ["GAUNTLET_LIVE_USAGE_FILE"] = str(usage_file)
    max_usd = float(os.environ.get("GAUNTLET_LIVE_MAX_USD", "5.0"))

    traces_root = REPO_ROOT / "traces"

    # 4: the session itself (serial, isolated, canaried)
    data = run_suite([task], repo_root=REPO_ROOT, traces_root=traces_root)
    runs = data.results[task.task_id]

    # 5: transport-failure scan → environment fact, fed to rule 1
    transport_failed = [r.run_index for r in runs if "TRANSPORT_FAILURE" in _trace_text(r)]
    if transport_failed:
        print(f"transport failures in runs {transport_failed} → env recorded unstable (§3.4)")
        data.env.canary_post_ok = False

    # 6: budget gate
    spent = 0.0
    if usage_file.exists():
        for line in usage_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                spent += float(json.loads(line).get("est_usd") or 0.0)
    if spent > max_usd:
        return fail(
            f"budget exceeded: est ${spent:.4f} > cap ${max_usd} — session aborted, "
            "NOT published; usage ledger retained", 4,
        )

    # 7: secret scan over everything we are about to publish. The agent already scrubs the
    # key from its stdout, so this is the second line of defense; if it ever fires, purge
    # the on-disk staging traces too (not just skip publishing) so nothing secret lingers.
    for r in runs:
        text = _trace_text(r)
        if SECRET_RE.search(text):
            for rr in runs:
                p = REPO_ROOT / rr.trace_ref
                if p.exists():
                    p.write_text("[REDACTED: secret scan tripped]\n", encoding="utf-8", newline="\n")
            return fail(
                f"secret pattern detected in trace of run {r.run_index} — NOT publishing; "
                "staging traces purged", 5,
            )

    # 8: verdict + publish
    audit = decide(task, runs, data.env)
    report = build_audit_report([audit], data.env, spec_hash, HARNESS_VERSION)
    md = publish_session(out_dir, report, task, runs, args.task, provider, model)

    print(md)
    print(f"\nsession spent: ${spent:.4f} (cap ${max_usd})")
    print(f"published: {out_dir}")
    return 0


def publish_session(out_dir: Path, report, task, runs, task_path: str,
                    provider: str = "openai", model: str = "dryrun") -> str:
    """Write the §5 artifacts (audit_report.json + GAUNTLET_REPORT.md with the §A4 live
    header — stochastic disclaimer + subject-under-test wording + not-a-comparison clause —
    prepended + scrubbed traces). Returns the rendered markdown. Extracted so the publish
    path is unit-testable without the full live/git gate."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit_report.json").write_text(
        report.to_json() + "\n", encoding="utf-8", newline="\n"
    )
    md = build_live_header(provider, model) + render_markdown(
        report, {task.task_id: task}, {task.task_id: runs},
        task_paths={task.task_id: task_path},
    )
    (out_dir / "GAUNTLET_REPORT.md").write_text(md, encoding="utf-8", newline="\n")
    dest_traces = out_dir / "traces"
    dest_traces.mkdir(exist_ok=True)
    for r in runs:
        src = REPO_ROOT / r.trace_ref
        shutil.copy2(src, dest_traces / src.name)
    return md


def _trace_text(run_result) -> str:
    path = REPO_ROOT / run_result.trace_ref
    return path.read_text(encoding="utf-8") if path.exists() else ""


if __name__ == "__main__":
    sys.exit(main())
