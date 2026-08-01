# HOYA BIT 加密市場資料來源 HTML 指南設計

> 狀態：已核准，待實作規劃  
> 日期：2026-07-30  
> 交付形式：可離線開啟的單一 `index.html`

## 1. 目標

建立一份繁體中文的單頁技術文件，整理 HOYA BIT 可使用的加密貨幣資料來源、API 使用方法、UTC CSV 規格，以及 Agent 使用第三方資料時必須遵守的判斷限制。

頁面必須能直接以瀏覽器雙擊開啟，不需要安裝套件、啟動伺服器或設定環境變數。它同時應適合：

- 開發人員查閱 API 與欄位對應。
- 團隊成員快速比較免費、有限免費及付費資料源。
- 比賽展示時說明資料取得方式與合規邊界。
- 透過瀏覽器列印或另存為 PDF。

## 2. 非目標

- 不在頁面內直接呼叫即時 API。
- 不儲存、驗證或管理 API Key。
- 不提供交易訊號、投資建議或第三方市場結論。
- 不建立後端、資料庫、登入或使用者狀態。
- 不使用外部 UI 框架、CDN、字型或圖表套件。

## 3. 交付與架構

交付物為單一 `index.html`：

- HTML 負責語意結構與內容。
- CSS 全部置於頁面的 `<style>`。
- JavaScript 全部置於頁面結尾的 `<script>`。
- 不引用外部 CSS、JavaScript、圖片或字型。
- 外部網路只存在於使用者主動點擊的官方文件連結。

JavaScript 的責任僅限：

- 平滑定位到文件章節。
- 顯示目前閱讀章節。
- 複製 API 或 CSV 範例。
- 複製失敗時選取程式碼，供使用者手動複製。

## 4. 資訊架構

頁面依序包含下列章節：

1. 頁首與使用限制摘要。
2. 建議資料組合。
3. 價格與市場 API。
4. 新聞與官方公告。
5. 社群情緒。
6. 鏈上資料。
7. 免費與付費方案比較。
8. API 使用範例。
9. UTC CSV 欄位及範例。
10. Agent 判斷流程與禁止事項。
11. 官方文件與來源連結。

### 4.1 頁首

頁首顯示：

- 「HOYA BIT 加密市場資料來源指南」。
- 最後更新日期。
- 文件用途。
- 非投資建議聲明。
- 核心限制：第三方服務產生的市場判斷、交易訊號或投資報告，不得直接作為主要分析結果。

### 4.2 建議資料組合

提供一組低成本、可實作的來源建議：

- Binance 作為 `BTCUSDT` UTC 日 K 主來源。
- Coinbase `BTC-USD` 與 OKX `BTC-USDT` 作為交叉驗證。
- CoinGecko 作為聚合市場背景。
- CryptoPanic、媒體 RSS 與官方公告作為新聞來源。
- Reddit、LunarCrush、X 作為社群資料來源，並揭露使用限制。
- Etherscan V2、Solana RPC、Dune 作為鏈上資料來源。
- CoinDesk Data、The Block、Glassnode、Solscan Pro 作為可選付費來源。

### 4.3 來源分類

每個來源至少顯示：

- 名稱。
- 資料類別。
- 存取方式。
- 是否需要 API Key。
- 免費、有限免費、付費或不建議作正式 API 的狀態。
- 適合用途。
- 主要限制。
- 官方文件連結。

必須特別標示以下現況：

- CryptoCompare Min API 已 deprecated，現行平台為 CoinDesk Data。
- CoinDesk Data 免費 API 層已終止。
- Yahoo Finance 沒有目前受支援的正式公開 Finance API。
- Glassnode 免費帳戶不包含正式 API 或 CSV 下載。
- X API 採按使用量計費。
- Solscan 的完整 API 主要是付費服務。

## 5. API 使用範例

文件提供可複製的靜態範例，不直接執行請求。

至少包含：

- Binance `/api/v3/klines`，示範 `interval=1d`、`timeZone=0` 及 UTC 起訖時間。
- OKX `/api/v5/market/history-candles`，示範 `bar=1Dutc` 與 `confirm=1`。
- CoinGecko 市場歷史或 OHLC 端點，說明它適合聚合背景，不應取代交易所開盤價。
- CryptoPanic v2 新聞端點與 `YOUR_API_KEY`／`AUTH_TOKEN` placeholder。
- Etherscan V2 使用 `chainid` 的示例。

每個範例需說明：

- 端點用途。
- 必要參數。
- 回傳資料中開盤時間或 Open 的位置。
- 是否需要 Key。
- 如何轉為 `YYYY-MM-DD` UTC CSV。

真實 API Key 不得出現在文件中。所有示例使用 `YOUR_API_KEY` 或 `YOUR_AUTH_TOKEN`。

## 6. CSV 規格

對外最低交付格式：

```csv
date_utc,open
2026-07-29,12345.67
```

內部可稽核格式：

```csv
date_utc,asset,pair,venue,open,is_final,candle_open_utc,source,retrieved_at_utc
```

規則：

- `date_utc` 使用 `YYYY-MM-DD`。
- `candle_open_utc` 對應 `00:00:00Z`。
- 只輸出已完成的日 K。
- 保留 `asset`、`pair` 與 `venue`，避免混用 `BTC-USD` 與 `BTC-USDT`。
- 數值使用小數點且不加千分位。
- 原始 JSON、請求參數與取得時間應在實際資料流程中另行保存。

## 7. Agent 判斷限制

頁面使用醒目區塊說明：

- CryptoPanic 的 bullish、bearish、panic score 只可作輔助特徵。
- LunarCrush 的 Galaxy Score、AltRank 與 sentiment 不得單獨觸發結論。
- CoinCap TA、Glassnode Insights、Dune dashboard 作者結論及媒體分析不得直接成為主要結果。
- 每個重要結論至少由兩種獨立資料類別佐證。
- Agent 必須自行計算報酬、波動、成交量變化、跨市場價差、事件數及鏈上變化。
- 最終報告揭露來源、時間、計算規則、支持與反對證據。
- 頁面說明可稽核的判斷摘要，不要求或呈現模型私有的逐步思考內容。

流程圖以純 HTML/CSS 表示：

`原始資料 → UTC 正規化 → 去重與驗證 → 自行計算特徵 → 多來源佐證 → 結論與限制`

## 8. 視覺設計

採技術文件儀表板風格：

- 深藍灰背景。
- 青綠色作為主要重點色。
- 黃橙色顯示警告。
- 紅色只用於禁止或高風險事項。
- 使用狀態文字搭配顏色，不以顏色作為唯一識別。
- 卡片呈現快速摘要，表格呈現詳細比較。
- 程式碼區塊使用系統等寬字型。

桌面版提供固定側邊章節導覽。小螢幕將導覽轉為頂部橫向章節列；寬表格放入可水平捲動容器。

## 9. 無障礙與安全

- 使用正確的標題層級、`main`、`nav`、`section` 與表格標題。
- 互動元素可使用鍵盤操作，並提供清楚的焦點樣式。
- 複製按鈕提供可理解的文字與狀態回饋。
- 外部連結清楚標示為官方來源，使用新分頁開啟並設定安全的 `rel`。
- 不使用 Cookie、Local Storage、追蹤碼或第三方腳本。
- 不將任何祕密資訊放入 HTML。

## 10. 列印設計

`@media print` 必須：

- 改為白底黑字。
- 隱藏導覽、複製按鈕及非必要裝飾。
- 保留外部連結文字。
- 避免卡片或程式碼區塊被不合理分頁。
- 讓表格在 A4 直式頁面上保持可讀。

## 11. 錯誤與降級處理

由於頁面不發送 API 請求，不存在網路資料錯誤。唯一互動錯誤是剪貼簿 API 可能因本機檔案權限或瀏覽器限制而失敗。

處理方式：

1. 優先使用 `navigator.clipboard.writeText`。
2. 不可用或失敗時，自動選取相應的 `<code>` 內容。
3. 顯示「請按 Ctrl/Cmd+C 手動複製」訊息。

JavaScript 停用時，全部內容與範例仍須可閱讀，只有章節提示和複製按鈕失去功能。

## 12. 驗收條件

- `index.html` 可直接雙擊開啟。
- 沒有外部 CSS、JavaScript、字型或圖片依賴。
- 所有章節內容在 JavaScript 停用時仍可閱讀。
- 桌面與手機寬度下沒有內容溢出或不可讀問題。
- 章節連結、目前章節提示與複製按鈕正常。
- 複製失敗時能選取程式碼並提示手動複製。
- 列印預覽為白底、隱藏導覽與互動控制。
- 所有 API Key 都是 placeholder。
- 每個資料來源具有狀態、用途、限制與官方連結。
- 頁面明確區分 `BTC-USD`、`BTC-USDT` 與聚合價格。
- 頁面明確陳述第三方訊號不得作為唯一或主要判斷。
- HTML 通過可用的結構與語法檢查。

