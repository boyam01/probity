# Launch Copy Pack

High-exposure, **honesty-safe** copy for a future public launch. Every line here stays inside
what the repo can show. **Nothing in this file authorizes publishing** — it is draft copy.

Rules for all copy below: evidence-led, no hype beyond evidence, no insults toward prior art
(AgentAssay, AgentLiar, EvalView are acknowledged), and no market-uniqueness claims. The brand
says **false greens** / *falsely claim done* — never "lie." See *Forbidden marketing claims* at
the end.

---

## 1. GitHub repo descriptions

- **Short:** Agent reliability methodology for false-green testing.
- **Punchy:** Claim -> evidence -> repeated trials -> verdict for AI coding agents.
- **Conservative:** A falsification-first method for testing whether a coding agent's "done" claim survives repo evidence.

## 2. Suggested GitHub topics

`ai-agents` `coding-agents` `agent-evaluation` `agent-reliability` `llmops`
`software-testing` `ci` `test-automation` `developer-tools` `deterministic-testing`
`reliability-testing` `false-green` `ai-safety` `provenance` `audit` `docker`

## 3. README call-to-action

> If you use coding agents, don't ask "did it *sound* done?"
> Ask: **what evidence lets it say done?**

## 4. Ethical star CTA

> If this matches a failure mode you've seen with coding agents, star the repo to follow the launch.

## 5. X / Twitter (3 variants)

**A —**
Your coding agent says "done, tests pass." Probity asks: what evidence says so?
It is an agent reliability methodology: run the task *k* times in fresh isolation, compare claim vs checker evidence, then return PASS / KILL / INSUFFICIENT without an LLM on the verdict path.
False-green testing for coding agents.

**B —**
One run says "ship it." Ten runs say KILL.
A coding agent passed once; on replay it went 7/10 → 95% interval [0.40, 0.89], below a 0.90 reliability claim → KILL.
A single green isn't evidence. Small samples can refute high reliability, never confirm it.

**C —**
The sneaky failure: an agent turns the bar green by editing the tests.
Probity treats editing the protected tests as an integrity failure — KILL, no statistics — and scores the agent's claim separately from what the checker actually found.

## 6. LinkedIn (1 variant)

Coding agents keep getting better at writing code — and at making the build look green without
doing the work: weakening a test, narrowing scope, or claiming a success the checker never
confirmed.

Probity is a falsification-first, zero-LLM integrity gate for coding agents. It re-runs the same
task *k* times in fresh git-worktree isolation and rules PASS / KILL / INSUFFICIENT from a
deterministic checker — never an LLM judge on the verdict path. It separates what the agent
*claims* from what the evidence *shows*, and blocks the unsupported greens.

It is honest about its limits: PASS means "no falsification found under this registered battery,"
not proof of correctness; a small sample can refute a high-reliability claim but can't confirm
one, so the answer is often INSUFFICIENT. Related work (AgentAssay, AgentLiar, EvalView) is
acknowledged — repeated trials, Wilson intervals, and three-valued verdicts are common
infrastructure, not our invention; the focus is the integrity gating.

If you ship code from coding agents: the question isn't "did it sound done?" — it's "what
evidence lets it say done?"

## 7. Hacker News — Show HN

**Title:** Show HN: Probity - an agent reliability methodology for false-green testing

**Body:**
Probity is a methodology and local harness for testing whether a coding agent's "done" claim is
supported by repo evidence. It re-runs the same task *k* times in fresh git-worktree isolation and
returns PASS / KILL / INSUFFICIENT from a deterministic checker, with no LLM on the verdict path
(reports are template-generated).

It's built around one question: is the agent's "done" claim supported by repo evidence? It
records the agent's self-report separately from the checker, and flags test-tampering (editing
the protected tests → unconditional KILL), scope-narrowing, and false success claims. A canary
attributes environment faults so they aren't blamed on the agent.

Honesty boundaries it keeps: PASS means "no falsification found under this registered battery,"
not proof of correctness. A small sample can refute a high-reliability claim but can't confirm
one — confirming r=0.90 from a clean record needs ~35 consecutive successes, so the honest
answer is frequently INSUFFICIENT.

Stack: Python standard library + system git, zero third-party runtime dependencies. Repeated
trials, Wilson intervals, and three-valued verdicts are common infrastructure, not our
invention; related work (AgentAssay, AgentLiar, EvalView) is documented in the repo. Feedback
welcome — especially on the verdict logic and the false-green failure modes you've hit.

## 8. Reddit (1 variant)

*(r/programming / r/devops tone)*

I kept hitting the same pattern with coding agents: the build goes green, but the work isn't
actually done — a test got weakened, scope got quietly narrowed, or the agent said "done" and
the checker never confirmed it.

So I built Probity: it re-runs the task *k* times in isolation and rules PASS / KILL /
INSUFFICIENT from a deterministic checker, with no LLM on the verdict path. It scores the
agent's claim separately from the evidence and flags test-tampering / scope-narrowing / false
claims.

It's deliberately strict and honest: PASS just means "no falsification found under this
battery," not proof of correctness, and it often returns INSUFFICIENT because a small sample
can't confirm high reliability. Curious whether others have seen these false-green failure
modes, and how you catch them today.

## 9. Product Hunt

- **Tagline:** Agent reliability methodology for false-green testing.
- **Short description:** Probity tests whether a coding agent's "done" claim survives repo
  evidence. It re-runs the task *k* times in isolation and returns PASS / KILL / INSUFFICIENT
  from a deterministic checker, with no LLM on the verdict path. PASS means "no falsification
  found," not proof of correctness.

## 10. Demo GIF script

1. **Agent claim.** Terminal shows the coding agent finish, green and confident:
   `agent ▸ "✓ done — all tests pass"`.
2. **Evidence check.** Probity runs the deterministic checker against the repo:
   `checker ▸ pytest FAIL` · `tests/ ▸ tampered` · `scope ▸ narrowed`.
3. **KILL verdict.** The banner stamps `KILL [AUDIT_INTEGRITY]` — claim ≠ evidence.
4. **Reviewer sees the evidence bundle.** The report panel shows verdict + reason + claim-vs-
   evidence + modified files + integrity flags + repro command — every line re-checkable.

(Caption: *A single green isn't evidence. Probity asks for the evidence.*)

## 11. Forbidden marketing claims (never use)

Do **not** use any of these in Probity marketing — they overclaim past the evidence or disparage
prior art:

- "first" / "the first to…"
- "unique" / "the only tool"
- "only" used as a uniqueness claim
- "nobody does this" / "no one else…"
- "proves correctness"
- "proves agents do not lie"
- "guarantees safe code"
- "detects all deception"
- "Wilson-powered" as a novelty claim
- "better than AgentAssay" (or "beats" any named prior art)
- "AGI-grade" (or any AGI framing)
- "kills hallucinations" / "eliminates hallucinations"

**Why:** Probity's claims must stay inside its evidence. Prior art (AgentAssay, AgentLiar,
EvalView) is acknowledged, not disparaged; repeated trials / Wilson intervals / three-valued
verdicts are common infrastructure, not our novelty. PASS reports "no falsification found,"
never proof of correctness.
