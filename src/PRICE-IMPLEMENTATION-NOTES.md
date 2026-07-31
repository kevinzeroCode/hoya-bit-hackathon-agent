# `src/` — 價格計算與分析技能

> 本文記錄 2026-08-01 該次工作階段所建立的內容：`src/calc/`（決定性價格計算）
> 與 `src/skills/`（產出 A1–A5、A7、A9 報告段落的分析技能）。
>
> 起點是 `docs/price-data-analysis-outputs.html` 所列的十項分析產出。
> 本階段實作其中七項，並在過程中發現該文件本身的若干標示問題（見 §5）。

---

## 1. 現況總覽

| 項目 | 數量 |
|---|---|
| 模組 | 18 個 `.py`（約 2,700 行） |
| 測試 | 329 個，全數通過 |
| Ruff | 無錯誤 |
| 外部相依 | 僅 `pandas` / `numpy`（測試另需 `pytest`） |

所有程式碼皆為**決定性**：不呼叫模型、不連網、`calc` 層不做任何 I/O。
相同輸入與相同 `as_of` 可完整重現同一份輸出。

執行方式：

```bash
python -m pytest -q          # 全部測試
python -m ruff check src tests
```

`pytest.ini` 以 `pythonpath = src` 讓套件可被匯入。
**待處理**：Task 1 建立 `pyproject.toml` 後，此設定需與 editable install 一併重新檢視
（見 §7）。

---

## 2. `src/calc/` — 決定性價格計算

純函式，輸入為 `pandas.Series`（以 `DatetimeIndex` 為索引），
輸出一律為**分數**（`-0.074` 表示 -7.4%），百分位為 `0..1`。

| 檔案 | 內容 |
|---|---|
| `percentile.py` | `expanding_percentile` — 共用的排序基元 |
| `indicators.py` | 單一資產：報酬、波動、位置、參與度、事件、門檻 |
| `cross_asset.py` | 雙資產：相關性、beta、相對強弱、離散度 |
| `data_quality.py` | OHLCV 完整性驗證 |
| `analogs.py` | 條件基準率引擎（本階段後段新增，供 A7 使用） |

### 為何 `expanding_percentile` 獨立成一個模組

`docs/price-data-analysis-outputs.html` §5.1 指出的唯一正確性陷阱：
以**全樣本**計算百分位，會讓 `analysis_as_of` 之後的 K 線影響該時點的排名。
波動百分位、量能百分位、區間位置、相對強弱百分位全部依賴同一個排序動作，
因此只實作一次，其餘全部呼叫它。

有一個測試專門守住這件事：擴張視窗與全樣本排名**只在最後一根 K 線相同**，
其餘每一點都不同——若只在最新 K 線驗證，一個錯誤實作會看起來完全正確。

### `analogs.py` 的三項約束

1. **重疊視窗不是獨立樣本。** 每日評估的 30 日條件會產生約 330 個觀測，
   但其中的獨立區間遠少於此。`EpisodeCount` 同時回報三個數字：
   `observations`（美化後的數量）、`distinct_episodes`（連續區段合併）、
   `effective_n`（`observations / horizon`，最保守者）。三者一律同行輸出。
2. **不輸出機率。** 結果為 `strong|moderate|weak|unavailable` 加原始計數。
   強度取自「距 50/50 的距離」而非原始比率——20% 與 80% 資訊量相同，50% 則無資訊。
   獨立區間數低於門檻時不給任何強度判定。
3. **條件門檻不得使用未來資料。** 預設 `mode="expanding"`；
   `mode="full_sample"` 保留供回溯對照，並會在自身 limitations 中揭露前視偏誤。

---

## 3. `src/skills/` — 分析技能

每個技能的介面一致：`run(bundle) -> SkillResult`。

```python
from skills import load_bundle, build_report

bundle, load_report = load_bundle("HOYA_BIT_crypto_market_dataset/data", "BNB")
report = build_report(bundle)
print(report.markdown)          # 繁體中文報告
print(report.statuses)          # {'A1': 'degraded', ..., 'A9': 'degraded'}
```

單獨執行某一項：

```python
from skills import a5_attribution
result = a5_attribution.run(bundle)
result.findings                 # 結構化數值
result.evidence_refs            # 每個數字的來源
result.limitations              # 無法確定的部分
result.section_markdown         # 可直接併入報告的段落
```

### 支撐檔案

| 檔案 | 職責 |
|---|---|
| `base.py` | `SkillResult` / `EvidenceRef` / `MarketBundle` 契約與格式化輔助 |
| `lint.py` | 投資建議字串檢查（最後一道防線） |
| `dataset.py` | 讀取 CSV、驗證完整性、依 `as_of` 切片（**唯一**碰檔案系統的模組） |
| `report.py` | 組裝完整繁中文件 |

### 七項技能

| ID | 名稱 | 主要依賴 | 降級行為 |
|---|---|---|---|
| A1 | 市場體制標籤 | `volatility_percentile`、`multi_horizon_returns`、`range_position` | < 252 根 K 線 → `unavailable` |
| A2 | 價格位置與趨勢快照 | `distance_from_ma`、`all_time_high_stats` | **逐指標**降級（MA200 缺失不影響 MA20） |
| A3 | 波動與風險輪廓 | `realized_volatility`、`atr`、`return_distribution` | < 31 根 → `unavailable`；百分位可單獨缺失 |
| A4 | 參與度與流動性 | `volume_mean_ratio`、`price_volume_cross` | < 365 根 → 改用 90 日基準並揭露 |
| A5 | 單幣 vs 全市場歸因 | `rolling_correlation`、`rolling_beta`、相對強弱 | 無基準或標的即基準 → `unavailable` |
| A7 | 歷史類比基準率 | `calc.analogs` | 獨立區間不足 → `unavailable` |
| A9 | 跨來源驗證與衝突旗標 | `zscore_anomalies` | **恆為 `degraded`**（見 §6） |

### 兩條跨技能鐵則

- **技能不拋例外。** 資料不足是要回報的結果，而非例外。
  已對 0／1／5／40／300 根 K 線的輸入測試全部七項技能。
- **技能不編造數字。** 無法計算的欄位直接缺席，並由 limitations 說明原因。

`report.py` 另有一層防護：若某個技能違反契約而拋出例外，
該項標為 `unavailable`，其餘六項仍照常產出。

---

## 4. 已釘住的計算慣例

以下慣例各自只有一種選擇能重現文件中的數值，因此都有測試守住。
任何一項被無聲更改，都會有測試失敗：

| 項目 | 採用 | 若改用其他做法 |
|---|---|---|
| 波動年化 | `sqrt(365)` | `sqrt(252)` 會讓 BTC 從 25.0% 變成 20.8% |
| ATR14 | 簡單滾動平均 | Wilder 平滑會讓 BTC 從 1,718.77 變成 1,839.34 |
| 偏態／峰態 | 對數報酬 | 簡單報酬會讓 XRP 偏態從 1.36 變成 2.92 |
| z-score | 已減去平均數 | 未減平均會讓 SOL 的 3σ 日數從 22 變成 23 |
| 百分位 | 擴張視窗 | 全樣本會引入前視偏誤 |

---

## 5. 對照原始文件時發現的問題

以實際 CSV 驗證 `docs/price-data-analysis-outputs.html` 的每一個數值時，
**計算本身正確，但四處標示與數字不相符**。四項皆已在測試中釘住正確值：

| 文件敘述 | 實際重現該數字的方法 |
|---|---|
| 「距 ATH **收盤** … −41.6%」 | −41.62% 是距**盤中最高價**；距最高收盤為 −40.90% |
| 「30日量均÷365日量均：0.74（第 **2** 百分位）」 | 第 2 百分位是 **30 日量均**的排名，非該比值的排名（比值為第 43） |
| 「相對 BTC 比值的 **1 年**百分位」 | 需以 **365** 根 K 線為視窗；252 根會讓 ETH 從第 13 變成第 0.8 |
| XRP MA200 −19.4% | SMA200 實得 **−19.10%**（其餘四檔與 SMA 完全相符，研判為謄寫誤差） |

另有一項在任何視窗定義下皆無法重現：
A4 價量交叉的量能變動（文件 BNB +35.3%，本實作定義為 +36.84%）。
因此該測試改為驗證**方向與價格側**，並在測試中註明原因。

### A7：誠實版本的結論比文件更弱

文件所載的 A7 基準率使用**全樣本**五分位界定條件——
正是同一份文件 §5.1 所禁止的前視偏誤。改用擴張視窗後，結論明顯轉弱：

| | 全樣本（文件） | 擴張視窗（本實作預設） |
|---|---|---|
| BTC 波動擴張 | 77.3% | 70.0% |
| 方向（五檔） | 51.5–61.4% | 48–54% |

方向項在誠實模式下對 BTC 與 ETH **低於五成**，實質上就是擲硬幣。
`expanding` 為預設值，因此**代理人的 A7 輸出預設不會與文件數字相符**——這是刻意的。
有測試針對五檔資產各自驗證「擴張視窗的波動比率必定低於全樣本」，
確保兩者的差距（即前視偏誤的大小）保持可見，不會被逐步調成一致。

---

## 6. 刻意的設計選擇

**A1 目前對五檔中的四檔回報 `degraded`。** 這不是缺陷。
§16.3 的標籤列舉對波動區間的**頂端**有名稱（`high_volatility`），對**底端**沒有。
因此當偵測到壓縮時，技能照常輸出規格標籤，另外揭露壓縮狀態，
並標記 `degraded` 且說明列舉無法表達此資訊。
是否新增標籤屬規格層決策，未在此擅自變更。

**投資建議檢查採「失敗即擋」，嚴格到會擋下自己的免責聲明。**
「本文不含任何投資建議」也會被擋，因為檢查是單純的子字串比對。
處理方式是改寫報告結尾為「不對任何交易或決策提供指引」，而非放寬規則——
一個試圖分辨「陳述」與「否定該陳述」的檢查，就是一個可以被說服放行的檢查。
有測試明確記錄此行為為刻意設計。

**A9 恆為 `degraded`，永遠不會是 `ok`。**
本專案目前沒有任何研究來源，未經驗證的分析不得以已驗證的樣貌呈現。
`sources` 參數已預留，日後研究分支接上時介面不需改變。

**A5 對 BTC 回報 `unavailable`。**
基準與自身的相關性恆為 1，屬同義反覆，因此拒絕輸出而非印出該數字。

**`src/skills/` 獨立於 `src/hoya_agent/`。**
CLAUDE.md 將 Task 1（`models.py`）與 Task 2 保留給 Kiro，
因此本階段不建立 `EvidenceItem` / `Claim` 型別，也不佔用該路徑。
`EvidenceRef` 僅承載日後對應到真正 `EvidenceItem` 所需的原始素材
（缺 `fetched_at`／`content_hash`／`independence_group`），使該對應保持機械式轉換。

---

## 7. 已知待辦與未涵蓋範圍

**待辦**

- `pytest.ini` 的 `pythonpath = src` 需與 Task 1 的 `pyproject.toml` 調和；
  屆時 `src/calc/` 與 `src/skills/` 需決定是維持獨立，或併入 `src/hoya_agent/`
  （`calc/indicators.py` 與 Task 4 的 `data/indicators.py` 存在重疊）。
- 資料集若擴充（目前 1,826 根 K 線／約 5 年），
  `history_bars`／`history_years` 會自動反映，程式不需更動；
  但綁定於 1,826 根視窗的黃金值測試會失敗——那正是基準改變的正確訊號。

**本階段未建立**

- A6（事件時間軸）、A8（量化失效條件）、A10（覆蓋率揭露）——依指示排除。
- `EvidenceItem` / `Claim` 型別、artifact 寫入、任何 LLM 呼叫。
- A9 的實際跨來源驗證（需研究 adapter 與 evidence ledger）。

**資料本身的限制（會傳遞到所有輸出）**

- 1,826 根 K 線僅涵蓋單一市場循環，所有基準率均以該單一路徑為條件。
- 各資產的歷史長度意義不同：五年之於 BTC 是樣本，之於 SOL 幾乎是全部生命週期。
- `open` 實質冗餘（每列等於前一列 `close`，最大偏離 0.101%，僅 SOL 有 2 列超過 0.1%），
  唯一實質用途是序列連續性驗證。
