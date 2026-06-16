# Is this PASS real, or theater? — judging a run

A Probity `PASS` is a narrow statement: *no falsification was found under the registered
battery.* It is **not** "the code is correct," and it can be **hollow** in specific,
checkable ways. The verdict line alone is not enough. This is the falsification-first
checklist for auditing a run — applied to Probity itself.

## Read these, not just the verdict

Open `<task>_audit.json` and look at, for every task:

1. `verdict` + `reason_codes`
2. `successes` / `k` and `wilson_95` (how far is the lower bound above your `r`?)
3. `diagnostics` — `DEGENERATE_VARIANCE`, `SYSTEMATIC_FAILURE`, `FALSE_CLAIM_PATTERN`
4. `integrity_summary` — `false_claim`, `scope_violation`, `test_tampering`
5. `env` — `canary_pre_ok`, `canary_post_ok`
6. the **distinct `trace_hash` count** across the k runs

## Failure mode 1 — the k trials were one trial, k times (the deadliest)

The Wilson interval is only valid for **independent** trials. If the agent is deterministic
(a scripted replay, temperature 0, or a task with no real variation), the k runs are
identical and the interval is meaningless — k=16 carries no more evidence than k=1.

- **Signal:** `diagnostics` contains `DEGENERATE_VARIANCE`, and/or the runs share **one**
  `trace_hash`.
- **Important:** this is a §3.5 *diagnostic*, it does **not** downgrade the verdict. Probity
  will return `PASS` on a deterministic `6/6` (Wilson `[0.6097, 1.0]`) **and** flag
  `DEGENERATE_VARIANCE` with `1` distinct hash. The teeth are in the diagnostic, not the
  banner — you must read it.
- **Verdict on the verdict:** if the traces don't vary, treat the result as k=1.

## Failure mode 2 — a toothless or self-authored oracle

A `PASS` means the agent's output satisfied **the registered checker** — nothing more. If the
same agent wrote the checker and the fixtures, "it passes its own tests" is not "it matches
the spec."

- **The single most powerful sharpness test:** mutation-test the oracle. Deliberately break
  the implementation in several ways and confirm Probity returns `KILL [RELIABILITY_REFUTED]`
  each time. If a knowingly-broken implementation still `PASS`es, the oracle has no teeth and
  every green from it is suspect.
- Check the checker tests invariants and boundaries, not just `output == expected` on the
  happy path.

## Failure mode 3 — oracle subversion without touching protected paths

`protected_paths` catches direct edits to oracle files. It does **not** catch indirect
subversion: a `conftest.py` monkeypatch, editing a non-protected dependency the oracle
imports, `sys.path`/env manipulation, or hard-coded expected values in a helper.

- **Check:** are `conftest.py`, `pytest.ini`, `pyproject.toml`, `sitecustomize.py`, and the
  oracle's helper imports inside `protected_paths`? Inspect `modified_files` for edits near
  the oracle. For OS-level isolation, run the trial under the opt-in `docker` adapter.

## Failure mode 4 — spec-interpretation collusion

If the implementer and the test author share the same wrong reading of an ambiguous clause,
the oracle and the code agree and you get a false green.

- **Check:** were the adversarial/boundary cases written by someone *other* than the
  implementer? Is every ambiguous clause pinned by an explicit test, or merely assumed?

## Failure mode 5 — razor-thin / optional-stopping PASS

- **Signal:** how far is `wilson_95[0]` above `r`? A `PASS` at the exact minimum k (lower
  bound barely over `r`) is fragile.
- **Check:** was `k` pre-registered? Escalating once from `k` to the reported `k_needed` is
  the intended flow; re-running at ever-larger k until it finally passes is optional stopping
  and inflates false greens.

## Failure mode 6 — environment masking

A deterministic external fault (a 403, a timezone offset) can fail all k runs and look like
agent failure.

- **Check:** are `canary_pre_ok` and `canary_post_ok` both true? Did the task declare
  `env_preconditions` and mock/stub external services? An env fault should read as
  `INSUFFICIENT [ENV_UNSTABLE]`, never `KILL`.

## Failure mode 7 — coverage illusion / scope creep

- **Check:** what requirements were **excluded** because they have no deterministic oracle
  (vague "high concurrency / financial-grade precision" clauses)? A `PASS` covers only the
  registered, checkable subset. Reading it as "the system works" is the scope error Probity
  is built to prevent — a good run states what it did *not* verify.

## The one-time sharpness test for any setup you rely on

Inject known-bad and confirm the ruler bites:

| Inject | Expect |
|---|---|
| a deterministic agent (same output every run) | `diagnostics: DEGENERATE_VARIANCE`, 1 distinct `trace_hash` |
| claims success but the checker fails | `integrity_summary.false_claim > 0` |
| edits a protected path | `KILL [AUDIT_INTEGRITY]` |
| a broken implementation | `KILL [RELIABILITY_REFUTED]` |

If any known-bad slips through as `PASS`, the ruler is dull **for your task** — fix the
oracle/fixtures before trusting a green.
