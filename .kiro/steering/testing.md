---
inclusion: always
---

# Testing Steering

本文件是 HOYA Market Agent 的強制測試規則。目標不是追求測試數量，而是在四位 junior、兩天的限制下，優先保護競賽會直接檢查的證據可追溯性、deadline、降級與四項 artifacts。

## 1. 必守流程

所有 required 任務採用 Red -> Green -> Refactor：

1. 先新增一個只描述單一行為的測試。
2. 執行精確測試節點，確認因缺少該行為而失敗，不得因 import、fixture 路徑或語法錯誤失敗。
3. 寫最小實作讓精確測試通過。
4. 執行該模組測試，再執行受影響的 integration tests。
5. `ruff check .` 與 required test suite 通過後才 commit。

不得先大量產生實作再補測試。修 bug 時必須先加入能重現問題的 regression test。

## 2. 測試分層

| 層級 | 位置 | 網路 | 用途 | Required gate |
|---|---|---|---|---|
| Unit | `tests/unit/` | 禁止 | schema、指標、deadline、Evidence Processor、renderer、lint | 每次 commit |
| Contract | `tests/contract/` | 禁止 | httpx adapter request/response、Bedrock client、錯誤正規化 | adapter／LLM commit |
| Integration | `tests/integration/` | 禁止 | fixture vertical slice、fork-join、partial result、四項 artifacts | 每次合併 |
| Acceptance | `tests/acceptance/` | 預設禁止 | 五幣矩陣、run modes、13 分鐘交付門檻 | Day 2 freeze 前 |
| Live rehearsal | `tests/live/` | 明確 opt-in | 真實 API、Bedrock、Binance／CSV overlap、部署 smoke | 手動執行三次 |

預設的 `python -m pytest` 絕對不能存取外網。Live tests 必須同時具有 `@pytest.mark.live` 與 `RUN_LIVE_TESTS=1` 防護，缺少任一條件時應 skip。

## 3. 固定指令

開發者在 repository root 執行：

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit tests/contract tests/integration -q
python -m pytest tests/acceptance -m "not live" -q
ruff check .
```

精確 Red/Green cycle 使用完整 node ID，例如：

```bash
python -m pytest tests/unit/test_models.py::test_official_request_freezes_analysis_as_of -vv
```

Live rehearsal 只能手動開啟：

```powershell
$env:RUN_LIVE_TESTS = "1"
python -m pytest tests/live -m live -vv -s
```

CI gate：

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
```

## 4. 決定性與時間

- 所有 datetime 使用 timezone-aware UTC；禁止在 assertion 中直接依賴本機時區。
- `official` mode 的 `analysis_as_of` 由注入的 clock 在 run 開始凍結；測試使用 fixed clock，不 patch 散落的 `datetime.now()`。
- `rehearsal` 與 `demo` 可傳入固定 `analysis_as_of`，以支援重現。
- Daily OHLCV 只允許 `analysis_as_of` 前已完成的 UTC K 線；未完成日 K 只能作為標示清楚的 intraday snapshot。
- 指標 golden fixture 必須包含可手算的 close/volume 序列與明確 expected values；浮點 assertion 使用 `pytest.approx` 並指定容許誤差。
- 測試不得依賴執行順序、真實系統時間、隨機 UUID 或先前 run 目錄；run ID 與 artifact root 皆由 fixture 注入。

## 5. 外部服務測試

- httpx adapters 使用 `httpx.MockTransport`，驗證 endpoint、query parameters、UTC range、timeout 與 response mapping。
- Bedrock 使用 fake `LLMClient` 或 botocore `Stubber`，不得在 unit／contract／integration tests 呼叫真實模型。
- 每個 adapter 至少覆蓋：成功、timeout、HTTP error、malformed payload、空資料。
- adapter timeout 上限為 45 秒且最多 retry 一次；測試以 fake sleeper/clock 驗證，不真的等待 45 秒。
- schema repair 最多一次且共用原 stage deadline；測試必須驗證第二次失敗後進入 deterministic fallback。
- API token、AWS credentials、完整 prompt 不得出現在 captured logs、artifacts 或 snapshot。

## 6. 核心契約測試

### AnalysisRequest 與 run modes

- `assets` 僅接受 1 至 2 個、且限 BTC/ETH/SOL/BNB/XRP。
- 題目文字與 `assets` 不一致時以 `assets` 為準並產生 execution warning。
- `official` 禁止 fixture、recorded result 與使用者自訂 `analysis_as_of`。
- `rehearsal` 可使用 deterministic fixtures；`demo` 必須標示 recorded fallback 與原始取得時間。
- `enable_conditional_debate` 預設為 false。

### Evidence 與 Claim

- `EvidenceItem` 必須有 source、URL、fetched time、content reference、normalized fact、reliability、independence group 與 content hash。
- 相同 normalized source content 僅保留一筆；同一原始發布者的轉載不得被計為不同獨立來源。
- reliability 僅依靜態表，不由 LLM 動態調高。
- conclusion 必須有 supporting link，否則 `insufficient_data=true`。
- inference/conclusion 必須可經 `based_on_claim_ids` 回溯到 fact，且不得循環或引用不存在的 claim。
- material conflict 僅在同一 claim 同時有不同 independence groups、reliability 至少 medium 的 supports 與 opposes links 時成立。

### 市場數據

- Market Worker 不得呼叫 LLM；所有市場數值來自 deterministic tool output。
- 報酬、波動、drawdown、volume change 與 rolling z-score 使用 golden fixtures 驗證。
- 跨幣不得直接比較 base-asset volume；只允許 quote volume、報酬、波動、相對變化或各自 rolling z-score。
- CSV 與 Binance 的來源切換點、endpoint、pair、參數、UTC range、fetched time 必須進 Evidence／run config。
- Binance／CSV overlap calibration 必須輸出每幣差異結果，不得暗示 CSV 來自 Binance。

### Orchestrator 與 artifacts

- Market Worker 與 Research Agent 必須並行；任一分支 timeout 後，另一分支結果仍進 Ledger。
- stage wall-clock deadline 優先於 per-call timeout；第 12 分鐘取消非必要外部呼叫。
- 跳過順序固定為 H3 -> optional context adapter -> 反方訊號二次搜尋。
- `run_config.json` 在 run 開始存在、`execution_log.jsonl` 串流追加、`evidence.json` 在 Ledger 完成即存在、`final_report.md` 最後寫入。
- Arbiter 失敗仍須產生 deterministic fallback report，且四個固定檔名齊全。
- Execution log 僅記 prompt/schema version，不記 prompt 全文。

### Report 與安全 lint

- Renderer 為 deterministic，輸入僅為 `AnalysisResult` 與 Ledger。
- 繁體中文報告包含 approved spec 6.2 的 11 個段落。
- 市場數值必須能回溯至 Evidence ID；report 不得加入 Ledger 外的新事實。
- 至少呈現一個反方訊號；找不到時列出查詢過的來源與限制。
- 禁止明確買賣或配置用語，包括「建議買入」、「建議賣出」、「加倉」、「減倉」、「做多」、「做空」。
- confidence 僅為 high/medium/low，不得渲染為未校準的精確機率。

## 7. Fixture 與 snapshot 規則

- 小型、人工可讀 fixtures 放在 `tests/fixtures/`；不得把完整競賽資料複製進 test tree。
- HTTP fixtures 保存正規化後的最小 payload，不保存 API key、cookie 或個資。
- Markdown snapshot 僅可用於 deterministic renderer；變更 snapshot 時必須在 commit 說明對應的報告契約改動。
- `tests/fixtures/recorded_demo/` 的內容只能供 `demo` mode，UI 與報告必須顯示 recorded fallback。

## 8. 合併與凍結門檻

Required branch 合併前：

```bash
python -m pytest tests/unit tests/contract tests/integration -q
ruff check .
```

Day 2 功能凍結前：

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
```

並人工確認：

- BTC、ETH、SOL、BNB、XRP fixture matrix 全過。
- 三次 live-source rehearsal 均在第 13 分鐘前產出四項 artifacts。
- timeout、全部外部來源失效、Arbiter schema failure 三個故障注入案例全過。
- Docker smoke、EC2 URL、artifact 下載與 secret scan 全過。

H3、S3、CloudWatch 的測試失敗不得阻塞 MVP；只有 required gates 全綠後才允許開始這些 optional 任務。
