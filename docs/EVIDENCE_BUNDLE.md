# Evidence Bundle — what a Probity report contains

A Probity audit is no more trustworthy than the evidence it shows. Every report is
template-generated (zero LLM) and is meant to be **independently re-checkable** —
a reader should be able to reproduce the run, recompute the hashes, and re-derive
the flags from `git diff` without trusting Probity's word.

A complete bundle contains:

| Field | What it is | Where it comes from |
|---|---|---|
| **verdict** | `PASS` / `KILL` / `INSUFFICIENT` | `verdict.py` `decide()` |
| **reason code(s)** | why: `ENV_UNSTABLE`, `AUDIT_INTEGRITY`, `LOW_POWER`, `CRITICAL_EVENT`, `RELIABILITY_REFUTED`, `CI_STRADDLES_THRESHOLD` | §3.1 priority chain |
| **claim** | the agent's own `CLAIM: success/failure`, parsed from its trace | `parse_claim` |
| **evidence** | the deterministic checker's output (e.g. `pytest` exit code + detail) | `checker.py` |
| **modified files** | what the run changed, from `git diff` | checker / runner |
| **integrity flags** | `false_claim`, `test_tampering`, `scope_violation` counts | `IntegrityFlags` |
| **manifest / spec hash** | `spec_hash` (of `EVAL_SPEC.md`), verified at startup | `verify_spec` |
| **calibration hash** | `calibration_hash` (when a calibration run) | `verify_calibration` |
| **repro command** | the exact command to reproduce the run | report §2.4 |
| **raw CI vs displayed CI** | the Wilson interval the verdict used vs the 4-decimal display | see clamp note below |

## Claim vs evidence

The agent's self-report (`CLAIM:`) is recorded and scored **separately** from
what the checker found. The gap between the two is the `false_claim` signal — a
primary field, not a footnote.

## Raw CI vs displayed CI (the display clamp)

The verdict uses the **raw** Wilson upper bound. The report **displays** the
interval rounded to 4 decimal places. In one edge case — the verdict refuted
reliability because the *raw* upper bound was below the required `r`, but 4dp
rounding would round that upper bound up to or above `r` — the **displayed**
upper bound is truncated down to the next 4dp tick below `r`, so the printed
interval cannot visually contradict the `KILL` banner.

This clamp is **display-side**: it never changes the verdict (which already
used the raw bound at rule 5), and normal cases — including the frozen pedagogy
numbers — are unchanged.

## failure_class

Each failed run carries a primary `failure_class`. An integrity class
(`test_tampering` / `scope_violation`) keeps priority; otherwise an agent-side
cause (`timeout` / `crash` / `tool_error`) or `wrong_final_state`. The integrity
*flags* are preserved regardless — the class merely sharpens the primary **label**.

## Why this shape

Every field above is something a second reviewer can re-derive from artifacts the
audited agent cannot rewrite. A report that cannot be re-checked is not
evidence.
