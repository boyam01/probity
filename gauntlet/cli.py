"""CLI: python -m gauntlet run|calibrate|report. Zero LLM; reports are template-only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gauntlet import HARNESS_VERSION
from gauntlet.runner import TaskRejected, WorkspaceSource, make_adapter, run_one, run_suite
from gauntlet.types import TaskCase
from gauntlet.verdict import (
    CalibrationDrift,
    SpecDrift,
    build_audit_report,
    decide,
    verify_calibration,
    verify_spec,
)

CALIBRATION_ORDER = [
    "cal_R1", "cal_R2", "cal_R3",
    "cal_U1", "cal_U2", "cal_U3", "cal_U4",
    "cal_B1", "cal_B2", "cal_I1",
]


def _load_task(path: Path) -> TaskCase:
    return TaskCase.from_dict(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# calibrate
# ---------------------------------------------------------------------------

def cmd_calibrate(args: argparse.Namespace) -> int:
    repo_root = Path.cwd()
    try:
        spec_hash = verify_spec(repo_root)
    except SpecDrift as e:
        print(f"REFUSING TO RUN: {e}")
        return 2
    try:
        verify_calibration(repo_root)  # finding #2: catch silently-weakened calibration fixtures
    except CalibrationDrift as e:
        print(f"REFUSING TO RUN: {e}")
        return 2

    cal_dir = repo_root / "tasks" / "calibration_v1"
    expected = {
        e["task_id"]: e
        for e in json.loads((cal_dir / "expected.json").read_text(encoding="utf-8"))
    }
    traces_root = repo_root / "traces"

    rows = []
    fp = fn = 0
    for task_id in CALIBRATION_ORDER:
        task = _load_task(cal_dir / f"{task_id}.json")
        data = run_suite([task], repo_root=repo_root, traces_root=traces_root)
        audit = decide(task, data.results[task_id], data.env)

        exp = expected[task_id]
        ok = audit.verdict == exp["verdict"] and audit.reason_codes == exp["reason_codes"]
        for diag in exp.get("diagnostics_include", []):
            ok = ok and diag in audit.diagnostics
        if exp.get("check_k_needed"):
            ok = ok and audit.k_needed_estimate == exp["k_needed_estimate"]

        if exp["verdict"] != "KILL" and audit.verdict == "KILL":
            fp += 1
        if exp["verdict"] == "KILL" and audit.verdict != "KILL":
            fn += 1

        rows.append((task_id, exp, audit, ok))

    print(f"\nCALIBRATION MATRIX (calibration_v1, spec {spec_hash[:18]}...)")
    print(f"{'ID':<8} {'expected':<38} {'actual':<38} match")
    print("-" * 96)
    matched = 0
    for task_id, exp, audit, ok in rows:
        e_str = f"{exp['verdict']} {exp['reason_codes']}"
        a_str = f"{audit.verdict} {audit.reason_codes}"
        mark = "OK" if ok else "MISMATCH"
        matched += ok
        print(f"{task_id:<8} {e_str:<38} {a_str:<38} {mark}")
        extra = []
        if exp.get("diagnostics_include"):
            extra.append(f"diagnostics={audit.diagnostics}")
        if exp.get("check_k_needed"):
            extra.append(f"k_needed={audit.k_needed_estimate} (expected {exp['k_needed_estimate']})")
        if extra:
            print(f"{'':<8} {' / '.join(extra)}")
    print("-" * 96)
    print(f"matched {matched}/{len(rows)}   FP={fp}   FN={fn}")
    if matched == len(rows) and fp == 0 and fn == 0:
        print("CALIBRATION: 10/10 — PASS")
        return 0
    print("CALIBRATION FAILED — do NOT patch per-case; report to Owner (frozen spec §0.1.3)")
    return 1


# ---------------------------------------------------------------------------
# run (single task; --once for the naive single-run demo)
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    repo_root = Path.cwd()
    try:
        spec_hash = verify_spec(repo_root)
    except SpecDrift as e:
        print(f"REFUSING TO RUN: {e}")
        return 2

    task = _load_task(Path(args.task))
    traces_root = repo_root / "traces"

    if args.once:
        adapter = make_adapter(task)
        seed = args.seed
        workspace_src = (repo_root / task.workspace.path).resolve()
        with WorkspaceSource(workspace_src, task.workspace.pristine_ref) as (source_repo, ref):
            result = run_one(
                task, adapter, run_index=1, seed=seed,
                source_repo=source_repo, pristine_ref=ref,
                repo_root=repo_root, traces_root=traces_root,
            )
        print(f"single run (seed={seed}) of {task.task_id} with {adapter.agent_id}")
        print(f"  checker: {result.checker_output.detail}")
        if result.success:
            print("  result: SUCCESS")
            print("\n  naive conclusion: ✓ ship it")
        else:
            print(f"  result: FAILURE ({result.failure_class})")
            print("\n  naive conclusion: needs another look")
        return 0

    data = run_suite([task], repo_root=repo_root, traces_root=traces_root)
    audit = decide(task, data.results[task.task_id], data.env)
    report = build_audit_report([audit], data.env, spec_hash, HARNESS_VERSION)

    out_dir = Path(args.out) if args.out else repo_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{task.task_id}_audit.json"
    json_path.write_text(report.to_json() + "\n", encoding="utf-8", newline="\n")

    from gauntlet.report import render_markdown

    md = render_markdown(
        report,
        {task.task_id: task},
        {task.task_id: data.results[task.task_id]},
        task_paths={task.task_id: args.task},
    )
    md_path = out_dir / f"{task.task_id}_GAUNTLET_REPORT.md"
    md_path.write_text(md, encoding="utf-8", newline="\n")

    print(md)
    print(f"\nwritten: {json_path}")
    print(f"written: {md_path}")
    return 0 if report.suite_verdict == "PASS" else 1


# ---------------------------------------------------------------------------
# report (re-render markdown from an audit_report.json)
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    from gauntlet.report import render_markdown
    from gauntlet.types import AuditReport

    report = AuditReport.from_json(Path(args.audit_json).read_text(encoding="utf-8"))
    print(render_markdown(report, {}, {}))
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows consoles may default to a legacy codepage; reports use ▮▯✓ etc.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="gauntlet", description="AGENT-GAUNTLET v0.1")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a task k times and emit the audit verdict")
    p_run.add_argument("task", help="path to task_case.json")
    p_run.add_argument("--once", action="store_true", help="single run (the naive demo)")
    p_run.add_argument("--seed", type=int, default=1)
    p_run.add_argument("--out", default=None, help="output directory for reports")
    p_run.set_defaults(func=cmd_run)

    p_cal = sub.add_parser("calibrate", help="run the 10-case calibration matrix")
    p_cal.set_defaults(func=cmd_calibrate)

    p_rep = sub.add_parser("report", help="re-render markdown from audit_report.json")
    p_rep.add_argument("audit_json")
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TaskRejected as e:
        print(f"TASK REJECTED: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
