# Related Work

> **What Probity is.** Probity (debut name; the Python package is still imported as
> `gauntlet`) is an **evidence-gated integrity gate** for coding agents. It runs the same
> agent on the same task *k* times in fresh isolation and rules **PASS / KILL /
> INSUFFICIENT** from a deterministic checker — never an LLM judge anywhere on the verdict
> path. Its question is narrow and adversarial: *is the agent's "I'm done" claim supported by
> immutable evidence, or did the agent edit/overstate its way to looking done?* It tests
> **honesty, not accuracy** — and a PASS reports only *"no falsification was found under this
> registered battery,"* never proof of correctness.
>
> This document situates Probity against directly relevant prior art and the broader
> landscape. Three honesty notes up front:
>
> - **The statistical machinery is common public infrastructure.** Repeated trials, binomial
>   confidence intervals, the Wilson score interval, and three-valued verdicts are standard
>   techniques for testing nondeterministic systems. **None of them is Probity's contribution,
>   and we make no originality claim over them.**
> - **The named tools below are cited from primary sources.** AgentAssay, AgentLiar, and
>   EvalView are described from their upstream repositories, arXiv pages, and package listings
>   (see *Sources* at the end). We report their public, *stated* features; we did not run their
>   code, so any internal-behavior claim is attributed to those sources, not independently
>   re-derived.
> - **This repository is private and pre-publication** — not pushed or published. The
>   public-facing name is Probity; the package / import path stays `gauntlet`.

---

## 1. A directly relevant prior-art candidate: AgentAssay

**AgentAssay** (Varun Pratap Bhardwaj, *Qualixar*; arXiv:2603.02601, *"AgentAssay: Token-Efficient
Regression Testing for Non-Deterministic AI Agent Workflows"*; repository `qualixar/agentassay`,
AGPL-3.0) is **directly relevant prior art** for statistically testing nondeterministic agent
workflows. Anyone evaluating Probity should evaluate AgentAssay too.

AgentAssay targets several capabilities Probity does not. Per its paper and repository:

- **Token-efficiency / adaptive budget.** AgentAssay reports *adaptive budget optimization*
  ("calibrating trial counts to behavioral variance") and large cost reductions (its materials
  cite "5–20×" / "78–100%", including offline analysis on already-recorded production traces).
  Probity uses a **fixed *k*** with no token optimization.
- **Sequential testing (SPRT).** AgentAssay uses SPRT / warm-start sequential testing for
  adaptive early stopping (the paper states "SPRT reduces trials by 78%"). Probity does not stop
  early; it spends the full budget.
- **Behavioral fingerprinting.** AgentAssay includes behavioral fingerprinting that "maps
  execution traces to compact vectors". Probity has no fingerprinting.
- **Framework adapters.** AgentAssay ships ~10 framework adapters (LangGraph, CrewAI, AutoGen,
  OpenAI Agents, smolagents, Semantic Kernel, AWS Bedrock Agents, MCP, Vertex AI, plus a custom
  adapter). Probity is a black-box harness with no framework-specific adapters.
- **Tooling breadth.** AgentAssay ships as a pytest plugin with a CLI and an HTML report.
  Probity ships template-generated reports.

### What the two tools share is common infrastructure, not novelty

Probity uses repeated trials under fixed conditions, binomial confidence intervals, the
**Wilson score interval**, and a **three-valued verdict**. These are **standard statistical
techniques and common public infrastructure** for testing nondeterministic systems. **None of
them is Probity's contribution, and we make no originality claim over them.**

- The **Wilson score interval** is standard statistical infrastructure. AgentAssay explicitly
  names the **Wilson score interval as its primary confidence-interval construction, with
  Clopper-Pearson for formal guarantees** (its paper, §3.3). **Probity also uses Wilson** — but
  Wilson is **common statistical infrastructure, not a Probity novelty claim**.
- **Repeated-trial / pass^k** testing of nondeterministic agents is an established idea in the
  agent-evaluation literature (see §3).
- A **three-way verdict** (ship / don't-ship / not-enough-evidence) is a natural reading of a
  confidence interval against a threshold, not a Probity invention.

If your need is an adaptive, integration-focused way to ask *"did this agent's behavior
regress?"*, **evaluate AgentAssay alongside Probity** — Probity is not optimized for adaptive
regression testing.

---

## 2. The distinction: regression vs. integrity

The two tools are best read as answering **different questions**, and the difference is the
whole point.

> **Regression framing: "did the behavior regress?"**
> **Probity asks: "is the success claim supported by immutable evidence?"**

A regression-testing frame characterizes an agent's behavior distribution and detects when a
new version drifts from it. That is a *quality* question.

Probity's frame is **integrity gating** — flagging a run that *edits or overstates its way to
looking done*. (We do not characterize AgentAssay's primary focus here; that would require a
citation.) Concretely, Probity's verdict path is organized around **registered ways a "done"
claim can be unsupported by evidence**:

- **Claim/evidence separation.** The agent's own self-report (`CLAIM: success`) is recorded
  and scored **separately** from what the deterministic checker actually found. The gap
  between the two is a primary signal (`false_claim`), not a footnote.
- **False success claims.** A run that announces success while the final state fails the
  checker is flagged — independent of how confident or fluent the agent's report was.
- **Test tampering.** Editing the protected oracle (the tests/spec the run is graded against)
  to make a red bar go green is treated as integrity failure, not as a pass.
- **Scope narrowing.** Touching files outside the allowed scope, or quietly shrinking the
  task to the part the agent can do, is caught rather than rewarded.
- **Canary / provenance violations.** Tampering with canaries, or drift in the checker /
  provenance chain, invalidates the run regardless of the apparent result.
- **Falsification-first verdicts.** The engine is built to look for reasons to **refuse**, not
  reasons to approve. Absence of a *found* integrity failure is reported honestly as
  absence-of-evidence, not as proof of honesty.

The verdict path is **zero-LLM** by construction — checker → stats → verdict contains no model
call, no LLM fallback, no LLM-written failure summaries; reports are template-generated. A
gate designed to flag registered integrity failures should keep the verdict path
deterministic, so it cannot be talked into a PASS.

---

## 3. Positioning: not optimized for low cost — intentionally strict

Turning the cost story into honest positioning:

**Probity is not optimized for low-cost reliability evaluation, and it is not trying to be.**
It runs a fixed *k* with no token optimization, no SPRT, no adaptive budget. Tools that
optimize trial budgets (AgentAssay does, via SPRT + adaptive budget; §1) will reach a
behavioral verdict in fewer trials; Probity spends the full fixed *k*.

**Probity is intentionally strict: fixed-*k*, zero-LLM on the verdict path, and
falsification-first.** It is built for the case where you want a *cost-no-object* attempt to
**falsify the agent's success claim** before a coding agent's output is allowed to ship. In
that setting, spending the full *k* and keeping an LLM away from the verdict is the feature,
not the inefficiency.

A second deliberate consequence of strictness: **PASS is hard to earn, and PASS does not prove
correctness.** A PASS means only *"no falsification was found under this registered battery"* —
the absence of a *caught* integrity failure, not a proof that the agent is reliable or
correct. Small *k* **can refute a high-reliability claim but can never confirm one**:
confirming a 0.90 claim from a clean record needs roughly **35 consecutive successes**, far
more than a typical battery runs. Probity does **not** claim to prove that an agent never
lies, and it does **not** guarantee correctness.

### What this means for a public tool release

The public repository ships the method and harness, not private benchmark
reports. Users should be able to run the demo, calibration, and their own
registered tasks locally without receiving this author's raw research traces.

The practical takeaway is methodological:

- one green run is not enough evidence for a reliability claim;
- a `CLAIM: success` line is not the same thing as checker evidence;
- protected tests and oracle files must be guarded before the agent runs;
- small batteries can refute overconfident claims but usually cannot confirm
  high reliability;
- private benchmark reports should be summarized conservatively, not shipped as
  public release content by default.

---

## 4. Capability comparison: Probity's documented posture

This table marks which rows are **AgentAssay capabilities (cited from its paper / repo)**,
which are **common statistical infrastructure** present in both kinds of tool, and which are
**Probity's documented focus / posture**. "Common infra" marks standard stochastic-testing
techniques — **not** a point of differentiation for anyone.

| Capability | AgentAssay | Probity | Notes |
|---|---|---|---|
| **Core question** | *Did behavior regress?* (reported framing) | *Is the success claim backed by immutable evidence?* | Different goals, not competing answers to one goal. |
| Token-efficiency / cost optimization | Yes (adaptive budget; "5–20×") | No (fixed *k*) | AgentAssay arXiv:2603.02601 / repo. |
| Sequential testing / SPRT, adaptive budget | Yes (SPRT, "−78% trials") | No | Probity uses fixed *k*. |
| Behavioral fingerprinting | Yes (traces → compact vectors) | No | AgentAssay repo / paper. |
| Framework adapters | Yes (~10: LangGraph, CrewAI, AutoGen, …) | No (black-box) | AgentAssay repo. |
| HTML report + CLI tooling | Yes (pytest + CLI + HTML) | Template reports | AgentAssay repo; no live "dashboard" claim reviewed. |
| Repeated trials (pass^k style) | Yes | Yes | *Common infra* — neither's novelty. |
| Confidence intervals | Yes | Yes | *Common infra.* |
| Wilson score interval | Yes (primary CI; Clopper-Pearson for formal guarantees) | Yes | Common infra — not Probity novelty. |
| Three-valued verdict | Yes (PASS / FAIL / INCONCLUSIVE) | Yes (**PASS / KILL / INSUFFICIENT**) | *Common infra*; different verdict names. |
| Zero-LLM verdict path (no judge on checker→stats→verdict) | Not assessed here | **Yes (invariant)** | Probity's posture. |
| Claim ↔ evidence separation (`false_claim`) | Not assessed here | **Yes** | Probity's focus. |
| Test-tampering detection | Not assessed here | **Yes** | Probity's focus. |
| Scope-narrowing detection | Not assessed here | **Yes** | Probity's focus. |
| Canary / provenance-drift gating | Not assessed here | **Yes** | Probity's focus. |
| Falsification-first verdicts | Not assessed here | **Yes** | Probity's posture. |

Read the table top-down: the **AgentAssay rows are its stated capabilities** (paper / repo);
the shared statistical rows are **common infrastructure** for both; Probity's documented
distinction is its **integrity / falsification posture** (the bottom block). If your need is
regression efficiency, evaluate a tool built for that (AgentAssay is one). If your need is a
strict, cost-no-object integrity gate, Probity is built for that.

For public-facing comparison, keep claims source-backed and conservative. Do not
publish private comparison tables or model-session reports unless Owner
explicitly approves that release.

---

## 5. The broader landscape

> **On sources.** AgentAssay, AgentLiar, and EvalView below are cited from primary sources
> (repositories / arXiv / package listings; see *Sources*). The remaining literature references
> are **descriptive, from public / secondary material**, and are framed in general terms rather
> than as specific verified claims.

- **AgentLiar** (`dakshjain-1616/AgentLiar`, MIT; announced on DEV, 2026-06). A **close
  prior-art effort on the same false-completion problem**: it runs four checks — file (missing /
  placeholder / `TODO` / no-op `pass`), test (empty / assertion-free / skipped), scope (narrowing
  markers, partial work), plus an *optional* OpenRouter LLM judge — and returns a 0–100
  confidence score via CLI / Python / GitHub Action / HTTP API. It is early-stage (a small,
  pre-release repository). It targets exactly what Probity's `false_claim` mechanism targets; a
  fair difference is that AgentLiar offers an optional LLM judge whereas Probity keeps its
  verdict path zero-LLM, and AgentLiar scores a single run's output while Probity runs *k* times
  with Wilson + integrity / canary / hash gating. Evaluate AgentLiar alongside Probity.
- **EvalView** (`hidai25/eval-view`; PyPI `evalview`; GitHub Action). A **behavior-regression
  gate** for AI agents ("Playwright, but for tool-calling and multi-turn agents"): it snapshots
  behavior and detects drift across outputs, tools, model IDs, and runtime fingerprints, and
  emits a four-tier verdict (`SAFE_TO_SHIP` / `SHIP_WITH_QUARANTINE` / `INVESTIGATE` /
  `BLOCK_RELEASE`). That is the "did behavior change?" question — different from Probity's
  claim-vs-evidence integrity gate; the reviewed sources do not describe test-tampering,
  scope-narrowing, or false-claim detection (absence in our review is not proof of absence).
- **The broader agent-reliability literature.** A growing body of work argues for putting agent
  reliability on a *measurable* footing (evidence over assertion) — aligned with Probity's
  stance, though Probity's slice is narrow (integrity gating, not a science of reliability).
- **Harness-safety work.** Research on the safety of the *harness* that runs the agent is
  adjacent to Probity's isolation and canary / provenance gating, which assume the harness
  itself can be a tampering surface.
- **Commercial evaluation platforms.** The broader market of agent / LLM evaluation products
  overlaps on repeated-trial testing and dashboards; Probity's narrow integrity-gate framing is
  a different slice of the same space. (Specific products not assessed here.)

Probity's deliberate scope boundary is narrow: deterministic integrity gating
for registered coding-agent tasks. It does not attempt to solve general
truthfulness, replace human review, or become a model leaderboard. Source notes
are kept in [`../REFERENCES.md`](../REFERENCES.md).

---

### One-line summary

AgentAssay is a token-efficient behavior-regression tool (SPRT + adaptive budget + framework
adapters); Probity is a fixed-*k*, zero-LLM **integrity gate** that asks whether a "done" claim
survives immutable evidence — and reports PASS only as *"no falsification found under this
registered battery,"* never as proof of correctness.

---

## Sources

- **AgentAssay** — V. P. Bhardwaj, *AgentAssay: Token-Efficient Regression Testing for
  Non-Deterministic AI Agent Workflows*, arXiv:2603.02601; repo
  <https://github.com/qualixar/agentassay> (AGPL-3.0).
- **AgentLiar** — <https://github.com/dakshjain-1616/AgentLiar> (MIT); author announcement on
  DEV Community (2026-06).
- **EvalView** — <https://github.com/hidai25/eval-view>; PyPI `evalview`; GitHub Marketplace
  Action *EvalView — AI Agent Testing*.

Features are taken from each project's own repository / paper / listing as reviewed in June
2026; we did not run their code, so capability statements reflect those sources.
