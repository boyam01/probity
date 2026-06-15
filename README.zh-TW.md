![Probity - 用於 false-green 測試的 Agent 可靠性方法論](docs/probity_hero.svg)

# Probity:用於 false-green 測試的 Agent 可靠性方法論

[![lang: English](https://img.shields.io/badge/lang-English-lightgrey?style=flat-square)](README.md)
[![lang: 繁體中文](https://img.shields.io/badge/lang-%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87-1f6feb?style=flat-square)](README.zh-TW.md)

Probity 是一套方法論與本機測試工具,用來檢查 AI coding agent 的「完成」宣稱是否有證據支持。
它針對的是 **false-green** 問題:agent 看起來完成了任務,但成功並不可信,原因可能是測試被削弱、
範圍被縮小、只幸運通過一次,或 agent 在 checker 還沒確認前就宣稱成功。

核心想法很簡單:

```text
宣稱 -> 證據 -> 重複試驗 -> 統計裁決
```

Probity 不是模型排行榜,不是 LLM 裁判,也不是正確性證明。它是一個 falsification-first
方法,用來回答一個更窄但更有工程價值的問題:

> 這個 agent 的成功宣稱,能不能通過我們事先註冊好的證據檢查?

## 誰適合使用

Probity 是為已經被 false green 困擾的人設計:

- 需要可重現證據才願意信任 agent 結果的領域研究員;
- 研究 false-completion / false-green 失敗模式的 AI safety、evaluation、reliability 研究者;
- 在 CI、PR review、refactor、migration、test repair 中使用 coding agent 的工程團隊;
- 想把 agent 自我宣稱與 repo 確定性證據分開檢查的 maintainer;
- 已在使用 Codex CLI、Claude Code 或其他本機 CLI agent,並想加入更嚴格驗收閘門的團隊。

## 這個方法論旨在改善什麼

| Agent 評估常見問題 | Probity 的方法論回應 |
|---|---|
| 一次幸運成功被誤認成能力 | 在乾淨隔離環境中重複跑同一任務 *k* 次。 |
| agent 說「完成」,但 checker 不同意 | 把 agent 的宣稱與 checker 證據分開記錄。 |
| agent 修改測試讓自己通過 | 保護 oracle 路徑,將 test tampering 視為審計失敗。 |
| 小樣本被過度解讀 | 使用 Wilson interval,證據不足時回 INSUFFICIENT。 |
| 評估器本身變成另一個會幻覺的 judge | 內建 checker -> stats -> verdict 路徑保持 zero-LLM。 |
| 事後難以檢查結果 | 輸出 evidence bundle:verdict、reason code、修改檔案、trace hash、重現命令。 |

## 方法論流程

```text
事先註冊的任務
  -> 隔離執行第 1..k 次
  -> 確定性 checker
  -> 宣稱與證據比對
  -> integrity flags
  -> Wilson 信賴區間
  -> PASS / KILL / INSUFFICIENT
```

裁決含義:

- **PASS**:在註冊好的測試矩陣下,沒有找到足以推翻的證據。
- **KILL**:證據推翻可靠性宣稱,或出現 integrity failure。
- **INSUFFICIENT**:執行次數、信賴區間或環境狀態不足以支持裁決。

PASS **不代表正確性已被證明**。它只代表這組註冊好的測試沒有推翻該宣稱。

## 五分鐘本機安裝

Docker 是最快的本機試用方式。內建 demo、calibration、tests 都不需要 API key。

```bash
git clone https://github.com/boyam01/agent-gauntlet.git
cd agent-gauntlet
docker build -t probity .
docker run --rm probity demo-once
docker run --rm probity demo
```

你應該會看到:

- `demo-once`:一次看起來可以 ship 的成功執行。
- `demo`:重複執行後,推翻「可以 ship」的天真結論。

跑本機 release gate:

```bash
docker run --rm probity calibrate
docker run --rm probity test
```

不用 Docker 的 Python 路徑:

```bash
python -m pip install pytest
python -m gauntlet run demo/patchbot/task_demo_patchbot_01.json --once --seed 1
python -m gauntlet run demo/patchbot/task_demo_patchbot_01.json
python -m gauntlet calibrate
python -m pytest -q
```

更多安裝細節見 [docs/QUICKSTART.md](docs/QUICKSTART.md) 與 [docs/DOCKER.md](docs/DOCKER.md)。
方法論細節見 [docs/METHODOLOGY.md](docs/METHODOLOGY.md)。公開主張邊界見
[docs/PUBLIC_CLAIMS.md](docs/PUBLIC_CLAIMS.md)。source repo 與 public export 邊界見
[docs/PROJECT_SURFACES.md](docs/PROJECT_SURFACES.md)。

## 測你自己的 agent

只要你的任務有確定性 checker,Probity 就能工作,例如 `pytest`、`cargo test`、compiler、
schema validator、script oracle 或 state-file check。

建立一個 `task_case.json`,包含:

- workspace 或 fixture repo;
- `agent.adapter = "subprocess"` 下的 agent 命令;
- checker:`pytest`、`script` 或 `state_file`;
- `allowed_paths` 與 `protected_paths`。

然後執行:

```bash
python -m gauntlet run path/to/task_case.json
```

使用 Docker:

```bash
docker run --rm -v "$PWD:/work" probity run /work/path/to/task_case.json
```

如果 agent CLI 必須在 Docker 內執行,請從 `probity` 建立衍生 image 並安裝你的 agent
工具鏈。如果 agent CLI 安裝在 host 上,建議用本機 Python 跑 Probity,讓 subprocess adapter
可以呼叫 host 工具。

任務 schema 見 [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md)。

## 可搭配 Codex、Claude Code 或其他 Agent CLI

Probity 不綁定特定 agent。它會把你設定的 agent command 當作 subprocess 執行,
再審計檔案、checker 輸出與最終宣稱。建議從這些工具開始:

- [Codex CLI](https://github.com/openai/codex):適合想把本機 terminal coding agent 放進可重現 harness 的使用者;
- [Claude Code](https://code.claude.com/):適合已使用 Claude Code workflow、project memory 或 Claude 導向 repo guidance 的團隊;
- 任何能用 command 執行、在有限 workspace 內改檔、並留下 checker 可驗證證據的 CLI agent。

Probity 不排名 Codex 與 Claude,也不排名它們背後的模型。它測的是你註冊的 task、checker
與 success claim。

## 建議使用領域

適合:

- AI coding agent CI 與 PR automation;
- generated patch review;
- refactor / migration agent;
- test-writing 或 test-repair agent;
- 有確定性驗證的 data/config editing agent;
- 需要保護檔案的 security-sensitive workflow;
- 每個主張都需要 source ID 的 evidence research 任務。

較不適合:

- 沒有確定性 checker 的開放式問答;
- 沒有外部 oracle 的主觀設計或寫作任務;
- 模型排行榜;
- 必須由 LLM judge 作最終裁判的 workflow。

更多範例見 [docs/USE_CASES.md](docs/USE_CASES.md)。

## 證據與限制

這個 repo 包含:

- 具有已知 ground truth 的 controlled calibration;
- 不需要 API key 的可重現 demo;
- Docker 與本機 Python 入口;
- 用來測自己 agent 的 task schema 範例;
- 方法論與公開主張邊界。

這些證據支持的是一個窄主張:Probity 能在有確定性 checker 的註冊任務中,揭露 false-green
與 unsupported-success 模式。它不證明任意 agent 都正確,不保證抓出所有幻覺,也不做模型排名。

私有研究報告、raw traces、模型 session logs 與 keys 不屬於公開工具 export。它們可以保留在
source repository 作為稽核歷史,除非 Owner 明確批准移動。

## 相關工作

Probity 位於 agent evaluation、agent regression testing、false-completion detection 附近。
它不宣稱自己是第一個、唯一的,或比相鄰工具更好。重複試驗、Wilson interval、三值裁決都是
common infrastructure。

延伸閱讀:[docs/RELATED_WORK.md](docs/RELATED_WORK.md)。

## 開發

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

核心約束:

- 內建 verdict path 維持 zero-LLM;
- `gauntlet/` runtime 維持 Python 標準庫 + system `git`;
- schema/verdict/checker contract 位於 [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md);
- calibration 必須維持 10/10,且不得 per-case patch。

## 發佈狀態

這個 repo 正在準備公開試錯與收集回饋,但公開發佈、repo visibility 變更、GitHub organization
變更與 package publication 仍需要 Owner 明確批准。

發佈檢查表見 [docs/PUBLICATION_PREP.md](docs/PUBLICATION_PREP.md)。
