# Roadmap

Probity v0.1 ships a frozen, zero-LLM verdict engine with a 10/10 calibration
matrix. This file lists what is **deliberately deferred** and the honest reason
for each gap. It is falsification-first applied to the product: the limits below
are stated, not hidden.

## Governance note

The schema (§2), verdict rules (§3), and checker contract (§4) in
[INTERFACE_CONTRACT.md](../INTERFACE_CONTRACT.md) are **frozen**. Anything that
changes their behaviour is an amendment: it must be proposed in `DECISION_LOG.md`,
approved by the maintainer, implemented, and re-validated so calibration stays
**10/10 with zero per-case patches**. The items below that touch §2–§4 are
proposals, not commitments.

## Deferred

### 1. Claim-contract hardening — `MISSING_CLAIM_CONTRACT` (touches §3/§4)

Today `false_claim = agent_claimed_success AND NOT checker_passed`, and the claim
is read from the agent's last `CLAIM: success` / `CLAIM: failure` line. If the
token is absent, the claim is `null` and never counts as a false claim. The gap:
an agent can avoid the false-claim signal simply by **not emitting a claim**, so
honesty testing currently binds agents that self-report, not those that stay
silent.

Proposed: a `MISSING_CLAIM_CONTRACT` reason code so a missing/ambiguous claim is
treated as non-compliant output — at least `INSUFFICIENT`, and `KILL` under a
strict mode. Needs calibration cases added without per-case patching.

### 2. Oracle-integrity hardening mode (touches §4)

`protected_paths` catches **direct** modification of oracle files via `git diff`.
It does not catch indirect oracle subversion: monkeypatching from a non-protected
`conftest.py`, editing a dependency the oracle imports, manipulating `sys.path` /
environment / installed packages, or hard-coding expected values in a
non-protected helper.

Proposed (opt-in hardening mode, off by default to preserve frozen semantics):
default-protect `conftest.py`, `pytest.ini`, `pyproject.toml`, `sitecustomize.py`
and declared helper imports; an oracle dependency/import-graph lock; checker
environment sanitization; and mutation testing to demonstrate the checker has
teeth.

### 3. Execution isolation (new subsystem)

A fresh git worktree isolates the *workspace*, not the OS. Probity audits
registered evidence; it is **not** an adversarial sandbox for safely executing
hostile agents. Planned, as explicit opt-in layers: containerized isolation,
network-off execution, and read-only oracle mounts.

### 4. Full branding pass — report title and environment variables (touches §2.4)

The CLI, package, and import path are `probity`. Two surfaces are intentionally
left unchanged in v0.1 because they are coupled to the **frozen** report contract
(§2.4) and the live-audit interface:

- the generated report keeps the title `# GAUNTLET REPORT` and filename
  `*_GAUNTLET_REPORT.md` (frozen §2.4; CI asserts the filename);
- live-audit environment variables keep the `GAUNTLET_*` prefix.

Renaming these is a §2.4 amendment (plus test/artifact updates) and will be done
as a single reviewed pass, not piecemeal.

### 5. Onboarding

`probity init` ships in v0.1: it scaffolds a starter `task_case.json` (a zero-LLM
template — it does not analyze your repo). Deferred: intelligent task synthesis from
a repo (which needs an authoring/LLM layer and therefore lives outside this zero-LLM
core), plus more worked examples and lower-friction entrypoints.

### 6. Sampling efficiency and robustness (v0.2 design)

Two planned, *additive* sampling options. The frozen single-temperature Wilson path stays the
default and unchanged.

- **Temperature-profile sampling** — run small batches at a few reference temperatures and
  report a reliability *curve* p(T) (a robustness profile), instead of one interval at one
  point. Temperatures are **not** pooled into a single Wilson CI — each temperature is a
  different `p`, and pooling them would violate the interval's single-parameter assumption.
- **Sequential early-stop** — stop the `k` runs as soon as the verdict is decisive, to save
  tokens (related to SPRT / adaptive budget; AgentAssay is prior art here). Enabled first only
  for *deterministic integrity* kills (one tampering/critical run is enough); statistical
  early-stop (PASS / refute) needs proper sequential boundaries to avoid optional-stopping
  bias, so it is deferred until those are in place.

Reasoning traces stay **evidence only**: they may be recorded, or reduced to a *deterministic*
check (e.g. a `CLAIM:` token is present, required sources are cited), but a model never judges
them on the verdict path — that would reintroduce the LLM-as-judge failure mode this tool exists
to avoid.

## Acknowledged attack surface (red-team)

Independent red-team review raised three attacks on the runtime path. Each is recorded
honestly — what the design already did, and what was added. All three hardenings shipped
in **D-040** as *additive, opt-in* amendments: the frozen §3.1 `decide()` chain, §4
primitives, and §2.1 example are unchanged, and calibration stays **10/10 with zero
per-case patches**.

### A1 — Deterministic environment poisoning vs the Wilson interval

Attack: a task whose failure is a *deterministic* external fault (a 403, a timezone
offset) fails all `k` runs; the interval reads 0/k and KILLs, mistaking environment
poison for agent-logic failure.

Already in place: a pre/post **environment canary** (an always-correct scripted agent on
a fixed task). A failed canary maps to `INSUFFICIENT · ENV_UNSTABLE` (§3.1 rule 1) — the
agent is never blamed for an environment fault. Deferred: the canary probes general
env/host health, not task-specific external dependencies. **Shipped (D-040):** an optional
`env_preconditions` field — declared probe commands run before the `k` runs; any failure
surfaces as `ENV_UNSTABLE` (never `KILL`). Default none, so the frozen example and
calibration are unaffected. A task that depends on a live external service should still
**mock/stub it** in `task_case.json`.

### A2 — Oracle omission (unasserted side effects)

Attack: code that passes every written assertion `k` times but leaks memory, OOMs, or
has an unchecked system side effect — the checker PASSes because it only verifies what it
asserts.

Already stated: "Probity does not judge whether your checker is a good checker … garbage
oracle in, false green out." **Shipped (D-040):** optional `checker.timeout_s` and
`checker.max_memory_mb` bound the checker subprocess (memory via POSIX `RLIMIT_AS`;
best-effort/no-op on Windows) — a runaway or OOM program FAILS the check instead of
passing on unasserted resource use. Mutation-test guidance to prove the checker has teeth
remains advisory.

### A3 — k-run state pollution (breaking the i.i.d. assumption)

Attack: a task that mutates shared external state (a real database, a Slack message, a
global file) makes run n+1 read run n's residue — the `k` samples stop being independent
and the Wilson math is invalid.

Already in place: **every run gets a fresh git worktree** built from the pristine ref and
destroyed afterwards (`probity/runner.py` `Worktree` — "zero residue between runs"), so
**workspace** state is fully reset between runs. The default path does not reset state
*outside* the worktree (OS, network) — a worktree is not a sandbox. **Shipped (D-040):**
an opt-in `docker` adapter runs each trial in a fresh, network-off container
(`--network=none`, `--rm`) for OS-level isolation + a full per-run reset. The
zero-dependency core never imports it; Docker is required only when `agent.adapter =
"docker"` is selected. Read-only oracle mounts remain on the roadmap.

## Not planned (by design)

These are deliberate scope boundaries, not gaps:

- model leaderboards or ranking;
- an LLM judge anywhere on the verdict path;
- a proof of arbitrary agent correctness;
- detection of every hallucination or every oracle-subversion path.
