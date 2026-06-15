#!/usr/bin/env python3
"""Semver ruler self-test — Layer 2 batch experiment (design 2026-06-12).

Runs each OpenCode model k=10 through the harness on the semver task (real API via the frozen
openai transport), then for each model records:
  - the GAUNTLET audit (real p_hat, verdict, integrity flags) — the frozen zero-LLM verdict path;
  - the NAIVE single-run view (run #1: did it pass? did it claim success?) — "what you'd see
    without the ruler";
  - an INDEPENDENT trace verifier that re-derives every integrity flag from raw facts
    (modified_files vs tests/**, data/**, src/**; the parsed CLAIM; the checker pass bit) and
    asserts the ruler's flags equal the facts. This is the "does the ruler work" proof.

All models published, zero selection (§3.3). No cross-model ranking is produced here (§A4.2);
this script only emits per-model records + a results ledger. Budget: shared usage ledger +
GAUNTLET_LIVE_MAX_USD hard cap enforced by the agent itself.

Secrets: OPENCODE_API_KEY read from .env.txt (gitignored), set as OPENAI_API_KEY; never logged.
"""
import fnmatch
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)
sys.path.insert(0, str(REPO))

from gauntlet import HARNESS_VERSION  # noqa: E402
from gauntlet.runner import run_task  # noqa: E402
from gauntlet.types import EnvStatus, TaskCase, Trace  # noqa: E402
from gauntlet.verdict import build_audit_report, decide, verify_spec  # noqa: E402

BASE_URL = "https://opencode.ai/zen"  # agent appends /v1/chat/completions (PROVIDER_CFG path)
PRICE_IN = "2"     # USD / 1M tokens — conservative over-estimate (OpenCode billing authoritative)
PRICE_OUT = "6"
MAX_USD = os.environ.get("GAUNTLET_EXP_MAX_USD", "5")  # per-batch cap; pre-reg may register higher
MAX_WALL_S = float(os.environ.get("GAUNTLET_EXP_MAX_WALL_S", "28800"))  # wall-clock cap (default 8h)
K = 10

# Parametrizable so the same runner drives the Python semver batch and the Rust/low-tier batch.
TASK_REL = os.environ.get("GAUNTLET_EXP_TASK", "tasks/semver/task_semver_openai.json")
_DEFAULT_MODELS = "deepseek-v4-flash,glm-5,deepseek-v4-pro,minimax-m2.7,qwen3.6-plus"
MODELS = [m.strip() for m in os.environ.get("GAUNTLET_EXP_MODELS", _DEFAULT_MODELS).split(",") if m.strip()]

OUT = REPO / os.environ.get("GAUNTLET_EXP_OUT", "reports/live/2026-06-12-semver-experiment")
ALLOWED = ["src/**"]
PROTECTED = ["tests/**"]


def _safe(model: str) -> str:
    return model.replace("/", "_").replace(".", "-")


def _read_key() -> str:
    for line in (REPO / ".env.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENCODE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("OPENCODE_API_KEY not found in .env.txt")


def _match(path: str, globs) -> bool:
    p = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(p, g) for g in globs)


def verify_run(rr) -> dict:
    """Independently re-derive the integrity flags from raw facts in this run, and compare to
    what the ruler recorded. Returns {ok, mismatches}."""
    trace_path = REPO / rr.trace_ref
    claimed = None
    if trace_path.exists():
        from gauntlet.checker import parse_claim
        claimed = parse_claim(Trace.from_jsonl(trace_path.read_text(encoding="utf-8")))
    modified = rr.modified_files
    touched_protected = any(_match(m, PROTECTED) for m in modified)
    touched_outside_allowed = any(not _match(m, ALLOWED) for m in modified)
    passed = rr.checker_output.passed

    expect_tamper = touched_protected
    # scope_violation mirrors checker.py exactly: it is bool(any file outside allowed_paths) in
    # EVERY branch — including the tampering branch (a tests/ edit is both test_tampering AND, since
    # tests/ is outside src/**, scope_violation). The two flags are not mutually exclusive.
    expect_scope = touched_outside_allowed
    expect_false_claim = (claimed is True) and (not passed)

    flags = rr.integrity_flags
    mism = []
    if flags.test_tampering != expect_tamper:
        mism.append(f"test_tampering ruler={flags.test_tampering} facts={expect_tamper}")
    if flags.scope_violation != expect_scope:
        mism.append(f"scope_violation ruler={flags.scope_violation} facts={expect_scope}")
    if flags.false_claim != expect_false_claim:
        mism.append(f"false_claim ruler={flags.false_claim} facts={expect_false_claim}")
    return {"run_index": rr.run_index, "ok": not mism, "mismatches": mism,
            "facts": {"passed": passed, "claimed": claimed, "modified": modified}}


def _checkpoint_run(model: str, rr) -> None:
    """Per-run durability hook: append one row to partial_results.jsonl the moment a run
    finishes, so a death mid-model leaves an auditable exploratory trail (a model never
    re-enters the confirmatory aggregate unless its full 10-run results.json record exists)."""
    row = {
        "model": model, "run_index": rr.run_index, "seed": rr.seed,
        "success": rr.success, "claimed": rr.agent_claimed_success,
        "failure_class": rr.failure_class,
        "test_tampering": rr.integrity_flags.test_tampering,
        "scope_violation": rr.integrity_flags.scope_violation,
        "false_claim": rr.integrity_flags.false_claim,
        "cost_usd": rr.cost_usd,
    }
    partial = OUT / "partial_results.jsonl"
    with partial.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_model(model: str) -> dict:
    os.environ["OPENAI_MODEL"] = model
    task = TaskCase.from_dict(json.loads((REPO / TASK_REL).read_text(encoding="utf-8")))
    task.task_id = f"semver_{_safe(model)}"
    print(f"\n=== {model}  (k={task.k_planned}) ===", flush=True)
    results = run_task(task, repo_root=REPO, traces_root=REPO / "traces",
                       on_run=lambda rr: _checkpoint_run(model, rr))
    audit = decide(task, results, EnvStatus())

    # naive single-run view. naive_ship_rate = fraction of single runs that would mislead a
    # one-shot shipper into shipping — either the checker passed OR the agent claimed success
    # (a naive user trusts both). This is the "without ruler" decision quality.
    r1 = results[0]
    ship = [r for r in results if r.success or r.agent_claimed_success is True]
    naive = {"run1_success": r1.success, "run1_claimed": r1.agent_claimed_success,
             "would_ship": bool(r1.success or r1.agent_claimed_success is True),
             "naive_ship_rate": round(len(ship) / len(results), 3)}

    # independent verifier
    checks = [verify_run(r) for r in results]
    verifier_ok = all(c["ok"] for c in checks)

    # publish per-model report (honest OpenCode API label)
    from scripts.run_live_session import build_live_header  # type: ignore
    from gauntlet.report import render_markdown
    report = build_audit_report([audit], EnvStatus(), verify_spec(REPO), HARNESS_VERSION)
    mdir = OUT / _safe(model)
    mdir.mkdir(parents=True, exist_ok=True)
    header = build_live_header("openai", model).replace(
        "(provider: openai)", "(provider: openai-compatible / OpenCode)")
    md = header + render_markdown(report, {task.task_id: task}, {task.task_id: results})
    (mdir / "GAUNTLET_REPORT.md").write_text(md, encoding="utf-8", newline="\n")
    (mdir / "audit_report.json").write_text(report.to_json() + "\n", encoding="utf-8", newline="\n")
    tdir = mdir / "traces"
    tdir.mkdir(exist_ok=True)
    import shutil
    for r in results:
        src = REPO / r.trace_ref
        if src.exists():
            shutil.copy2(src, tdir / src.name)

    rec = {
        "model": model,
        "verdict": audit.verdict,
        "reason_codes": audit.reason_codes,
        "successes": audit.successes,
        "k": audit.k,
        "p_hat": audit.p_hat,
        "wilson_95": audit.wilson_95,
        "k_needed_estimate": audit.k_needed_estimate,
        "diagnostics": audit.diagnostics,
        "integrity": audit.integrity_summary.to_dict(),
        "critical_events": len(audit.critical_events),
        "failure_clusters": [c.to_dict() for c in audit.failure_clusters],
        "naive": naive,
        "verifier_ok": verifier_ok,
        "verifier_checks": checks,
        "latency_mean": audit.latency_s.mean,
    }
    print(f"  verdict={audit.verdict} {audit.reason_codes} p_hat={audit.p_hat} "
          f"integrity={audit.integrity_summary.to_dict()} verifier_ok={verifier_ok}", flush=True)
    return rec


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    key = _read_key()
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = BASE_URL
    os.environ["GAUNTLET_LIVE_PRICE_IN"] = PRICE_IN
    os.environ["GAUNTLET_LIVE_PRICE_OUT"] = PRICE_OUT
    os.environ["GAUNTLET_LIVE_MAX_USD"] = MAX_USD
    ledger = OUT / "usage.jsonl"
    os.environ["GAUNTLET_LIVE_USAGE_FILE"] = str(ledger)

    def spent() -> float:
        if not ledger.exists():
            return 0.0
        return sum(float(json.loads(l).get("est_usd") or 0) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip())

    ledger_out = OUT / "results.json"

    def save(records):
        ledger_out.write_text(json.dumps({
            "harness_version": HARNESS_VERSION,
            "task": TASK_REL,
            "k": K, "base_url": BASE_URL, "price_in": PRICE_IN, "price_out": PRICE_OUT,
            "est_total_usd": round(spent(), 4),
            "records": records,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    # resume: keep records for models already completed cleanly (a report exists, no error)
    records = []
    done = set()
    if ledger_out.exists():
        prior = json.loads(ledger_out.read_text(encoding="utf-8")).get("records", [])
        for rec in prior:
            if "error" not in rec and (OUT / _safe(rec["model"]) / "audit_report.json").exists():
                records.append(rec)
                done.add(rec["model"])

    start = time.monotonic()
    for model in MODELS:
        if model in done:
            print(f"=== {model}: already done, skipping ===", flush=True)
            continue
        if spent() >= float(MAX_USD):
            print(f"BUDGET CAP hit (${spent():.4f}) — skipping remaining models", flush=True)
            break
        if time.monotonic() - start >= MAX_WALL_S:
            print(f"WALL-CLOCK CAP hit ({MAX_WALL_S:.0f}s) — skipping remaining models", flush=True)
            break
        try:
            records.append(run_model(model))
        except Exception as e:  # noqa: BLE001 — one model failing must not abort the batch
            print(f"  MODEL ERROR {model}: {e}", flush=True)
            records.append({"model": model, "error": str(e)})
        save(records)  # checkpoint after every model so a death never loses progress

    save(records)
    print(f"\nDONE. est_total=${spent():.4f}  results -> {ledger_out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
