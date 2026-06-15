# References

> 注意：本清單由 LLM 整理，arXiv 編號可能有誤。
> 任何條目在公開 README 引用前，必須由 Owner 逐一以 arXiv 頁面驗證。

## v0.1 設計支柱
- τ-bench (arXiv:2406.12045) — pass^k 概念來源；單次成功與重複一致性的落差實證
- WebArena Verified (OpenReview) — benchmark/checker 本身會錯 → 本專案校準層（Level 1）的存在理由
- Evaluating Scoring Bias in LLM-as-a-Judge (arXiv:2506.22316) — verdict path 零 LLM 條款的依據之一
- Are We on the Right Way to Assessing LLM-as-a-Judge? (arXiv:2512.16041) — 同上
- Evaluation-Driven Development and Operations of LLM Agents (arXiv:2411.13768) — pre-deploy audit 的流程定位
- Rigorous Evaluation of Coding Agents on SWE-Bench (ACL 2025) — coding agent 評估嚴謹性 → checker contract 設計

## v2 路線圖（本版凍結）
- Saving SWE-Bench (arXiv:2510.08996) / SWE-Bench++ (arXiv:2512.17419) — benchmark mutation gate（方向 A）
- ToolSandbox (arXiv:2408.04682) / AgentBoard (arXiv:2401.13178) — state / milestone / progress gates
- BFCL — tool-call validity gates
- Judge consistency 系列 — judge-the-judge audit（方向 C）

## v3 路線圖
- Agent-SafetyBench (arXiv:2412.14470) / AgentHarm (arXiv:2410.09024) /
  AgentDojo (arXiv:2406.13352) / SkillSafetyBench (arXiv:2605.12015, 未驗證) — 安全與 injection gates

## 背景與 README 素材
- AgentBench (2308.03688)、OSWorld (2404.07972)、WebArena (2307.13854)、
  WorkArena (2403.07718)、TheAgentCompany (2412.14161)、SWE-bench Verified

## 文獻對照
- 尺子在 LLM 真實性 / 幻覺 / 欺騙文獻中的定位、刻意不做的範圍、以及相容的未來方向，
  見 `RESEARCH_ALIGNMENT.md`（meta-evaluation 與 deterministic-checker 的文獻支持、
  deception-under-pressure 作為 v2 候選）。
