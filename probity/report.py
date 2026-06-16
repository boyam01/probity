"""GAUNTLET_REPORT.md generation — frozen §2.4 section order, pure templates, zero LLM."""
from __future__ import annotations

from probity.stats import k_needed
from probity.types import AuditReport, RunResult, TaskAudit, TaskCase

PEDAGOGY_TEMPLATE = (
    "With k={k} runs and {s} successes, the 95% Wilson interval is [{lo}, {hi}]. "
    "This evidence can refute reliability claims above {hi}. "
    "It cannot confirm any claim above {lo}. "
    "To PASS a {r} claim from a clean record would require ≥{k_needed} consecutive successes."
)


def run_matrix(runs: list[RunResult] | None, audit: TaskAudit) -> tuple[str, list[str]]:
    """▮ = success, ▯ = failure, in run order. Falls back to counts when run
    records are unavailable (re-rendering from audit json alone)."""
    if runs:
        cells = "".join("▮" if r.success else "▯" for r in runs)
        notes = [
            f"run {r.run_index}: {r.failure_class}"
            + (" + critical_event" if r.critical_event else "")
            for r in runs
            if not r.success
        ]
        return cells, notes
    cells = "▮" * audit.successes + "▯" * (audit.k - audit.successes)
    return cells, ["(run order unavailable — re-rendered from audit json)"]


def render_task_section(
    audit: TaskAudit,
    task: TaskCase | None,
    runs: list[RunResult] | None,
    task_path: str | None = None,
) -> str:
    r_str = f"{task.required_reliability}" if task else "n/a"
    lo, hi = audit.wilson_95
    lines: list[str] = []

    # 1. VERDICT banner
    codes = " ".join(audit.reason_codes) if audit.reason_codes else "—"
    lines += [
        f"## {audit.task_id}",
        "",
        "### 1. VERDICT",
        "",
        f"# **{audit.verdict}** [{codes}]",
        "",
    ]
    if audit.diagnostics:
        lines += [f"Diagnostics (informational, do not affect the verdict): {', '.join(audit.diagnostics)}", ""]

    # 2. Claim vs Evidence
    lines += [
        "### 2. Claim vs Evidence",
        "",
        f"| claimed reliability r | observed | p̂ | 95% Wilson CI | p̂^k | pass^k lower |",
        f"|---|---|---|---|---|---|",
        f"| {r_str} | {audit.successes}/{audit.k} | {audit.p_hat} | [{lo}, {hi}] | {audit.pass_hat_k} | {audit.pass_k_lower} |",
        "",
    ]

    # 3. Run matrix
    cells, notes = run_matrix(runs, audit)
    lines += ["### 3. Run matrix", "", f"`{cells}`", ""]
    if runs:
        distinct = len({r.trace_hash for r in runs})
        warn = (
            "  ⚠ identical traces — the runs are not independent, so the Wilson CI overstates confidence"
            if distinct == 1 and len(runs) > 1 else ""
        )
        lines += [f"- distinct trace hashes: {distinct}/{len(runs)}{warn}", ""]
    lines += [f"- {n}" for n in notes]
    if notes:
        lines.append("")

    # 4. What this k can and cannot prove (frozen pedagogy template)
    if task is not None:
        pedagogy = PEDAGOGY_TEMPLATE.format(
            k=audit.k, s=audit.successes, lo=lo, hi=hi,
            r=task.required_reliability, k_needed=k_needed(task.required_reliability),
        )
    else:
        pedagogy = PEDAGOGY_TEMPLATE.format(
            k=audit.k, s=audit.successes, lo=lo, hi=hi, r="r", k_needed="?",
        )
    lines += ["### 4. What this k can and cannot prove", "", f"> {pedagogy}", ""]
    if audit.k_needed_estimate is not None:
        lines += [f"k_needed_estimate (at observed rate): {audit.k_needed_estimate}", ""]
    elif "CI_STRADDLES_THRESHOLD" in audit.reason_codes:
        # k_needed_estimate is None for two distinct reasons (stats.k_needed_estimate): p̂<=r
        # (truly unreachable at the observed rate) vs the search exceeding its cap (reachable, but
        # would need more runs than the cap). Only the former is "unreachable" (finding #5).
        if task is not None and audit.p_hat > task.required_reliability:
            lines += ["k_needed_estimate: exceeds the search cap (reachable, but needs many more runs)", ""]
        else:
            lines += ["k_needed_estimate: unreachable at observed rate", ""]

    # 5. Integrity findings
    s = audit.integrity_summary
    lines += [
        "### 5. Integrity findings",
        "",
        f"- false_claim: {s.false_claim}",
        f"- scope_violation: {s.scope_violation}",
        f"- test_tampering: {s.test_tampering}",
    ]
    if audit.critical_events:
        lines.append("- critical events:")
        lines += [
            f"  - run {e.run_index}: {e.rule} → `{e.path}`" for e in audit.critical_events
        ]
    else:
        lines.append("- critical events: none")
    lines.append("")

    # 6. Failure clusters
    lines += ["### 6. Failure clusters", ""]
    if audit.failure_clusters:
        lines += ["| class | count | example run |", "|---|---|---|"]
        lines += [
            f"| {c.class_} | {c.count} | {c.example_run} |" for c in audit.failure_clusters
        ]
    else:
        lines.append("none")
    lines.append("")

    # 7. Cost / latency
    lines += [
        "### 7. Cost / latency",
        "",
        f"- cost_usd: mean {audit.cost.mean}, cv {audit.cost.cv}",
        f"- latency_s: mean {audit.latency_s.mean}, cv {audit.latency_s.cv}",
        "",
    ]

    # 8. Reproduce
    repro = f"python -m probity run {task_path}" if task_path else "python -m probity run <task_case.json>"
    lines += ["### 8. Reproduce", "", "```", repro, "```", ""]
    return "\n".join(lines)


def render_markdown(
    report: AuditReport,
    tasks: dict[str, TaskCase],
    runs: dict[str, list[RunResult]],
    task_paths: dict[str, str] | None = None,
) -> str:
    task_paths = task_paths or {}
    header = [
        "# GAUNTLET REPORT",
        "",
        f"- harness_version: {report.harness_version}",
        f"- spec_hash: `{report.spec_hash}`",
        f"- env canary: pre={'ok' if report.env.canary_pre_ok else 'FAIL'} "
        f"post={'ok' if report.env.canary_post_ok else 'FAIL'}",
        f"- suite verdict: **{report.suite_verdict}**",
        "",
        "> Small k can only refute high-reliability claims, never confirm them. "
        "INSUFFICIENT is often the honest answer — that is the point.",
        "",
    ]
    sections = [
        render_task_section(
            audit,
            tasks.get(audit.task_id),
            runs.get(audit.task_id),
            task_paths.get(audit.task_id),
        )
        for audit in report.tasks
    ]
    return "\n".join(header) + "\n" + "\n".join(sections)
