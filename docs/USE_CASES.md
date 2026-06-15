# Use cases

Probity is for evidence-gated agent workflows. It is strongest when the task has
a deterministic checker and the agent is allowed to edit a bounded part of a
repo.

## Good fits

| Use case | Why Probity helps |
|---|---|
| Coding-agent CI | Replays the same task and blocks unsupported greens before merge. |
| PR patch bots | Separates "I fixed it" from what the tests and git diff show. |
| Refactor / migration agents | Catches partial fixes, scope narrowing, and flaky success. |
| Test-repair agents | Protects tests so "green" cannot come from weakening the oracle. |
| Security-sensitive repo edits | Critical rules catch deletion or modification of guarded paths. |
| Data/config agents | Script checkers can validate generated config, schema, or fixtures. |
| Evidence research tasks | Custom checkers can require source IDs, citations, and balanced evidence. |

## Weaker fits

| Use case | Why it is weaker |
|---|---|
| Open-ended factual Q&A | There may be no deterministic checker. |
| Design taste / copywriting | The final judgment is subjective unless you create a separate oracle. |
| Model leaderboards | Probity audits one agent against one registered claim, not cross-model rank. |
| Cheap one-off experiments | Running *k* trials is intentionally stricter than one-shot demos. |
| Workflows requiring an LLM judge | The built-in verdict path intentionally avoids LLM judgment. |

## Suggested starting patterns

### Existing test suite

Use `checker.type = "pytest"` and protect `tests/**`.

This is the simplest path for coding-agent tasks.

### Custom deterministic checker

Use `checker.type = "script"` when the right oracle is not pytest:

- `cargo test`;
- schema validation;
- golden-file comparison;
- source/citation validation;
- build/lint/type-check pipeline.

The custom checker is a trust input. Probity records and type-checks the result,
but a human still owns the checker semantics.

### State-file check

Use `checker.type = "state_file"` for tiny calibration tasks or minimal demos.

### Hidden holdout

Use a sidecar checker when you want public tests for the agent loop and hidden
tests for the final audit. This is experimental today; see
`tasks/experimental_hidden_holdout/`.

## Operating posture

Probity is conservative by design:

- a single green does not prove reliability;
- PASS means no falsification was found, not correctness;
- KILL means the evidence was strong enough to refuse;
- INSUFFICIENT is an honest answer when the battery is underpowered.
