# Public claim register

This file is the source of truth for what Probity may say in public copy. It is
stricter than marketing copy on purpose.

## Allowed claims

| Claim | Status | Evidence / source | Safe wording |
|---|---|---|---|
| Probity is a methodology and local harness for testing AI coding-agent success claims. | Supported | README, `INTERFACE_CONTRACT.md`, `gauntlet/runner.py`, `gauntlet/checker.py` | "Agent reliability methodology for false-green testing of AI coding agents." |
| Built-in checker -> stats -> verdict path is zero-LLM. | Supported for built-in path | `gauntlet/`, `gauntlet/verdict.py`, `gauntlet/checker.py` | "No LLM on the built-in verdict path." |
| Probity separates the agent's claim from checker evidence. | Supported | `parse_claim`, `RunResult.agent_claimed_success`, `IntegrityFlags.false_claim` | "Claim and evidence are recorded separately." |
| Probity detects protected-test tampering for registered protected paths. | Supported with scope | `checker.protected_paths`, `assert_protected`, calibration U4 | "Edits to registered protected paths are flagged as audit integrity failures." |
| Probity uses repeated trials and Wilson intervals. | Supported, not novel | `gauntlet/stats.py`, `docs/RELATED_WORK.md` | "Uses repeated trials and Wilson intervals, common statistical infrastructure." |
| PASS means no falsification found under the registered battery. | Supported boundary | `gauntlet/verdict.py`, README, methodology docs | "PASS is absence of found falsification, not proof of correctness." |
| Docker can run the demo/calibration/test path. | Implemented, needs daemon verification before public launch | `Dockerfile`, `scripts/probity_docker_entry.py`, `docs/DOCKER.md` | "Docker wrapper is provided for local demo and gates." |
| Probity can wrap Codex CLI, Claude Code, or other local CLI agents. | Supported by subprocess adapter | `INTERFACE_CONTRACT.md`, `agent.adapter = "subprocess"` | "Probity is agent-agnostic and can run bounded CLI agents as subprocesses." |

## Boundary claims

| Claim | Required qualifier |
|---|---|
| "false-green testing" | Must explain that it applies to registered tasks with deterministic checkers. |
| "agent reliability" | Must not imply full real-world reliability. It is reliability under a registered battery. |
| "zero-LLM" | Must say built-in verdict path. Custom script checkers are task-author trust inputs. |
| "detects test tampering" | Must say registered protected paths. |
| "evidence-based" | Must link to evidence bundle / reproducibility docs. |

## Not allowed

Do not say:

- first;
- only;
- unique;
- proves correctness;
- proves agents do not lie;
- guarantees safe code;
- detects all hallucinations;
- kills hallucinations;
- better than AgentAssay;
- Wilson as novelty;
- model leaderboard.
- private benchmark report.

## Pre-publication rule

If a sentence is not clearly supported by this file, downgrade it or add
evidence before publishing.

Private research reports, raw traces, model-session logs, keys, and benchmark
artifacts are not public-release content. Summarize only the general method in
README/docs unless Owner explicitly approves publishing a report.
