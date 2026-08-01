# S2 ↔ S1 契約期望與交接（Task 2 → Task 1b）

> ## ✅ 這份交接已完成（2026-08-01）——以下保留為紀錄
>
> Task 1b 已合併，§4 的 swap 程序**已執行完畢**：`src/hoya_agent/_provisional_seams.py`
> 與 `tests/integration/test_s1_seam_bridge.py` 都已刪除，全套測試 670 passed。
>
> 契約贏了每一處分歧，S2 是改的那一邊。實際改了什麼：
> `RunContext` 的 `question`/`assets`/`run_mode` 收進 `request`、`deadline_seconds` →
> `deadline_monotonic`、改由 `clock.build_run_context()` 建構；`RunSummary` 依 `design.md` §104
> 只留 artifact 路徑／data mode／stage 狀態／降級說明；`RunConfigSnapshot` 改由
> `Settings.sanitized_snapshot()` 產生；`ProgressSink.emit()` → `publish()`；
> `AnalysisPipeline`／`PipelineOutcome`／`EventEmitter` 移進 `orchestration/pipeline.py`。
> 完整清單見 `docs/Implementation-Plan.md` 的 S2 現況區塊。
>
> **本文件不再是待辦，不要再照著它做一次 swap。**

> 狀態：**需求說明與交接備忘，非實作**。
>
> **權威順序**：`.kiro/steering/evidence-contracts.md` > `.kiro/specs/hoya-market-agent/design.md` >
> `.kiro/specs/hoya-market-agent/tasks.md` > 本文件。
> 若 Task 1b 的實際命名與本文件不同而仍合乎契約，**改 S2，不改 1b**。
>
> 對照文件：`docs/ai/P3_CONTRACT_EXPECTATIONS.md`（S7/Task 6 用同一套做法先行實作）。

## 1. 為什麼需要這份文件

`tasks.md` 的 Task 2（S2，fixture 垂直切片）依賴 Task 1（S1）。S1 的前半 **1a 已合併進 `main`**
（PR #6，merge `faf437b`：`models.py` 的資料契約），但後半 **1b（runtime seams）仍在進行中**，
因此 `main` 上還沒有：

| 缺什麼 | 1b 的落點 |
|---|---|
| `RunContext`、`ExecutionEvent`、`RunConfigSnapshot`、`RunSummary` | `models.py`（1b 的 *Modify* 項） |
| `Clock`、`ProgressSink`、`ArtifactStore` 等 Protocol | `ports.py` |
| `Settings` / `parse_env()` / `sanitized_snapshot()` | `config.py` |
| fixed clock、fake adapters、in-memory progress sink | `tests/conftest.py`、`tests/fakes.py` |

S2 不能等，也**不得直接編輯上述任何檔案**（它們是 1b owner 正在動的路徑，
`models.py` 更是四個人共用）。所以 S2 採用與 P3 相同的策略：**把需要的形狀先宣告在自己的路徑裡，
並留下一個會自動生效的驗證機制**。

## 2. 接縫機制（三個部分）

### 2.1 `src/hoya_agent/_provisional_seams.py` — 暫時替身

- 內容只有「1b 或 Task 3 應該提供、但目前不存在」的型別，欄位名逐字抄自
  `evidence-contracts.md` §13（Execution Log）與 §14（Run Config）。
- 檔頭明寫它是替身、由誰接手、何時刪除。
- 🚫 不得在此加入只有 S2 方便用的欄位。
- 先例：`src/hoya_agent/evidence/types.py` 對 `EvidenceDraft` 扮演同樣角色。

### 2.2 `tests/integration/test_s1_seam_bridge.py` — 會自己醒來的橋接測試

- 真實 seam 不存在時 **skip**（目前 6 skipped）。
- 1b 一落地就自動開始比對：
  - 替身的欄位集合必須是真實契約的子集，否則指名多出來的欄位；
  - 替身 Protocol 用到的方法必須存在於真實 `ports.py`；
  - 全部 seam 都到位時，`test_swap_is_still_pending` **故意失敗**，訊息就是替換步驟。
- 這樣「欄位漂移」不需要靠人記得，測試會講。

### 2.3 本文件 — 讓 1b owner 知道 S2 會消費什麼

見 §3。

## 3. S2 實際消費的名稱

### 3.1 `models.py`（1b 新增）

**`ExecutionEvent`**（`execution_log.jsonl` 每一行；§13）

`schema_version` `timestamp` `run_id` `run_mode` `stage` `event_type` `status`
`duration_ms` `provider_or_model` `parameters` `attempt` `input_count`
`output_count` `error_category` `message`

- `parameters` 為 sanitized `dict[str, str]`；🚫 不含 token、header、憑證。
- 🚫 不記 prompt 全文與 chain-of-thought。
- S2 實際使用的 `event_type`：`run_start`、`run_end`、`cutoff_frozen`、
  `request_asset_mismatch`、`artifact_write`、`artifact_write_failed`、`stage_end`。

**`RunConfigSnapshot`**（`run_config.json`；§14）

`schema_version` `prompt_version` `policy_version` `run_id`
`requested_run_mode` `effective_run_mode` `sanitized_request` `analysis_as_of`
`deadline_seconds` `stage_durations_ms` `configured_sources`
`optional_keys_present` `used_recorded_fallback` `used_cached_evidence`
`has_stale_evidence` `terminal_status` `artifact_checksums` `missing_artifacts`
`artifact_write_failures`

- `optional_keys_present` 只放**存在布林值**（`BEDROCK_FALLBACK_MODEL_ID`、
  `CRYPTOPANIC_API_TOKEN`），🚫 永不放值。
- `missing_artifacts` 與 `artifact_write_failures` 是 design.md §12.1 的缺檔揭露契約載體。

**`RunSummary`**（回給 UI）

`run_id` `run_mode` `terminal_state` `artifact_dir` `artifact_paths`
`missing_artifacts` `evidence_item_count` `confidence` `insufficient_data`
`degradation_notes` `report_markdown`

**`RunContext`**（run 開始後不可變）

`run_id` `run_mode` `question` `assets` `analysis_as_of` `deadline_seconds`

- `official` 的 `analysis_as_of` 由注入 clock 在 run 開始凍結；rehearsal／demo 可重播固定值。

### 3.2 `ports.py`（1b 新增）

```python
class Clock(Protocol):
    def now_utc(self) -> datetime: ...
    def monotonic(self) -> float: ...

class ProgressSink(Protocol):
    def emit(self, event: ExecutionEvent) -> None: ...
```

- S2 只用到這兩個。`ArtifactStore` 的具體實作是 `reporting/artifacts.py::LocalArtifactStore`；
  1b 若定義 `ArtifactStore` Protocol，請對照它現有的方法：
  `write_text` `write_json` `append_event` `checksums` `artifact_paths`
  `missing_artifacts` `disclose_missing` `failures` `directory_writable`。

### 3.3 `config.py`（1b 新增）— 目前**刻意不耦合**

S2 的 `ApplicationService.__init__` 直接收 `artifact_root: Path`、`prompt_version`、
`policy_version`、`configured_sources`、`optional_keys_present`，**沒有** import `Settings`。
理由：`Settings` 的欄位還沒定案，用 `Path` 是最小承諾。

1b 落地後建議由 S2 補一個 classmethod（不改 1b 的檔案）：

```python
@classmethod
def from_settings(cls, settings: Settings, *, clock: Clock, pipeline: AnalysisPipeline) -> "ApplicationService":
```

S2 需要 `Settings` 提供：`artifact_root`、`bedrock_primary_model_id`（記識別字）、
以及 optional key 的**存在布林值**。

### 3.4 Task 3（orchestration）會取代的部分

`_provisional_seams.py` 另含兩個 **Task 3 擁有**的形狀，S2 只是先給 pipeline 一個注入點：

- `TerminalState`（`completed|degraded|failed|cancelled`）→ 落點 `orchestration/run_state.py`；
- `AnalysisPipeline` Protocol 與 `PipelineOutcome`（`ledger` / `result` /
  `terminal_state` / `degradation_notes` / `stage_durations_ms`）→ 落點 `orchestration/pipeline.py`。

Task 3 只要讓 `DeadlineAwarePipeline.execute(context, emit)` 回傳同形狀的結果，
`application.py` 不需要改。

## 4. 替換程序（1b 合併後照做）

```bash
# 1. 先跑橋接測試，它會告訴你是否有欄位不符
python -m pytest tests/integration/test_s1_seam_bridge.py -vv

# 2. 重新指向真實 seam（機械式取代）
#    hoya_agent._provisional_seams -> hoya_agent.models / hoya_agent.ports
#    受影響檔案只有三個：application.py、reporting/artifacts.py、
#    tests/integration/test_vertical_slice.py

# 3. 刪掉替身與橋接測試
git rm src/hoya_agent/_provisional_seams.py tests/integration/test_s1_seam_bridge.py

# 4. 驗證
python -m pytest tests/unit tests/contract tests/integration -q
ruff check .
```

替換時的固定判準：**名稱不符一律改 S2**。1b 的 `models.py`／`ports.py` 是唯一真相。

## 5. S2 刻意沒有碰的檔案（避免撞其他 owner）

| 檔案 | Owner | S2 的處理方式 |
|---|---|---|
| `models.py`、`config.py`、`clock.py`、`ports.py` | Task 1b（S1） | 用 `_provisional_seams.py` 替身 |
| `tests/conftest.py`、`tests/fakes.py` | Task 1b | fixture loader 暫放 `tests/unit/reporting/conftest.py`；fake clock／progress sink 暫放測試檔內 |
| `reporting/lint.py` | Task 7 / S3（UI） | `renderer.render(..., lint=hook)` 留好注入點；禁語表暫以測試常數把關 |
| `orchestration/` | Task 3 | 以 `AnalysisPipeline` Protocol 注入，fixture pipeline 只存在於測試 |
| `evidence/types.py`、`evidence/policies.py`、`reasoning/`、`adapters/bedrock.py` | 已凍結 | 完全未 import |

## 6. 已知待決事項

1. **`reporting/lint.py` 沒有出現在任何 task 的 file list**（只在 `Implementation-Plan.md` S3 與
   `structure.md` 出現）。目前 renderer 只提供注入點，production 預設不執行 lint。
   D 落地 `lint.py` 後必須把它接到 `render(..., lint=...)`，否則禁語防線只存在測試裡。
2. **`AnalysisRequest.run_id` 是必填**（1a 的決定），所以 run identity 必須在 request 建立時就決定。
   S2 因此提供 `application.make_run_id()` 與 `application.build_request()`；
   UI 應該用 `build_request()` 而不要自己拼 `run_id`。
3. **`analysis_as_of` 的凍結點**：`build_request()` 在 `official` 模式拒絕呼叫端自訂 cutoff，
   `ApplicationService` 另外以注入 clock 覆寫 `RunContext.analysis_as_of` 並記錄 `cutoff_frozen` 事件。
   1b 若把凍結邏輯放進 `RunContext`，S2 這段就可以刪掉。
4. **clock tolerance**（`fetched_at` 早於 `published_at` 的容許量）仍是 1b 的 deferral，S2 未使用。
