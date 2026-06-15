# PROJECT_STATE.md

## Spec hash（verdict 引擎啟動時驗證；不符 → 拒跑並回報 SPEC_DRIFT）

```
spec_hash: sha256:e75146ad01bee1564b8e0e59893ddbc1d80a1cc8ed29758b76c6cf1e174cf75a
calibration_hash: sha256:2f2d41d053e392aa53f676be4066b30b24f797d065d4bad3f738535678ed4d20
```

- 計算方式：`EVAL_SPEC.md` 位元組內容，換行正規化（`\r\n` / `\r` → `\n`）後的 sha256。
- 正規化理由：跨平台 clone（autocrlf）不得造成假性 SPEC_DRIFT。
- `calibration_hash`（D-038 / finding #2）：`tasks/calibration_v1/*.json`(10 校準案例 + expected.json)
  名稱分隔 + 換行正規化後的 sha256。`gauntlet calibrate` 啟動時驗證；不符 → 拒跑 `CALIBRATION_DRIFT`。
  目的:防止有人默默弱化某個校準案例(同時改 cal_X.json 與 expected.json)而不被偵測。與 spec_hash
  分離,故已發佈報告內嵌的 spec_hash provenance 不受影響。
- **Provenance policy（owner-controlled）**：`calibration_hash`、校準 fixtures、以及 `spec_hash` 都是
  **Owner 掌控的 provenance**。更改其中任一者(fixtures 或記錄的 hash)屬 **Owner amendment**——agent
  **不得**靠「同時改 fixtures 與記錄的 hash」自我授權繞過此 gate。此 gate 偵測的是漂移(drift),授權
  本身仍在 Owner;偵測通過不等於批准。

## Phase 進度

| Phase | 狀態 | 測試 |
|---|---|---|
| 0 — Governance & Skeleton | ✅ 完成 | 14 passed |
| 1 — Stats | ✅ 完成 | 35 passed（累計） |
| 2 — Runner & Checker | ✅ 完成 | 75 passed（累計） |
| 3 — Verdict & Calibration | ✅ 完成 | 106 passed（累計，173s）；校準 10/10，FP=0 FN=0 |
| 4 — Report & Demo | ✅ 完成 | **118 passed（v0.1 Phase 4 最終，212s）**；demo 重現 §10 KILL 報告 |

> **當前完整套件：177 passed**（2026-06-15 實跑 `py -3.13 -m pytest -q`，exit 0；含 10/10 校準與 3 個 flip-probe）。下表各階段與 live-audit 的 118 / 161 為當時里程碑快照，非當前數。

## LIVE_AUDIT_SPEC v0.1 進度（第二份委託書）

| 項目 | 狀態 |
|---|---|
| §0 Rider：3 個 verdict-flip 迴歸測試 | ✅ 本機綠（in-memory mutation，磁碟凍結檔有 byte-identity guard） |
| §0 Rider：CI（pytest / calibrate / demo 三 job）+ badge | ✅ 檔案就緒（`.github/workflows/ci.yml`）；**等 Owner `gh auth login` / 建立 GitHub repo 後 push 即綠** |
| §2.1 agent（stdlib-only、單輪） | ✅ v0.2 統一為 `agents/llm_patch_agent.py`（`--provider openai/anthropic`） |
| §2.3 dry-run（罐頭 transport、CI 安全網） | ✅ 兩 provider 端到端綠 |
| §3 driver `scripts/run_live_session.py`（紀律機械化） | ✅ pre-registration + task-hash 綁定 + provider-aware |
| Secret scan（DoD #4）+ secret canary | ✅ fresh-clone 惡意外洩 test + 假 key dry-run → grep 全空；git 歷史 CLEAN |
| 跨引擎對抗式安全審查 + 加固 | ✅ Codex + Claude 雙審；9 真實漏洞全修（D-025） |
| **v0.2 雙 provider wrapper（§A2）** | ✅ parity 凍結（transport 外逐位元相同）；usage 正規化 `{in,out}` |
| **v0.2 §A4 出版規則** | ✅ driver build_live_header（單一 agent 措辭 + not-a-comparison，零 LLM） |
| **v0.2 §A3 secret 擴充** | ✅ ANTHROPIC_* scrub + sk-ant scan；anthropic dry-run secret 測試 |
| Owner 親手 sk-ant canary（§A3.4） | ⏸ 等 Owner（Claude API/CLI 場前硬 gate） |
| API session（openai/anthropic，每場 §9.3 停下） | ⏸ 等 Owner：金鑰環境 / 官網單價 / commit manifest |
| **subagent transport（D-032）+ 第一場 live 發佈** | ✅ `reports/live/2026-06-11-fable-5/`：Fable 5 10/10 → INSUFFICIENT、k_needed=35（誠實標 subagent transport, NOT API audit） |
| CLI SUT（Codex/Claude CLI） | ⏸ parked：claude -p 401（需 token）、codex 非互動卡住（需修調用） |
| 測試 | **161 passed（live-audit 當時，326s）；校準 10/10**（當前完整套件 177，見上） |

task 檔換行正規化 sha256：openai `5b646f11b676bd6a336ccb1efdc0520c20941f1555bdb8be2020491ec82ddd7e`；
anthropic `3e563db1c2124e34c68e3ef3ece26b949e4efcfe7b3a162dc53cc8d40c30e7a4`。

## v0.1 交付狀態：全部 Phase 完成

- 校準矩陣：**10/10 expected == actual，FP=0，FN=0，零 per-case 補丁**（`make calibrate` 重現）。
- Demo：`demo-once`（seed=1 單次成功 →「✓ ship it」）；`demo`（10 runs → KILL
  [RELIABILITY_REFUTED]，matrix `▮▮▯▮▮▯▮▯▮▮`，run 6 critical scope violation）。
- 預錄 traces：`demo/patchbot/traces/`（10 條，committed）；測試逐位元比對重跑結果。
- 零 API key、零 LLM、零第三方 runtime 依賴（pytest 僅 dev）。
- optional `--live` adapter 雛形未實作（§6 明示不計入驗收；subprocess adapter 已可
  銜接任意 CLI agent）。

## 環境

- 開發直譯器：Python 3.13（`py -3.13`），pytest 9.0.3。
- Repo root：`D:\GAUNTLET_ruler`（= 規格中的 `agent-gauntlet/`，見 DECISION_LOG D-001）。
- 測試指令：`py -3.13 -m pytest -q`。

## 已交付

- Governance：CLAUDE.md / INTERFACE_CONTRACT.md / EVAL_SPEC.md（已定稿，hash 如上）/
  DECISION_LOG.md / REFERENCES.md / README.md（完整版）/ Makefile / pyproject.toml。
- `gauntlet/`：types / stats / checker / runner / verdict / cluster / report / cli +
  adapters（scripted、subprocess）。
- `tasks/calibration_v1/`：10 案例 + fixtures（minirepo、abstract_ws）+ expected.json。
- `demo/patchbot/`：minirepo + task json + 10 條預錄 traces。
- `tests/`：118 個測試（types round-trip、§3.3 數值 ground truth、checker primitives、
  worktree 隔離、verdict 優先序、校準矩陣端到端、demo 重現性）。
