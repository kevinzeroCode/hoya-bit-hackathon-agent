# CLAUDE.md — P2 資料/證據 ETL (HOYA 加密市場分析 AI Agent)

> 這是 **P2(Data/Evidence)** 的 ETL/資料處理工作區,獨立於主 repo。
> **權威規格**在主 repo：`../hoya-bit-hackathon-agent/.kiro/`（specs + steering）與其根目錄 `CLAUDE.md`。
> 本檔與主規格衝突時，以主 repo 的 `.kiro/specs` 與 `.kiro/steering` 為準。
> 主辦資料集：`../hoya-bit-hackathon-agent/HOYA_BIT_crypto_market_dataset/data/{ASSET}_daily_ohlcv.csv`

## 專案一句話
現場接收「指定幣種 + 未知題目」後 15 分鐘內，整合多源資料，產出**可回溯、會誠實揭露限制**的繁體中文加密市場分析。我（P2）負責**資料取得 → 正規化 → 證據化**，不做判斷。

## 我的範圍（P2：Task 4 + Task 5）
- **Task 4 市場資料**：`indicators.py`、`market_series.py`、`adapters/organizer_csv.py`、`adapters/binance.py`、`market_worker.py`
- **Task 5 研究/證據**：`adapters/cryptopanic.py`、`rss.py`、`alternative_me.py`、`official.py`、`evidence/policies.py`、`ledger.py`、`processor.py`
- **越界紅線**：❌ 不寫 Renderer、❌ 不做 Bedrock/LLM reasoning、❌ 不自行合併 shared contract（models 由 P1 定，有需求跟 P1 提）。

---

## 鐵則（違反 = 直接丟分）
1. **我的程式碼完全不碰 LLM。** 所有市場數值只能來自 deterministic 工具；不得補值/猜值。
2. **證據可回溯**：每筆 Evidence 要能溯源；LLM 產物永遠不是證據來源。
3. **Evidence 無立場**：`supports|opposes|neutral` 只存在 Claim-Evidence Link（那是 Arbiter 端，不是我）。
4. **reliability 用靜態表**（見下），不由任何模型動態調整。
5. **幣種無關**：pipeline 以 `{asset}` 為參數，五幣共用一條路徑；禁止 per-coin 分支/特調。
6. **秘密**：API token / 憑證不得進 log / artifact / repo。
7. schema 用 **Pydantic v2 + `extra="forbid"`**；欄位名在 Python/JSON/prompt/fixture/test 完全一致。

## 支援幣種
`BTC | ETH | SOL | BNB | XRP`（現場才抽，任一都可能中）。

---

## 可用資料來源（主辦工作坊認證）
| 類型 | 來源 | MVP 取捨 |
|---|---|---|
| 市場基準 | 主辦 Daily OHLCV CSV（UTC） | ✅ 必做 |
| 市場 live | **Binance Public API**（`{ASSET}USDT`，免 key） | ✅ baseline |
| 市場其他 | CoinGecko / CryptoCompare / CoinCap / Yahoo Finance | ⏸ CoinGecko=Future Work |
| 新聞 | **CryptoPanic**（依 currency 過濾，免費 token）、CoinDesk / The Block / Decrypt RSS | ✅ CryptoPanic + 1 RSS |
| 社群 | Reddit（用 r/CryptoCurrency 這種幣種無關的）、LunarCrush | ⏸ 選做 |
| 情緒 | **Alternative.me Fear & Greed**（免 key，全市場） | ✅ 必做 |
| 鏈上 | Etherscan / Solscan / BscScan / Dune / Glassnode 免費層 | ⏸ 選做，且**只用單一多鏈聚合來源，不為五條鏈各寫一套** |

**幣種無關原則**：只有「用幣種符號就能查五幣」的來源進 MVP；「每個幣要各寫一套」的（各鏈瀏覽器、各專案官方 Blog）一律 best-effort 或跳過，缺漏誠實揭露。

**重要限制**：不得把第三方已產出的完整判斷 / 交易訊號 / 投資報告直接當結果——我只做取得＋正規化＋證據化。

---

## 市場資料規則
- 只用 `analysis_as_of` 前**已完成**的 UTC 日 K；當日未完成 → intraday snapshot 另計，不與完整日 K 混用。
- 主辦 CSV 來源名 `public_market_data`、獨立群 `organizer-public-market-data`，**不得推定其為 Binance 或任何交易所**。
- CSV 迄 **2026-05-31**；跨到 live 以 **2026-06-01** 為來源切換點並揭露差異。
- **禁止跨幣直接比較 base-asset volume**（單位不同）。跨幣只用：報酬 / 波動 / 相對變化 / 各自 rolling z-score / quote(USD) volume。
- 缺 bar 就標 unavailable，**不得 forward-fill** 硬湊指標。
- 保留完整精度，只在呈現時 round。

## Evidence 規則（做 processor / policies 用）
`EvidenceItem` 至少含：`source_name`、`source_url`、`fetched_at`、`published_at`（可 null 但要揭露）、`content_reference`、`normalized_fact`、`reliability`、`independence_group`、`content_hash`、cache/stale。（命題硬性四欄：source、fetched_at、content_reference、related_claim）

**靜態 reliability 表**（不得由模型調整）：
| reliability | 適用 |
|---|---|
| `high` | 主辦 OHLCV、交易所 API 市場數據、已驗證官方公告、由 high-reliability 輸入算出的 deterministic 計算 |
| `medium` | 具名原始新聞頁（有 URL + 時間） |
| `low` | 聚合/轉載未取原頁、Fear&Greed、社群、缺作者/時間、二手評論 |

**independence group**（依序）：① 原始發布者 ② 原始 URL 註冊網域(小寫去 www) ③ provider ID。轉載與原文同群。CryptoPanic 有原始發布者就用其網域，否則 `cryptopanic.com`。
**去重**：只合併 SHA-256 完全相同的 `content_hash`，不做語意/近似相似度。
**material conflict**（deterministic）：同一 claim 同時有 supports 與 opposes、雙方 reliability≥medium、且來自不同 independence group。

---

## 技術棧 & 測試
- Python 3.12、Pydantic v2、`httpx.AsyncClient`、`pandas`、`pytest` + `pytest-asyncio`。
- **TDD**：先寫會失敗的聚焦測試 → 最小實作 → 跑測試 → 綠了才 commit。
- 預設 `pytest` **絕不碰外網**；adapter 用 `httpx.MockTransport` + fixture 測；live 只手動 rehearsal。
- 每個 adapter 契約測試：成功 / timeout / 429 / 5xx / malformed / 空資料。
- 單次 call ≤ 45 秒、最多 retry 1 次、共用 stage deadline；用 fake clock 測，不真的 sleep。
- 指標用 golden fixture（手算 mini 序列 + 下方真實 golden 值）。

## 指標 golden 值（真實資料，截至 2026-05-31；供回歸測試）
| Asset | close | return_14d | realized_vol_30d(日) | max_drawdown_90d |
|---|---:|---:|---:|---:|
| BTC | 73674.39 | -0.048843 | 0.013045 | -0.118499 |
| ETH | 2007.01 | -0.058184 | 0.014900 | -0.170314 |
| SOL | 82.44 | -0.032848 | 0.020598 | -0.179418 |
| BNB | 710.55 | +0.094029 | 0.024817 | -0.141516 |
| XRP | 1.333 | -0.048944 | 0.017913 | -0.152560 |
> 定義：`return_14d = close[T]/close[T-14]-1`；`realized_vol_30d` = 近 31 根收盤日報酬(pct_change)樣本標準差(ddof=1)；`max_drawdown_90d` = 近 90 根 `close/cummax-1` 最小值。以 `pytest.approx` 比對。

---

## MVP 功能清單（P2；🟢現在可做 / 🔴等 P1 models）
**Task 4**
- [ ] 🟢 `indicators.py`：報酬 / realized vol / max drawdown / volume z-score / 相對變化（golden 測）
- [ ] 🟢 `market_series.py`：CSV 載入 / UTC / 排除未完成日 K / 來源切換
- [ ] 🟢 `adapters/organizer_csv.py`：讀 CSV + 驗證 + 來源標記
- [ ] ⚠️ `adapters/binance.py`：klines + 24hr ticker（MockTransport 測）
- [ ] 🔴 `market_worker.py`：整合 → high-reliability EvidenceDraft（不呼叫 LLM）

**Task 5**
- [ ] 🟢 `evidence/policies.py`：靜態 reliability 表 + independence group + confidence caps
- [ ] ⚠️ `adapters/cryptopanic.py`（baseline）/ `rss.py` / `alternative_me.py`
- [ ] ⏸ `adapters/official.py`（best-effort）
- [ ] 🔴 `evidence/processor.py`：正規化 / SHA-256 去重 / 獨立性 / 衝突 / 排序 / 截前 20~30
- [ ] 🔴 `evidence/ledger.py`：Ledger 操作 + 穩定 ID

**建議起手式**：先做 `indicators.py` + golden 測試（🟢 零依賴，不卡 P1）。

## 對接
- 跟 **P1** 要 `models.py`：EvidenceItem / EvidenceDraft / MarketBar / SourceResult / WorkerResult 欄位（卡住 🔴 兩項）。
- 跟 **P3** 對齊 `EvidenceDraft` 格式（他的 Research Agent 產同格式，一起進 processor）。
