# S0 — 服務可用性 Preflight 紀錄（P2 驗證）

> 對應 `Implementation-Plan.md` S0 / `.kiro` Task 0。本檔記錄**真的跑過**的事實，非計畫。
> 🚫 不含任何金鑰/token/憑證值。

- **紀錄者：** P2（資料/證據）
- **日期：** 2026-08-01（UTC）
- **Region：** `us-west-2`

## 1. Amazon Bedrock（全案最高風險項）— ✅ PASS

| 項目 | 值 | 結果 |
|---|---|---|
| Primary model ID | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | ✅ 成功回應 |
| Region | `us-west-2` | ✅ |
| 呼叫方式 | boto3 `bedrock-runtime` `invoke_model`（Anthropic Messages body） | ✅ |
| 憑證 | Bedrock API 金鑰（`AWS_BEARER_TOKEN_BEDROCK`；EC2 上改 IAM 角色） | ✅ |
| 驗證工具 | `python bedrock_smoke.py` → `[OK]`；`python run_agent.py BTC` → 10 篇新聞抽出 30 筆結構化事實 | ✅ |
| Fallback model | `BEDROCK_FALLBACK_MODEL_ID`（選用，未設；不阻塞 Bronze/Silver） | — |

> **結論：專案史上第一次真實 Bedrock 呼叫已由 P2 驗證成功。** 原「最大未爆彈」已拆除。
> 曾遇 `ResourceNotFoundException: model version has reached end of life`（舊 `claude-3-5-haiku-20241022` 已下架），改用現役 Haiku 4.5 即通。

## 2. 研究/資料來源可用性（只探測可用性，🚫 不記 token/header）

| 來源 | 類型 | 金鑰 | 結果 |
|---|---|---|---|
| 主辦 Daily OHLCV CSV | market | — | ✅ 隨映像打包 |
| Binance spot / OKX spot | market | 免 | ✅ 五幣皆可 |
| Binance Futures 資金費率 | market(衍生品) | 免 | ✅ |
| CoinGecko snapshot | market | 免 | ✅（Future Work 級） |
| 第一手新聞 RSS（CoinDesk / The Block / Bitcoin Magazine / CryptoSlate / Decrypt / Cointelegraph / NewsBTC / Bitcoinist / CoinJournal） | news | 免 | ✅ |
| Google News（依幣種搜尋） | news(聚合) | 免 | ✅ 五幣皆有覆蓋 |
| Reddit r/CryptoCurrency（Atom feed） | social | 免 | ✅ 住宅 IP；資料中心 IP 會 403（降級揭露） |
| Alternative.me Fear & Greed | social | 免 | ✅ |
| CryptoPanic | news | 免費 token | ⏸ 需 token（未設則停用、降級揭露） |

**指定 baseline research source（Silver 前需定）：**
免 key 且五幣覆蓋 → **第一手新聞 RSS + Google News 依幣種搜尋** 為已驗證基準；
CryptoPanic 為 spec 原訂選項，取得 token 後可升為主。

## 3. 工具版本

| 工具 | 版本 | 備註 |
|---|---|---|
| Python | 3.11.8（開發）/ **3.12（容器 `python:3.12-slim`）** | spec 要求 3.12，映像已用 |
| Docker | 28.4.0 | ✅ 已安裝（`p2-etl-mvp/Dockerfile`） |
| AWS CLI | 未安裝 | 用 Bedrock 金鑰/IAM 角色，CLI 非必要 |

## 4. 重申 Future Work（本階段不做）

Platinum 能力、CoinGecko 深用、五幣完整矩陣、H3 辯論、S3、CloudWatch、ECS
＝ **賽後 Future Work**，不阻塞 Bronze/Silver/Gold。

## 5. 待辦（本檔尚未涵蓋、屬他人階段）

- 正式 `.env.example` 位置由團隊統一（本 repo 另附 `p2-etl-mvp/.env.example` 範本）。
- S0 於計畫指派給「任務 D」；此次 Bedrock 由 P2 驗證，請團隊據此更新 S0 狀態，避免重工。
