"""Phase 4: frozen §2.4 section order and template content. Pure templates, zero LLM."""
import re
from pathlib import Path

from probity import HARNESS_VERSION
from probity.report import render_markdown
from probity.types import EnvStatus
from probity.verdict import build_audit_report, decide

from tests.test_verdict import ENV_OK, _runs, _task


def _render(r: float = 0.90, successes: int = 7, env: EnvStatus = ENV_OK):
    task = _task(r=r)
    runs = _runs(successes)
    audit = decide(task, runs, env)
    report = build_audit_report([audit], env, "sha256:" + "a" * 64, HARNESS_VERSION)
    md = render_markdown(report, {"t": task}, {"t": runs}, {"t": "tasks/example.json"})
    return md, audit


def test_section_order_is_frozen():
    md, _ = _render()
    order = [
        "### 1. VERDICT",
        "### 2. Claim vs Evidence",
        "### 3. Run matrix",
        "### 4. What this k can and cannot prove",
        "### 5. Integrity findings",
        "### 6. Failure clusters",
        "### 7. Cost / latency",
        "### 8. Reproduce",
    ]
    positions = [md.index(h) for h in order]
    assert positions == sorted(positions)


def test_verdict_banner_kill_with_reason():
    md, _ = _render(r=0.90, successes=6)
    assert "**KILL** [RELIABILITY_REFUTED]" in md


def test_run_matrix_symbols_in_run_order():
    md, _ = _render(successes=7)  # runs 1..7 succeed, 8..10 fail
    assert "`▮▮▮▮▮▮▮▯▯▯`" in md


def test_pedagogy_paragraph_has_frozen_numbers():
    md, _ = _render(r=0.90, successes=7)
    assert (
        "With k=10 runs and 7 successes, the 95% Wilson interval is [0.3968, 0.8922]."
        in md
    )
    assert "refute reliability claims above 0.8922" in md
    assert "cannot confirm any claim above 0.3968" in md
    assert "To PASS a 0.9 claim from a clean record would require ≥35 consecutive successes." in md


def test_insufficient_unreachable_note():
    md, audit = _render(r=0.80, successes=8)
    assert audit.k_needed_estimate is None
    assert "unreachable at observed rate" in md


def test_k_needed_cap_overflow_not_labeled_unreachable():
    """When p̂ > r but k_needed exceeds the search cap, the report must NOT say 'unreachable at
    observed rate' — it IS reachable, just beyond the cap (finding #5)."""
    md, audit = _render(r=0.85, successes=9)
    assert audit.k_needed_estimate is None
    assert audit.p_hat > 0.85
    assert "exceeds the search cap" in md
    assert "unreachable at observed rate" not in md


def test_kill_edge_display_clamp_below_threshold():
    """#4b: raw Wilson upper bound is below r, but 4dp rounding would display it AT/above r. The
    verdict must still KILL on the RAW value, and the DISPLAYED upper bound must be clamped below r
    so the report cannot contradict the KILL banner. Reporting-only; raw CI/verdict unchanged."""
    from probity.stats import wilson_ci
    _lo, raw_hi = wilson_ci(1, 10)
    r = round(raw_hi, 4)              # 0.4042 — 4dp rounding goes UP across r
    assert raw_hi < r                # precondition: the edge actually rounds up
    md, audit = _render(r=r, successes=1)
    # verdict uses RAW CI (raw hi < r -> KILL); if it used the rounded hi (== r) it would not KILL
    assert audit.verdict == "KILL"
    disp_lo, disp_hi = audit.wilson_95
    assert disp_hi < r               # displayed upper bound clamped below threshold (was == r pre-#4b)


def test_reproduce_contains_exact_command():
    md, _ = _render()
    assert "python -m probity run tasks/example.json" in md


def test_render_without_runs_falls_back():
    task = _task(r=0.90)
    runs = _runs(7)
    audit = decide(task, runs, ENV_OK)
    report = build_audit_report([audit], ENV_OK, "sha256:" + "a" * 64, HARNESS_VERSION)
    md = render_markdown(report, {}, {})  # re-render from audit json alone
    assert "run order unavailable" in md
    assert "▮▮▮▮▮▮▮▯▯▯" in md


def test_header_carries_spec_hash_and_suite_verdict():
    md, _ = _render(r=0.90, successes=6)
    assert "spec_hash: `sha256:" in md
    assert "suite verdict: **KILL**" in md
    assert "Small k can only refute" in md
