# P3 對共享契約的需求規格

> 狀態：**需求說明，非實作**。這份文件不定義新契約，只把 `reasoning/` 與 `adapters/bedrock.py`
> 實際會 import 的名稱，從 `.kiro/steering/evidence-contracts.md` 抄錄成一張清單。
>
> **權威順序**：`.kiro/steering/evidence-contracts.md` > `.kiro/specs/hoya-market-agent/design.md` > 本文件。
> 若本文件與 evidence-contracts.md 有出入，**以 evidence-contracts.md 為準**，並回頭修正本文件與 P3 程式碼。
>
> 用途：Task 1（`models.py` / `ports.py` / `config.py`，由 Kiro 生成）與 Task 6（P3 手寫）之間的介面備忘。
> Kiro 生成 Task 1 時可對照本清單確認欄位齊全；P3 程式碼已依此清單撰寫。

## 1. 為什麼需要這份文件

`tasks.md` 的 Task 6（bounded Planner / Research Agent / Arbiter）依賴 Task 1 的共享契約，但
CLAUDE.md 規定 Task 1、Task 2 保留給 Kiro 從 spec 生成（作為 Kiro 使用證據）。因此 P3 在 Task 1
落地前先行實作 Task 6，程式碼一律 import `hoya_agent.models` 與 `hoya_agent.ports` 的下列名稱。

Task 1 落地後的第一件事：跑 `python -m pytest tests/unit/reasoning tests/contract -q`，
把名稱不符處對齊到 Kiro 產出的實際契約（**以 Kiro 產出為準，不是以 P3 為準**）。

## 2. `models.py` — reasoning 層直接使用的型別

### 2.1 列舉

| 名稱 | 值 | 來源 |
|---|---|---|
| `Asset` | `BTC` `ETH` `SOL` `BNB` `XRP` | §1 |
| `RunMode` | `official` `rehearsal` `demo` | §1 |
| `SourceType` | `official` `market` `news` `onchain` `social` `macro` | §1 |
| `Reliability` | `high` `medium` `low` | §1 |
| `Stance` | `supports` `opposes` `neutral` | §1 |
| `ClaimType` | `fact` `inference` `conclusion` | §1 |
| `TrustLevel` | `strong` `moderate` `weak` `unavailable` | §16.1 |
| `RegimeLabel` | `trending_up` `trending_down` `range_bound` `high_volatility` `mixed` | §16.3 |
| `InvalidationOperator` | `lt` `lte` `gt` `gte` | §16.4 |

全部以 `str` 為底（`class Asset(str, Enum)`）以便直接序列化。

### 2.2 `EvidenceItem`（§3）— Arbiter 的唯一事實來源

`evidence_id` `asset` `source_type` `source_name` `source_url` `published_at`
`fetched_at` `query_or_parameters` `content_reference` `normalized_fact`
`reliability` `independence_group` `content_hash` `is_cached` `cache_time` `is_stale`

- `asset` 可為 `None`（僅限全市場指標，如 Fear & Greed）。
- **不得有 stance 欄位**——這是 P3 測試會斷言的反向條件。
- 拒收舊欄名 `fetched time` / `fetched_time`。

### 2.3 `EvidenceLedger`（§12）

`schema_version` `run_id` `analysis_as_of` `run_mode` `items` `conflict_indicators` `degradation_events`

P3 需要能以 `evidence_id` 查表，建議提供 `items_by_id` property 或由 reasoning 自行建 dict（目前 P3 自行建）。

### 2.4 `ConflictIndicator`（§9）

`claim_id` `supporting_evidence_ids` `opposing_evidence_ids` `independence_groups` `rule_version`

### 2.5 `Claim`（§7）

`claim_id` `claim_type` `assets` `time_range` `text` `based_on_claim_ids`
`confidence` `limitations` `invalidation_conditions`

`time_range` 為 `{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}`。

### 2.6 `ClaimEvidenceLink`（§8）— stance 的唯一持有者

`claim_id` `evidence_id` `stance` `reason`

### 2.7 `AnalysisResult`（§11 + §16）

`run_id` `question` `assets` `analysis_as_of` `direct_answer` `market_context`
`claims` `claim_evidence_links` `confidence` `confidence_rationale`
`limitations` `invalidation_conditions` `watch_items` `insufficient_data` `degradation_notes`
＋ §16 新增：`market_regime`（optional）、`trust_scorecards`（list，預設空）

`market_context` 為 `{"summary": str, "time_range": {...}}`。

### 2.8 `InvalidationCondition`（§16.4）

`text`（必填）`metric` `operator` `threshold` `basis_evidence_id`（後四者可全為 `None` = 定性條件）。

> **注意**：§7 的 `Claim.invalidation_conditions` 範例是字串陣列，§16.4 則是結構化物件。
> P3 目前假設 **`AnalysisResult.invalidation_conditions` 為 `list[InvalidationCondition]`**，
> `Claim.invalidation_conditions` 維持 `list[str]`。Task 1 落地時請確認此假設；若 Kiro 採不同解讀，
> 以 Kiro 為準並回報 P1。

### 2.9 `ResearchPlan`（Planner 輸出）

evidence-contracts.md 未定義欄位。P3 目前採用：

`plan_version` `assets` `question_summary` `lookback_days` `required_evidence_types`
`planned_steps`（每步 `step_id` / `tool_operation` / `rationale`）`asset_question_mismatch_warning` `notes`

**這是 P3 的提案，Task 1 有權改寫。** 唯一硬性要求：`tool_operation` 必須是 `ToolRegistry`
允許清單內的既有操作名，Planner 不得自造 provider / host / URL。

### 2.10 其他

`AnalysisRequest`（§2）、`RunContext`、`WorkerResult`（`status` = `completed|partial|failed`、
`evidence_drafts`、`degradation_events`）、`EvidenceDraft`、`RawSourceRecord`、`DegradationEvent`。

## 3. `ports.py` — reasoning 層依賴的 Protocol

```python
class LLMClient(Protocol):
    async def converse_structured(
        self, *, operation: str, messages: list[dict], schema: type[BaseModel],
        max_tokens: int, deadline: float,
    ) -> BaseModel: ...
```

- `deadline` 是 `time.monotonic()` 基準的絕對時間點（非剩餘秒數）。
- 實作端負責 schema 驗證；驗證失敗且 repair 也失敗時丟 typed 例外（見 §4）。

```python
class ToolRegistry(Protocol):
    def operations(self) -> tuple[str, ...]: ...        # 靜態允許清單
    def is_allowed(self, operation: str) -> bool: ...
    async def invoke(self, operation: str, **params) -> object: ...
```

- 靜態設定式，**不得**被執行期取得的內容修改（P3 測試會斷言 ingestion 後清單不變）。

```python
class ConflictExtension(Protocol):
    async def evaluate(self, ledger, indicators, context) -> ConflictExtensionResult: ...
```

`ConflictExtensionResult`：`status`（MVP 恆為 `"disabled"`）、`route`（恆為 `"arbiter"`）、`indicators`（原樣回傳）。

## 4. reasoning 層自有的例外型別

由 `adapters/bedrock.py` 定義並拋出，供 planner / arbiter 判斷是否走決定論 fallback：

| 例外 | 意義 | 上層反應 |
|---|---|---|
| `LLMSchemaError` | 生成 + 一次 repair 後仍無法通過 schema | 走決定論 fallback |
| `LLMTimeoutError` | 超過 stage deadline 或單次 call 逾時 | 走決定論 fallback |
| `LLMUnavailableError` | throttling / 5xx / 模型不可用（含 fallback 模型亦失敗） | 走決定論 fallback |

三者共同基底 `LLMError`。

## 5. `config.py` — reasoning 讀取的設定

| 名稱 | 必要 | 用途 |
|---|---|---|
| `AWS_REGION` | ✅ | boto3 client |
| `BEDROCK_PRIMARY_MODEL_ID` | ✅ | 主要模型 |
| `BEDROCK_FALLBACK_MODEL_ID` | — | 僅限 throttling/availability 降級 |
| `MAX_EVIDENCE_FOR_ARBITER` | — | 預設 30，硬上限 30（§design 9） |
| `LLM_CALL_TIMEOUT_SECONDS` | — | 預設 45，硬上限 45 |

名稱固定，見 evidence-contracts.md §14。`run_config.json` 只記存在與否的布林值，不記值。
