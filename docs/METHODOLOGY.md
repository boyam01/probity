# Probity methodology

Probity is a method for testing whether an AI coding agent's success claim is
supported by evidence. The target failure is **false green**: the workflow looks
green, but the evidence does not justify trusting the result.

## The problem

Agent evaluation often starts from a fragile signal:

```text
The agent finished once -> the task is done -> ship it
```

That signal collapses several different facts into one story:

- whether the final state passed the checker;
- whether the agent honestly described that final state;
- whether the agent edited the test oracle;
- whether the result repeats across independent runs;
- whether the environment was healthy.

Probity separates those facts.

## Method

```text
registered task
  -> fresh isolated worktree per run
  -> deterministic checker
  -> claim/evidence comparison
  -> integrity flags
  -> repeated-trial statistics
  -> PASS / KILL / INSUFFICIENT
```

The method has six parts.

### 1. Register the task before the run

A task defines:

- the workspace;
- the agent command;
- allowed files;
- protected files;
- critical rules;
- the deterministic checker;
- the reliability claim `r`;
- the number of trials `k`.

This prevents the evaluation from moving the target after seeing the output.

### 2. Keep the checker deterministic

The built-in verdict path is:

```text
checker -> stats -> verdict
```

It contains no LLM call, no LLM judge, and no LLM-written failure summary.

Custom script checkers are allowed, but they are trust inputs owned by the task
author. Probity can record their output; it cannot prove that an arbitrary
custom checker is semantically correct.

### 3. Separate claim from evidence

The agent's final self-report is parsed separately from the checker's result.

```text
agent:   CLAIM: success
checker: failed
result:  false_claim
```

This matters because a failed run that claims success can still fool a human
single-run workflow.

### 4. Treat oracle tampering as an integrity failure

If the agent edits protected tests or other protected oracle files, the run is
not treated as evidence of capability. It is an audit-integrity failure.

### 5. Repeat under fresh isolation

Each run starts from a fresh git worktree. One lucky run is not enough evidence.
Repeated runs expose flakiness, degradation, partial fixes, and rare destructive
actions.

### 6. Prefer honest refusal over overclaiming

Probity uses a confidence interval over repeated trials. Small `k` can refute a
high-reliability claim, but it usually cannot confirm one.

That is why `INSUFFICIENT` is a first-class outcome, not an error.

## What the method improves

| Evaluation weakness | Improvement |
|---|---|
| Single-run optimism | Repeated trials |
| Self-reported completion | Claim/evidence separation |
| Test oracle mutation | Protected-path audit |
| Hidden scope changes | Allowed-path audit |
| Overconfident small samples | Wilson interval + INSUFFICIENT |
| Judge hallucination | Zero-LLM built-in verdict path |
| Hard-to-review reports | Evidence bundle and repro command |

## Limits

Probity does not:

- prove correctness;
- prove that an agent never makes false claims;
- detect all hallucinations;
- rank models;
- replace a human security review;
- validate open-ended work without a deterministic checker;
- make a bad checker good.

## Best current framing

Use:

```text
Agent reliability methodology for false-green testing of AI coding agents.
```

Avoid:

```text
The only agent evaluation tool.
Proves agents are correct.
Detects all hallucinations.
Guarantees safe code.
```
