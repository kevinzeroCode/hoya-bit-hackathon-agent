# 金牌規劃 — 從「能交差」到「能奪冠」

> **權威**:本文為執行路線圖,**與 `.kiro/specs`、`.kiro/steering` 或 `Implementation-Plan.md` 衝突時,以它們為準**。這裡只排序「差異化 + 完賽」的工作,不重新定義任何 gate。
> **更新**:2026-08-01。

## 0. 評分靈魂
主題是「**多源資訊的信任提煉**」。兩條評分軸(資料處理 / agent 運用)共用同一個靈魂:
> **在雜訊與矛盾中,證明「這個結論可信」,而且讓評審看得見。**

引擎(信任模型)已約 80 分;差距在「**把信任做成看得見的贏點**」+「**讓 agent 看起來真的在判斷**」。

## 1. 現況(誠實)
- **能交差 ≈ 70%**:Bronze 離線產品完成(S1/S2/S3/S5/S7 嚴格完成、S9/S9B 離線完成、598 tests 綠、ruff 乾淨)。
- **能奪冠 ≈ 55–60%**:差異化展示與 live/部署尚缺。
- **最大未爆彈**:live Silver(真 Bedrock + 真來源、卡 15 分鐘)**從未端到端跑過**。

## 2. 已具備的信任底子(可在 demo 直接講)
- 獨立群去重(識破轉載堆疊)、SHA-256 去重
- 交叉佐證抬升信心(需 ≥2 獨立群才准 high)、靜態可信度表(不由 LLM 動)
- material conflict 偵測、confidence 上限、5 維 `TrustScorecard`、deterministic renderer(數字絕不由 LLM 生)

## 3. 金牌工作流(依投報率排序)

| 代號 | 工作 | Lane | 狀態 | 驗收 |
|---|---|---|---|---|
| **G1** | **事實接地驗證(fact-grounding)** | 證據(+reasoning 語意層) | 🟢 確定性核心 + pipeline 揭露 + confidence gate(opt-in)已完成;語意複核待做 | 抽出事實的數值/日期能比對原文;捏造值被標 partial、揭露於 degradation,且不計入 confidence 佐證 |
| **G2** | **跨源三角驗證** | 證據(純 P2) | 🟢 已完成(`evidence/triangulation.py` + 測) | 價格異動日 ↔ 當天具名新聞/情緒對齊,產出 `TriangulatedEvent`(跨來源類型 strength) |
| **G3** | **信任漏斗 + TrustScorecard 上 UI** | 證據算/UI 顯示 | 🔴 未開始 | UI 首屏可見「N 筆→去重→獨立群→佐證→矛盾」漏斗 + 每 claim 的 5 維分數 |
| **G4** | **agent 判斷可視化** | reasoning | 🔴 未開始 | Planner 依題型明顯換來源策略;execution_log 呈現查核/降級決策 |
| **S8** | **live Silver 端到端跑通一次** | 全隊 | 🔴 gate 未過 | 真 Bedrock + baseline 來源,15 分內產四 artifact(拆最大未爆彈) |
| **S10** | **Gold local Exit** | 全隊 | 🔴 | 兩次獨立單幣 run、fake-clock budget、acceptance、run-log |
| **S11** | **部署 + 計時彩排** | 全隊 | 🔴 | ECR/EC2 tag 逐字相同、rollback 演練、一次完整 15 分鐘彩排 |

### G1 事實接地驗證(確定性面已完成)
- ✅ `evidence/grounding.py`:確定性硬原子(百分比/金額/數字/日期)比對 `content_reference`;跨語言(英文原文佐證中文事實);golden 測綠。
- ✅ **已接進 pipeline**:`ground_drafts` 在 `build_ledger` 前執行,partial 事實寫入 `degradation`(誠實揭露)。
- ✅ **已餵進 confidence**:`confidence_signals_for_claim(require_grounding=True)` 讓未接地的 LLM 事實**不計入獨立佐證群**,捏造值無法把信心抬到 high(opt-in、確定性重算、不加欄位、不動 reliability)。
- ⏭ 待做:純質性事實的**語意複核**(便宜 Haiku、走 `LLMClient` port、放 reasoning 層,非 `evidence/`);以及決定是否在 live pipeline 預設開啟 `require_grounding`。
- 🚫 紅線:不動靜態 `reliability`;不加 `EvidenceItem` 欄位(除非走路線 B + 團隊簽核)。

### G2 跨源三角驗證(建議下一個做,純你 lane)
- 取市場證據的異動日(如 |日報酬| 或波動 z-score 超閾值)、對齊當天 ±N 日的具名新聞與情緒方向。
- 產出 deterministic 結構(不進 `EvidenceItem` 契約,另開一個 summary/衍生物件),供 Arbiter 與 UI 用。
- **主題正中紅心**:「三種不同類型來源同時指向同一事件」= 最高等級信任故事。

### G3 信任漏斗(展示 ROI 最高)
- 證據層輸出漏斗數字(P2)、UI 畫圖(P4);TrustScorecard 你已算好,只差呈現。

## 4. 全案紅線(任何工作都不得違反)
1. 市場數值只能來自 deterministic 工具;**LLM 不得補值、不得當證據來源**。
2. reliability **靜態**,不由模型調整。
3. 報告**無投資建議**(renderer 已跑 `advice_lint`)。
4. agent **有界**(步數/單呼叫/stage deadline 上限)。
5. **秘密**永不進 code/repo/log/artifact/UI/錄影;EC2 用 IAM 角色,不放金鑰。

## 5. 建議順序
**G1 收尾(語意複核 + 接線)→ G2 三角驗證 → G3 信任漏斗 → S8 live Silver → S10 → S11。**
G2/G3 對 Bronze/Silver 非阻塞,但都須在 **S10 觸發 Feature Freeze 前**完成。
