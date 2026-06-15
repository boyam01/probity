# Probity methodology

Probity is a method for testing whether an AI coding agent's success claim is
supported by evidence. The target failure is **false green**: the workflow looks
green, but the evidence does not justify trusting the result.

中文：Probity 是一套方法，用來測試 AI coding agent 的成功宣稱是否有證據支持。它針對的失敗模式是
**false green**：workflow 看起來變綠，但證據不足以讓人信任結果。

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

中文：常見 agent 評估會把「跑成功一次」誤當成「任務完成」。Probity 把 final state、agent 宣稱、
test oracle 是否被動過、結果是否可重複、環境是否健康分開看。

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

中文：任務要先註冊，包含 workspace、agent 命令、可改檔案、受保護檔案、critical rules、checker、
可靠性宣稱與 trial 次數。這避免看到結果後才移動標準。

### 2. Keep the checker deterministic

The built-in verdict path is:

```text
checker -> stats -> verdict
```

It contains no LLM call, no LLM judge, and no LLM-written failure summary.

Custom script checkers are allowed, but they are trust inputs owned by the task
author. Probity can record their output; it cannot prove that an arbitrary
custom checker is semantically correct.

中文：內建 verdict path 不呼叫 LLM。自訂 script checker 可以使用，但它是任務作者持有的信任輸入；
Probity 能記錄輸出，但不能自動證明任意 checker 的語意正確。

### 3. Separate claim from evidence

The agent's final self-report is parsed separately from the checker's result.

```text
agent:   CLAIM: success
checker: failed
result:  false_claim
```

This matters because a failed run that claims success can still fool a human
single-run workflow.

中文：agent 的自我宣稱和 checker 結果分開記錄。因為「失敗但宣稱成功」的 run 很容易騙過只看一次的人工流程。

### 4. Treat oracle tampering as an integrity failure

If the agent edits protected tests or other protected oracle files, the run is
not treated as evidence of capability. It is an audit-integrity failure.

中文：如果 agent 修改受保護測試或 oracle 檔案，這不是能力證據，而是審計完整性失敗。

### 5. Repeat under fresh isolation

Each run starts from a fresh git worktree. One lucky run is not enough evidence.
Repeated runs expose flakiness, degradation, partial fixes, and rare destructive
actions.

中文：每次 run 都從乾淨 worktree 開始。一次幸運成功不是足夠證據；重複執行可以揭露不穩定、退化、
局部修補與罕見破壞行為。

### 6. Prefer honest refusal over overclaiming

Probity uses a confidence interval over repeated trials. Small `k` can refute a
high-reliability claim, but it usually cannot confirm one.

That is why `INSUFFICIENT` is a first-class outcome, not an error.

中文：Probity 用重複 trial 的信賴區間做裁決。小 `k` 可以推翻高可靠性宣稱，但通常不能確認它。
因此 `INSUFFICIENT` 是正常裁決，不是錯誤。

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

中文：它改善的是單次成功過度樂觀、自我宣稱完成、測試 oracle 被修改、範圍被偷偷改小、小樣本過度自信、
LLM judge 可能幻覺，以及報告難以事後檢查這些問題。

## Limits

Probity does not:

- prove correctness;
- prove that an agent never makes false claims;
- detect all hallucinations;
- rank models;
- replace a human security review;
- validate open-ended work without a deterministic checker;
- make a bad checker good.

中文：Probity 不證明正確性，不證明 agent 永不錯誤，不抓所有幻覺，不做模型排名，不取代人工安全審查，
也不能讓壞 checker 變好。

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

中文：對外最佳定位是「用於 AI coding agents false-green testing 的 agent reliability methodology」。
不要宣稱唯一、證明正確、抓所有幻覺或保證安全。
