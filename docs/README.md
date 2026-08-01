# claude-plan — HOYA Market Agent 上游設計文件組

> **這一整組文件是衍生視圖，不是新的真相來源。**
> 規範性權威仍是 `.kiro/specs/hoya-market-agent/`（requirements / design / tasks）
> 與 `.kiro/steering/`（尤其 `evidence-contracts.md`）。
> **若本組任一文件與 `.kiro/` 衝突，以 `.kiro/` 為準**，並回報以便修正本組文件。

這是用 **design-pipeline** 方法產出的四份互相咬合的上游設計文件。
`.kiro` 已經把「需求、契約、任務」寫得很完整；這一組補上它缺的三件事：

1. **檔案級地圖** —— 每個檔做什麼、跟誰互動、**現在存不存在**；
2. **分階段建置順序** —— 每階段可獨立驗證，帶會持續更新的現況區塊；
3. **人工檢查清單** —— 那些無法 headless 驗證的部分該怎麼驗、誰簽核；
   直接內嵌在 ④ 的 [§3.2](Implementation-Plan.md) 與各階段的「測試」欄，不另開文件。

---

## 依相依順序閱讀

| # | 文件 | 回答什麼問題 | 交給下一份什麼 |
|---|---|---|---|
| ① | **[Features.md](Features.md)** | 這個產品**做得到什麼**？契約詞彙表在哪？ | 能力面 + **§7 外部相依面** + §5 契約詞彙表 |
| ② | **[Tech-Stack-Plan.md](Tech-Stack-Plan.md)** | 動工前必須鎖死什麼？橫切關注點怎麼設計？第一刀切哪裡？ | 分層佈局 + 只准向內的依賴規則 + **風險導向的第一個里程碑** |
| ③ | **[Architecture-FileMap.md](Architecture-FileMap.md)** | 每個檔做什麼、跟誰互動、**現在存不存在**？ | 具體檔名（④ 的「元件」欄位直接指回來） |
| ④ | **[Implementation-Plan.md](Implementation-Plan.md)** | 什麼時候建什麼？每階段怎麼算完成？現在做到哪？無法 headless 驗證的怎麼簽核？ | 現況與簽核結論回寫進自己的階段區塊 |

```text
產品命題 + 主辦方資料集
        │
        ▼
  ① Features ──(能力面 + 外部相依面 + 契約詞彙表)──▶
  ② Tech-Stack-Plan ──(分層 + 依賴規則 + 橫切設計 + 第一里程碑)──▶
  ③ Architecture-FileMap ──(檔案級職責 + 依賴 + 流程 + 現況)──▶
  ④ Implementation-Plan ──(階段 + 現況 + Definition-of-Done + 人工檢查清單)
        │
        ▼
  隨設計與程式碼演進，四份保持同步
```

---

## 現況速覽（2026-08-01，基準 commit `f7536fb`）

| 項目 | 狀態 |
|---|---|
| `main` 的 Python 樹 | ✅ **44 個 `.py`**，**501+ tests passing**（Python 3.12.13） |
| `pyproject.toml` | ✅ 已存在（含 `[dev]` extras） |
| 共用契約 `models.py`（S1） | ✅ **已存在，40 個 Pydantic classes**（Task 1a + corrective 完成） |
| Runtime seams `config.py`、`clock.py`、`ports.py` | ✅ 已存在（Task 1b 落地） |
| S2 fixture vertical slice | ✅ **COMPLETE on main**（`application.py`、`reporting/`、四項 artifacts 離線整合測試） |
| 推理層（S7） | ✅ **已完成並凍結**（`adapters/bedrock.py` + `reasoning/` + `prompts/`） |
| 市場與證據層（S5/S6） | ✅ **INTEGRATED on main**（`data/`、`evidence/`、adapters: organizer_csv, binance, cryptopanic, rss, alternative_me, port_adapters） |
| 編排（S3） | 🟡 CSV-only pipeline 存在（`orchestration/pipeline.py` OrganizerCsvPipeline）；full deadline/fork-join 未開始 |
| 報告（S2/Renderer） | ✅ `reporting/renderer.py` + `reporting/artifacts.py` on main |
| UI（S4） | 🔴 未開始 |
| **真實 Bedrock 呼叫（S0）** | 🟡 **已成功呼叫過，但 S0 未關閉** —— 卡在 AWS 帳號設定，見下 |
| **`main` 測試狀態** | ❌ **6 failed / 564 passed**（`test_s1_seam_bridge.py`，設計上的 swap 信號） |

> ⚠️ **如果你只讀一段，讀這一段：**
> **「Bedrock 一次都沒呼叫過」已經不成立。** P2 於 2026-08-01 在 `us-west-2` 以
> `us.anthropic.claude-haiku-4-5-20251001-v1:0` 成功呼叫（紀錄見
> `p2-etl-mvp/docs/service-access-check.md`）。
>
> **但 S0 仍然關不掉，剩下兩個獨立的缺口：**
>
> 1. **AWS 帳號未提交 Anthropic use case details 表單。** 現在每次呼叫都回
>    `ResourceNotFoundException: Model use case details have not been submitted for this account`。
>    Bedrock 本身可達（列得到 112 個模型、Haiku 4.5 在清單內），標準 AWS profile 憑證也有效——
>    純粹卡在主控台這一步。**沒填完，比賽當天整個 H2-Lite 是死的。**
> 2. **S0 退出條件 #1 要的是一次真實的 *Converse 結構化輸出* 呼叫。** P2 那次走的是
>    `invoke_model`，而 `adapters/bedrock.py` 走的是 `converse` + forced `toolConfig`——
>    不是同一條路。已證明的是憑證／region／模型存取權，未證明的是強制工具呼叫的結構化輸出。
>
> → [Implementation-Plan 的 S0](Implementation-Plan.md)。

---

## 里程碑

| 里程碑 | 階段 | 成果 |
|---|---|---|
| M0 可執行性 | S0 · S1 | ✅ 契約凍結（models.py 40 classes）；⚠️ 外部服務尚未證實可用（Bedrock 零次呼叫） |
| **M1 Bronze** ★ | S2 · S3 | ✅ **完全離線**從 fixture 產出並驗證四項 artifacts（S2 complete, CSV pipeline exists） |
| M2 能力層 | S4 · S5 · S6 · S7 | ✅ S5/S6 integrated on main；✅ S7 frozen；🟡 S4 deadline 編排未開始 |
| **M3 Silver** ★ | S8 | 🔴 一次 live schema-valid Bedrock run **＋** 一次獨立的 deterministic fallback |
| M4 洞察 | S9 | 🔴 Trust Scorecard、Market Regime、量化 invalidation（非阻塞） |
| **M5 Gold local Exit** ★ | S10 | 🔴 兩個不同資產各一次獨立單幣 run → **觸發 Feature Freeze** |
| M6 交付 | S11 | 🔴 ECR/EC2 部署 + 一次 15 分鐘計時彩排 + 提交驗證 |

---

## 依角色的入口

| 你是 | 先讀 |
|---|---|
| 第一天加入、想搞懂全貌 | ① → ③（然後看 `docs/ACTIVE_WORK.md` 認領工作） |
| 要開始寫某個模組 | ③ 找到你的檔案 row → ④ 找到對應的階段 |
| 要驗收某個階段 | ④ 的該階段 → 若是 S0/S3/S11 再看 ④ 的 §3.2 人工檢查清單 |
| 要知道「現在做到哪」 | 本頁的現況速覽 → ④ 各階段的現況區塊 |
| 要知道「誰正在改哪個檔」 | **`docs/ACTIVE_WORK.md`**（那是它的職責，不是這一組的） |
| 要知道欄位的精確語意 | **`.kiro/steering/evidence-contracts.md`**（規範性擁有者） |

---

## 每份文件各自擁有什麼（🚫 不要在別處重新決定）

這一組刻意維持「一個事實只有一個擁有者」：

| 事實 | 唯一擁有者 |
|---|---|
| 能力清單、契約詞彙表、外部相依面 | ① Features.md（其中欄位語意再上溯 `evidence-contracts.md`） |
| 技術棧、授權姿態、分層佈局、依賴規則、橫切設計、第一里程碑 | ② Tech-Stack-Plan.md（規範性再上溯 `tech.md` / `structure.md`） |
| 每個檔的職責、互動對象、**存在狀態** | ③ Architecture-FileMap.md |
| 階段順序、每階段現況、Definition-of-Done、可追溯性、人工檢查清單與簽核條件 | ④ Implementation-Plan.md（任務規範性再上溯 `tasks.md`） |
| 誰正在做什麼、哪些路徑已凍結 | **`docs/ACTIVE_WORK.md`**（不在本組） |

**下游文件只「指向」上游，🚫 不重新決定。**
如果你在寫 ④ 時想重新定義一個欄位，正確做法是回去修 ① 或 `evidence-contracts.md`，
然後往前重新流一次——這條 pipeline 是迴圈，不是單行道。

---

## 維護規則

- **③ 與 ④ 帶活的狀態，必須跟著程式碼走。** 檔案落地、改責任、被合併時，
  更新它的 ③ row 就是那個檔 definition-of-done 的一部分；階段完成時更新它的 ④ 現況區塊。
- **記錄刻意的偏離。** 偏離計畫是正常的，藏起來才是問題
  （例：S7 在 S1 之前完成——這已記在 ④ 的 S7 現況區塊）。
- **被折進別處的檔案留麵包屑**，🚫 不要靜默刪除 row —— 追舊參照的人需要那條線索。
- **名稱要跨文件一致**：④ 的元件必須是 ③ 的 row；③ 的流程必須用 ① 的能力；
  ④ 的步驟與人工檢查項必須引用 ① 的契約詞彙表。

---

*本組文件由 design-pipeline（feature-specification → tech-stack-plan → architecture-file-map →
implementation-roadmap）依序產出，並在完成後跑過整組一致性檢查。
人工驗證原先規劃為第五份 testing-guide，已合併進 ④ §3.2 與各階段的「測試」欄，不另立文件。*
