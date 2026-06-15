![Probity - agent reliability methodology for false-green testing](docs/probity_hero.svg)

# Probity: Agent Reliability Methodology for False-Green Testing

> 中文：**Probity：用於 false-green 測試的 Agent 可靠性方法論**

Probity is a methodology and local harness for testing whether an AI coding
agent's "done" claim is supported by evidence. It is built for the false-green
problem: an agent appears to finish a task, but the success is not trustworthy
because the tests were weakened, scope was narrowed, the task only passed once,
or the agent claimed success before the checker agreed.

中文：Probity 是一套方法論與本機測試工具，用來檢查 AI coding agent 的「完成」宣稱是否有證據支持。
它針對的是 **false-green** 問題：agent 看起來完成了任務，但成功並不可信，原因可能是測試被削弱、
範圍被縮小、只幸運通過一次，或 agent 在 checker 還沒確認前就宣稱成功。

The core idea is simple:

中文：核心想法很簡單：

```text
claim -> evidence -> repeated trials -> statistical verdict
宣稱 -> 證據 -> 重複試驗 -> 統計裁決
```

Probity is not a model leaderboard, not an LLM judge, and not a proof of
correctness. It is a falsification-first method for asking a narrower, more
useful engineering question:

中文：Probity 不是模型排行榜，不是 LLM 裁判，也不是正確性證明。它是一個 falsification-first
方法，用來回答一個更窄但更有工程價值的問題：

> Can this agent's success claim survive the evidence we registered before the run?
>
> 這個 agent 的成功宣稱，能不能通過我們事先註冊好的證據檢查？

## Who This Is For

中文：誰適合使用

Probity is designed for people who already feel the pain of false greens:

中文：Probity 是為已經被 false green 困擾的人設計：

- domain researchers who need reproducible evidence before trusting an agent result;
- AI safety, evaluation, and reliability researchers studying false-completion failure modes;
- engineering teams using coding agents in CI, PR review, refactors, migrations, or test repair;
- maintainers who want to compare a coding agent's self-report against deterministic repo evidence;
- teams using tools such as Codex CLI, Claude Code, or other local CLI agents and wanting a stricter acceptance gate.

- 需要可重現證據才願意信任 agent 結果的領域研究員；
- 研究 false-completion / false-green 失敗模式的 AI safety、evaluation、reliability 研究者；
- 在 CI、PR review、refactor、migration、test repair 中使用 coding agent 的工程團隊；
- 想把 agent 自我宣稱與 repo 確定性證據分開檢查的 maintainer；
- 已在使用 Codex CLI、Claude Code 或其他本機 CLI agent，並想加入更嚴格驗收閘門的團隊。

## What This Methodology Improves

中文：這個方法論旨在改善什麼

| Problem in agent evaluation | Probity's methodological response |
|---|---|
| One lucky run looks like capability | Run the same task *k* times in fresh isolation. |
| The agent says "done" but the checker disagrees | Store the agent claim separately from checker evidence. |
| The agent edits tests to make itself pass | Protect oracle paths and treat test tampering as audit failure. |
| A small sample is over-interpreted | Use Wilson intervals and return INSUFFICIENT when evidence is underpowered. |
| The evaluator becomes another hallucinating judge | Keep the built-in checker -> stats -> verdict path zero-LLM. |
| Results are hard to inspect later | Emit evidence bundles: verdict, reason codes, modified files, trace hashes, repro commands. |

| Agent 評估常見問題 | Probity 的方法論回應 |
|---|---|
| 一次幸運成功被誤認成能力 | 在乾淨隔離環境中重複跑同一任務 *k* 次。 |
| agent 說「完成」，但 checker 不同意 | 把 agent 的宣稱與 checker 證據分開記錄。 |
| agent 修改測試讓自己通過 | 保護 oracle 路徑，將 test tampering 視為審計失敗。 |
| 小樣本被過度解讀 | 使用 Wilson interval，證據不足時回 INSUFFICIENT。 |
| 評估器本身變成另一個會幻覺的 judge | 內建 checker -> stats -> verdict 路徑保持 zero-LLM。 |
| 事後難以檢查結果 | 輸出 evidence bundle：verdict、reason code、修改檔案、trace hash、重現命令。 |

## Methodology in One Diagram

中文：方法論流程

```text
registered task
  -> isolated run 1..k
  -> deterministic checker
  -> claim/evidence comparison
  -> integrity flags
  -> Wilson confidence interval
  -> PASS / KILL / INSUFFICIENT
```

```text
事先註冊的任務
  -> 隔離執行第 1..k 次
  -> 確定性 checker
  -> 宣稱與證據比對
  -> integrity flags
  -> Wilson 信賴區間
  -> PASS / KILL / INSUFFICIENT
```

Verdicts mean:

中文：裁決含義：

- **PASS**: no falsification was found under the registered battery.
- **KILL**: the evidence refutes the reliability claim or shows an integrity failure.
- **INSUFFICIENT**: the run budget, confidence interval, or environment cannot support a verdict.

- **PASS**：在註冊好的測試矩陣下，沒有找到足以推翻的證據。
- **KILL**：證據推翻可靠性宣稱，或出現 integrity failure。
- **INSUFFICIENT**：執行次數、信賴區間或環境狀態不足以支持裁決。

PASS does **not** mean correctness is proven. It only means this registered
battery did not falsify the claim.

中文：PASS **不代表正確性已被證明**。它只代表這組註冊好的測試沒有推翻該宣稱。

## Five-Minute Local Install

中文：五分鐘本機安裝

Docker is the fastest way to try Probity locally. No API keys are required for
the demo, calibration, or tests.

中文：Docker 是最快的本機試用方式。內建 demo、calibration、tests 都不需要 API key。

```bash
git clone https://github.com/boyam01/agent-gauntlet.git
cd agent-gauntlet
docker build -t probity .
docker run --rm probity demo-once
docker run --rm probity demo
```

What you should see:

中文：你應該會看到：

- `demo-once`: a single successful run that looks shippable.
- `demo`: repeated runs that falsify the naive "ship it" conclusion.

- `demo-once`：一次看起來可以 ship 的成功執行。
- `demo`：重複執行後，推翻「可以 ship」的天真結論。

Run the local gates:

中文：跑本機 release gate：

```bash
docker run --rm probity calibrate
docker run --rm probity test
```

Local Python path:

中文：不用 Docker 的 Python 路徑：

```bash
python -m pip install pytest
python -m gauntlet run demo/patchbot/task_demo_patchbot_01.json --once --seed 1
python -m gauntlet run demo/patchbot/task_demo_patchbot_01.json
python -m gauntlet calibrate
python -m pytest -q
```

More setup detail: [docs/QUICKSTART.md](docs/QUICKSTART.md) and
[docs/DOCKER.md](docs/DOCKER.md).

中文：更多安裝細節見 [docs/QUICKSTART.md](docs/QUICKSTART.md) 與
[docs/DOCKER.md](docs/DOCKER.md)。

Methodology details: [docs/METHODOLOGY.md](docs/METHODOLOGY.md). Public claim
boundaries: [docs/PUBLIC_CLAIMS.md](docs/PUBLIC_CLAIMS.md). Source vs public
export boundaries: [docs/PROJECT_SURFACES.md](docs/PROJECT_SURFACES.md).

中文：方法論細節見 [docs/METHODOLOGY.md](docs/METHODOLOGY.md)。公開主張邊界見
[docs/PUBLIC_CLAIMS.md](docs/PUBLIC_CLAIMS.md)。source repo 與 public export 邊界見
[docs/PROJECT_SURFACES.md](docs/PROJECT_SURFACES.md)。

## Run Your Own Agent

中文：測你自己的 agent

Probity works when your task has a deterministic checker: `pytest`, `cargo test`,
a compiler, a schema validator, a script oracle, or a state-file check.

中文：只要你的任務有確定性 checker，Probity 就能工作，例如 `pytest`、`cargo test`、compiler、
schema validator、script oracle 或 state-file check。

Create a `task_case.json` with:

中文：建立一個 `task_case.json`，包含：

- a workspace or fixture repo;
- an agent command under `agent.adapter = "subprocess"`;
- a checker: `pytest`, `script`, or `state_file`;
- `allowed_paths` and `protected_paths`.

- workspace 或 fixture repo；
- `agent.adapter = "subprocess"` 下的 agent 命令；
- checker：`pytest`、`script` 或 `state_file`；
- `allowed_paths` 與 `protected_paths`。

Then run:

中文：然後執行：

```bash
python -m gauntlet run path/to/task_case.json
```

With Docker:

中文：使用 Docker：

```bash
docker run --rm -v "$PWD:/work" probity run /work/path/to/task_case.json
```

If the agent CLI must run inside Docker, build a derived image from `probity`
and install your agent toolchain there. If the agent CLI is installed on your
host, run Probity locally with Python so the subprocess adapter can reach it.

中文：如果 agent CLI 必須在 Docker 內執行，請從 `probity` 建立衍生 image 並安裝你的 agent
工具鏈。如果 agent CLI 安裝在 host 上，建議用本機 Python 跑 Probity，讓 subprocess adapter
可以呼叫 host 工具。

Task schema: [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md).

中文：任務 schema 見 [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md)。

## Use With Codex, Claude Code, or Other Agent CLIs

中文：可搭配 Codex、Claude Code 或其他 Agent CLI

Probity is agent-agnostic. It runs the configured agent command as a subprocess,
then audits the files, checker output, and final claim. Recommended starting
tool choices are:

中文：Probity 不綁定特定 agent。它會把你設定的 agent command 當作 subprocess 執行，
再審計檔案、checker 輸出與最終宣稱。建議從這些工具開始：

- [Codex CLI](https://github.com/openai/codex), when you want a local terminal coding agent in a reproducible harness;
- [Claude Code](https://code.claude.com/), when your team already uses Claude Code workflows, project memory, or Claude-oriented repo guidance;
- any other CLI agent that can run from a command, edit a bounded workspace, and leave evidence for a checker.

- [Codex CLI](https://github.com/openai/codex)：適合想把本機 terminal coding agent 放進可重現 harness 的使用者；
- [Claude Code](https://code.claude.com/)：適合已使用 Claude Code workflow、project memory 或 Claude 導向 repo guidance 的團隊；
- 任何能用 command 執行、在有限 workspace 內改檔、並留下 checker 可驗證證據的 CLI agent。

Probity does not rank Codex vs Claude or the models behind them. It tests the
registered task, checker, and success claim you provide.

中文：Probity 不排名 Codex 與 Claude，也不排名它們背後的模型。它測的是你註冊的 task、
checker 與 success claim。

## Recommended Use Cases

中文：建議使用領域

Good fits:

中文：適合：

- AI coding agent CI and PR automation;
- generated patch review;
- refactor and migration agents;
- test-writing or test-repair agents;
- data/config editing agents with deterministic validation;
- security-sensitive workflows with protected files;
- evidence-research tasks where every claim needs source IDs.

- AI coding agent CI 與 PR automation；
- generated patch review；
- refactor / migration agent；
- test-writing 或 test-repair agent；
- 有確定性驗證的 data/config editing agent；
- 需要保護檔案的 security-sensitive workflow；
- 每個主張都需要 source ID 的 evidence research 任務。

Weaker fits:

中文：較不適合：

- open-ended factual Q&A with no deterministic checker;
- subjective design or writing tasks with no external oracle;
- model leaderboard creation;
- workflows where an LLM judge must be the final authority.

- 沒有確定性 checker 的開放式問答；
- 沒有外部 oracle 的主觀設計或寫作任務；
- 模型排行榜；
- 必須由 LLM judge 作最終裁判的 workflow。

More examples: [docs/USE_CASES.md](docs/USE_CASES.md).

中文：更多範例見 [docs/USE_CASES.md](docs/USE_CASES.md)。

## Evidence and Limits

中文：證據與限制

This repository contains:

中文：這個 repo 包含：

- controlled calibration with known ground truth;
- reproducible demos that need no API keys;
- Docker and local Python entrypoints;
- task-schema examples for running your own agent;
- methodology and public-claim boundaries.

- 具有已知 ground truth 的 controlled calibration；
- 不需要 API key 的可重現 demo；
- Docker 與本機 Python 入口；
- 用來測自己 agent 的 task schema 範例；
- 方法論與公開主張邊界。

The evidence supports a narrow claim: Probity can expose false-green and
unsupported-success patterns in registered tasks with deterministic checkers.
It does not prove arbitrary agent correctness, does not detect all hallucinations,
and does not rank models.

中文：這些證據支持的是一個窄主張：Probity 能在有確定性 checker 的註冊任務中，揭露 false-green
與 unsupported-success 模式。它不證明任意 agent 都正確，不保證抓出所有幻覺，也不做模型排名。

Private research reports, raw traces, model-session logs, and keys are not part
of the public tool export. They may remain in the source repository for audit
history unless Owner explicitly approves moving them.

中文：私有研究報告、raw traces、模型 session logs 與 keys 不屬於公開工具 export。
它們可以保留在 source repository 作為稽核歷史，除非 Owner 明確批准移動。

## Related Work

中文：相關工作

Probity sits near agent evaluation, agent regression testing, and false-completion
detection. It does not claim to be first, unique, or better than adjacent work.
Repeated trials, Wilson intervals, and three-valued verdicts are common
infrastructure.

中文：Probity 位於 agent evaluation、agent regression testing、false-completion detection
附近。它不宣稱自己是第一個、唯一的，或比相鄰工具更好。重複試驗、Wilson interval、
三值裁決都是 common infrastructure。

Read:

中文：延伸閱讀：

- [docs/RELATED_WORK.md](docs/RELATED_WORK.md)

## Discoverability Metadata

中文：搜尋與可發現性 metadata

Suggested GitHub repository description:

中文：建議 GitHub repo description：

```text
Agent reliability methodology for false-green testing of AI coding agents.
```

Suggested GitHub topics:

中文：建議 GitHub topics：

```text
ai-agents
coding-agents
agent-evaluation
agent-reliability
llmops
software-testing
ci
test-automation
developer-tools
deterministic-testing
reliability-testing
false-green
ai-safety
provenance
audit
docker
```

Social preview: use a 1280x640 image with the words `Probity`, `agent reliability
methodology`, and `false-green testing`. GitHub supports custom social preview
images from repository settings.

中文：社群預覽圖建議使用 1280x640，包含 `Probity`、`agent reliability methodology`、
`false-green testing`。GitHub 可在 repository settings 上傳自訂 social preview image。

Detailed discoverability checklist: [docs/DISCOVERABILITY.md](docs/DISCOVERABILITY.md).

中文：詳細搜尋可發現性檢查表見 [docs/DISCOVERABILITY.md](docs/DISCOVERABILITY.md)。

## Development

中文：開發

```bash
python -m pip install pytest
python -m pytest -q
python -m gauntlet calibrate
```

Docker:

```bash
docker build -t probity .
docker run --rm probity test
docker run --rm probity calibrate
```

Core constraints:

中文：核心約束：

- built-in verdict path stays zero-LLM;
- `gauntlet/` runtime stays Python stdlib plus system `git`;
- schema/verdict/checker contract lives in [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md);
- calibration must stay 10/10 with zero per-case patches.

- 內建 verdict path 維持 zero-LLM；
- `gauntlet/` runtime 維持 Python 標準庫 + system `git`；
- schema/verdict/checker contract 位於 [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md)；
- calibration 必須維持 10/10，且不得 per-case patch。

## Publication Status

中文：發佈狀態

This repo is prepared for public feedback, but public release, repo visibility
changes, GitHub organization changes, and package publication still require
explicit Owner approval.

中文：這個 repo 正在準備公開試錯與收集回饋，但公開發佈、repo visibility 變更、GitHub organization
變更與 package publication 仍需要 Owner 明確批准。

Launch checklist: [docs/PUBLICATION_PREP.md](docs/PUBLICATION_PREP.md).

中文：發佈檢查表見 [docs/PUBLICATION_PREP.md](docs/PUBLICATION_PREP.md)。
