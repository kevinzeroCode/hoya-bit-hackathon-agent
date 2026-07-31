# P3（Reasoning / Report）交接文件

> 分支：`task/6-bedrock-reasoning`
> 日期：2026-07-31
> 本次由 Claude Code 完成。接手者（人或其他模型）請**先讀完本文件第 1、5 節**再動手。

## 1. 三十秒摘要

Task 6（bounded Planner / Research Agent / Arbiter）**程式碼與測試已完成並全部跑過**：
134 個測試 + 15 個 subtests 通過，`ruff check` 無違規。三份 prompts 已寫好。

**尚未做、且明天要做的兩件事：**

1. **接上真實契約**——目前 reasoning 模組的 schema 類別是**注入**的，測試用 stub 契約。
   Kiro 產出 Task 1 的 `models.py` 後，把真實類別接進去（見第 5 節，預估 30 分鐘）。
2. **Bedrock live 驗證**——AWS 資源到位後跑真實呼叫（見第 6 節）。

**沒有做**：`models.py` / `ports.py` / `renderer.py` / `artifacts.py` / `application.py`。
這些是 CLAUDE.md 指定保留給 Kiro 的 Task 1、Task 2 檔案，本次**刻意避開**。

## 2. 為什麼避開 Task 1／Task 2

原計畫是先補 Task 1 共享契約再做 P3。發現隊友新推的 `CLAUDE.md` 明文規定：

> Task 1（models/contracts）與 Task 2（fixture vertical slice）由 Kiro 從 spec 生成，
> 作為「Kiro 用於開發」的證據。**Claude Code 不要搶先實作這兩個 task 的核心檔案。**

Kiro 使用證據關係到 **+10% 加分**，因此改為嚴格遵守：P3 只做 Task 6 與 prompts，
契約需求改以文件形式交付（`docs/ai/P3_CONTRACT_EXPECTATIONS.md`）供 Kiro 生成時對照。

## 3. 交付內容

### 程式碼

| 檔案 | 內容 |
|---|---|
| `src/hoya_agent/adapters/bedrock.py` | Bedrock Converse 邊界：強制 tool call 取結構化輸出、**至多一次** schema repair、per-call timeout clamp 到 stage deadline、**僅** throttling/5xx 才切備援模型、sanitized 事件記錄 |
| `src/hoya_agent/reasoning/prompt_library.py` | 版本化 prompt 載入，對外只吐版本標籤（`arbiter-v1`），不吐內文 |
| `src/hoya_agent/reasoning/planner.py` | 有界規劃；計畫若指定允許清單外的操作或改動 assets，整份丟棄改用決定論預設計畫 |
| `src/hoya_agent/reasoning/research_agent.py` | 執行允許清單操作 → **一次**抽取呼叫；注入文字當引用資料處理並揭露；引用不存在紀錄的 draft 直接丟棄 |
| `src/hoya_agent/reasoning/arbiter.py` | 證據排序截斷、結構驗證（參照可解析／DAG 無環／結論須有非中性 link）、**決定論信心上限**、決定論 fallback |
| `src/hoya_agent/reasoning/conflict_extension.py` | `DisabledConflictExtension`：無網路無 LLM，恆 route 到 Arbiter，`enable_conditional_debate=true` 記為 ignored |

### Prompts

`prompts/planner-v1.md`、`prompts/research-extraction-v1.md`、`prompts/arbiter-v1.md`

三份都含：禁投資建議、禁 JSON 以外輸出、prompt-injection 隔離條款、繁中輸出。
`arbiter-v1.md` 另含 fact→inference→conclusion 分層範例、反方證據硬性要求、
信心規則、量化 invalidation 契約（`metric`/`operator`/`threshold`/`basis_evidence_id`）。

### 測試（全部實跑通過）

```
tests/contract/test_bedrock_client.py      27 passed
tests/unit/reasoning/test_prompt_library.py 28 passed + 15 subtests
tests/unit/reasoning/test_arbiter.py        36 passed
tests/unit/reasoning/test_planner.py        19 passed
tests/unit/reasoning/test_research_agent.py 17 passed
tests/unit/reasoning/test_conflict_extension.py 9 passed
```

`test_prompt_library.py` 對三份 prompt 的**內容**下斷言（例如 arbiter 必須提到
`basis_evidence_id`、必須禁機率），所以有人刪掉某條規則會讓 build 失敗。

## 4. 本次做的兩個設計決定（P1 可推翻）

**決定一：schema 類別用注入，不用 import。**
`Arbiter(llm, result_schema=AnalysisResult)`、`Planner(llm, plan_schema=ResearchPlan)`、
`ResearchAgent(llm, draft_schema=...)`。

- 原因：Task 1 尚未存在，注入讓 Task 6 邏輯**今天就能被真實測試**，而不是寫一堆跑不動的程式碼。
- 副作用：與 `converse_structured(schema=...)` 的既有形狀一致，且決定論 fallback 走**同一個 schema 驗證**，不會產生繞過驗證的路徑。
- 若 P1 偏好直接 import，改成 module-level import 即可，其餘邏輯不動。

**決定二：信心上限用「決定論下修」而非「拒絕」。**
`design.md §9` 寫「confidence obeys the caps」為輸出接受條件。實作上，**結構性**違規
（參照解不開、DAG 有環、結論無證據）→ 拒絕並走 fallback；**信心上限**違規 → 依規則
下修並記入 `degradation_notes`。

- 原因：上限只會往下調，不可能製造出沒有的把握；為了一個可決定論修正的欄位丟掉整份分析
  不划算，且下修後輸出確實「obeys the caps」。
- 每次下修都會寫進 `degradation_notes`，報告可以誠實揭露。
- 若 P1 認為必須嚴格拒絕，把 `apply_confidence_caps` 的呼叫改成「檢查到違規就走 fallback」即可。

## 5. 明天第一件事：接上 Kiro 的真實契約

Kiro 跑完 Task 1 後：

1. 讀 `docs/ai/P3_CONTRACT_EXPECTATIONS.md`，**逐項比對** Kiro 產出的 `models.py`。
   **以 Kiro 產出為準**，不是以本文件為準。
2. 已知需確認的三個假設：
   - `AnalysisResult.invalidation_conditions` 是否為結構化的 `InvalidationCondition`
     物件陣列（本文件 §2.8 有說明此處 spec 有兩種讀法）。
   - `ResearchPlan` 的欄位名（evidence-contracts.md 未定義，P3 是提案方）。
   - `ConflictExtensionResult` 目前定義在 `reasoning/conflict_extension.py`，
     若 Kiro 把它放進 `models.py`，改成 import 並刪掉本地定義。
3. 把測試裡的 stub 換成真實類別：
   - `tests/unit/reasoning/_stubs.py` 的 `Result` / `Plan` / `DraftBatch` / `Evidence` 等
     改成從 `hoya_agent.models` import，其餘 fake（`FakeLLM` / `FakeRegistry`）保留。
   - 跑 `python -m pytest tests/unit tests/contract -q`，修欄位名不符處。
4. 刪掉兩個臨時的 path bootstrap：`tests/contract/conftest.py`、
   `tests/unit/reasoning/conftest.py`——Task 1 的 `pyproject.toml` 與 `tests/conftest.py` 會取代它們。
5. `src/hoya_agent/__init__.py` 與 `src/hoya_agent/adapters/__init__.py` 目前是**空檔**，
   只為讓 package 可 import。Task 1／Task 4 若也建立同名檔案會有 trivial 衝突，取對方的版本即可。

## 6. 明天第二件事：Bedrock live 驗證

本機**完全沒有**跑過真實 Bedrock 呼叫。`bedrock.py` 的 boto3 client 是 lazy import，
測試全部用 fake client，所以離線也能跑。

1. AWS Console → Bedrock → Model access，開通模型存取。
2. 確認該 region 實際可用的模型 ID：
   ```bash
   aws bedrock list-foundation-models --region <REGION> \
     --query "modelSummaries[?contains(modelId,'claude')].modelId" --output table
   ```
   **Bedrock 的模型 ID 帶 `anthropic.` 前綴**（例如 `anthropic.claude-sonnet-5`），
   與第一方 API 的裸 ID 不同。不要憑印象填，一律以 `list-foundation-models` 的輸出為準。
3. `.env` 填入（**值不得進 repo**）：
   ```
   AWS_REGION=<REGION>
   BEDROCK_PRIMARY_MODEL_ID=<Sonnet 系列，取自上一步>
   BEDROCK_FALLBACK_MODEL_ID=<Haiku 4.5，取自上一步>
   ARTIFACT_ROOT=./artifacts
   ```
   選型理由：Arbiter 需要較強的結構化推理與長 context，用 Sonnet；備援只在
   throttling/可用性失敗時觸發，用 Haiku 求快求便宜。這是**成本／品質的取捨，不是硬性規定**，
   有預算就把主力換更強的模型。
4. 冒煙測試（尚未撰寫，需新增）：呼叫一次 `BedrockLLMClient.converse_structured`
   帶一個小 schema，確認 toolConfig 強制輸出在真實模型上可行。
   **這是唯一無法離線驗證的部分，優先做。**
5. 提醒：Silver 門檻要求**至少一次 schema-valid 的真實 Bedrock 成功**，
   只有 fallback 成功不算數（`tasks.md` Execution Rules）。

## 7. 尚未完成、屬於 P3 但被 Task 2 擋住的部分

`reporting/renderer.py` 與 `reporting/lint.py` 在四人分工文件中屬於 P3 擁有，
但 `renderer.py` 列在 Task 2 的檔案清單（Kiro）。因此本次**未實作**。

Kiro 跑完 Task 2 後，P3 需要補：

- `reporting/lint.py`：投資建議禁語 lint（`renderer` 的最後防線）。
  禁語清單可直接取自 `prompts/arbiter-v1.md` 第一節的列舉。
- 確認 renderer 產出含 requirements.md Req 11 的 11 個繁中章節。
- Task 11（creativity layer）的 renderer 部分：regime headline、Trust Scorecard、量化 invalidation。

## 8. 對接的介面（給 P1 整合 Task 8 時看）

```python
planner = Planner(llm=bedrock_client, plan_schema=ResearchPlan, tool_registry=registry)
plan, notes = await planner.run(request=request, deadline=stage_deadline)

agent = ResearchAgent(llm=bedrock_client, draft_schema=DraftBatch, tool_registry=registry)
outcome = await agent.run(plan=plan, request=request, deadline=stage_deadline)
# outcome.status / .drafts / .records / .degradation_events / .executed_operations

extension = DisabledConflictExtension()
routing = await extension.evaluate(ledger, indicators, context)   # 恆為 arbiter

arbiter = Arbiter(llm=bedrock_client, result_schema=AnalysisResult)
result, notes = await arbiter.run(
    request=request, ledger=ledger, indicators=indicators,
    deadline=stage_deadline, degradation_notes=accumulated_notes,
)
```

- 三個 stage **都不寫 artifacts**，只回傳資料——寫檔屬 P1。
- `deadline` 是 `time.monotonic()` 基準的**絕對時間點**，不是剩餘秒數。
- `bedrock_client.drain_events()` 回傳 sanitized `CallEvent` 清單，直接餵 `execution_log.jsonl`。
- `planner.prompt_version` / `agent.prompt_version` / `arbiter.prompt_version` 給 `run_config.json`。
- Planner 與 Arbiter **不會**因為 provider 失敗而拋例外；它們回傳決定論後備結果加上說明 notes。
  只有「registry 在執行期被竄改」會拋 `RuntimeError`，那是不該吞掉的違規。

## 9. 驗證指令

```bash
python -m pytest tests/unit tests/contract -q
python -m ruff check src tests
```

環境注意：本機是 **Python 3.11.9**，spec 要求 3.12。目前程式碼未用 3.12 專屬語法，
但 Task 1 的 `pyproject.toml` 會把 `requires-python` 訂在 3.12——屆時本機需裝 3.12，
或由 P1 決定是否放寬。
