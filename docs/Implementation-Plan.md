# HOYA Market Agent — 實作路線圖（分階段建置計畫）

> **④ of ④ — design-pipeline 最後一份產出。**
> 上一份：[Architecture-FileMap.md](Architecture-FileMap.md)｜索引：[README.md](README.md)
> 無法 headless 驗證的部分收在本文 §3.2，不另立測試指南文件。

> ## 🔴 開 PR 前必做：更新你那個階段的「現況」區塊
>
> **任何動到 `src/`、`tests/` 或 artifact 行為的 PR，都必須在同一個 PR 裡更新本文。**
> 兩個地方，不是一個：① §1.1 現況快照那一列；② 你那個階段的「現況」區塊。
>
> **現況區塊寫「真的跑過的事實」**：實際測試數字（`X passed, Y failed`）、`ruff` 結果、
> 以及**踩過的坑**。最後一項價值最高——S0 記下的三個 Bedrock 陷阱
> （舊 `claude-3-5-haiku-20241022` 已下架、需要 `us.` inference profile 前綴、
> 模型回應被 markdown 圍欄包住導致抽取 0 筆）省掉了後面每個人各撞一次。
>
> **為什麼是硬性規定：** 2026-08-01 半天之內，本文的狀態標記過時了兩次。
> 一次寫著「Bedrock 從未呼叫過，這是最大未爆彈」，其實已經通了；
> 一次寫著「S2 未開始、是關鍵路徑」，其實已經合併。兩次都會讓人**重做已完成的工作**，
> 或**空等一個並不存在的阻塞**。四個人平行開發時，
> **一份存在但過時的狀態表，比沒有狀態表更糟**——沒有的話大家會自己去查，有但過時的話大家會相信它。
>
> 不確定要不要更新就更新。成本是三分鐘，不更新的成本是別人半天。

> **這份文件是衍生視圖，不是新的真相來源。**
> 任務清單與驗收條件的規範性擁有者是 `.kiro/specs/hoya-market-agent/tasks.md`；
> 「誰正在做什麼、哪些路徑已凍結」的擁有者是 `docs/ACTIVE_WORK.md`。
> 本文把 `tasks.md` 的 task 重排成**可獨立驗證的建置階段**，每階段都用同一個模板，
> 並帶一個會持續更新的**現況區塊**。**若本文與 `.kiro/` 或 `ACTIVE_WORK.md` 衝突，以它們為準。**

## 1. Context

本文把整個建置切成**階段**，每個階段都必須在下一個開始前**獨立驗證通過**。它綁定三份上游：

- [Features.md](Features.md) — **做什麼**，以及每階段要引用的**契約詞彙表**（§5.1–§5.7）；
- [Tech-Stack-Plan.md](Tech-Stack-Plan.md) — **用什麼**、共用慣例，以及**風險導向的第一個里程碑**（→ 最早的階段）；
- [Architecture-FileMap.md](Architecture-FileMap.md) — **在哪裡**；每階段的「元件」欄位就是那份地圖的 row。

**技術棧速覽：** Python 3.12 · Pydantic v2 · 標準庫 `asyncio` · `httpx` · `pandas` · boto3/Bedrock Converse ·
Streamlit（同 process）· pytest · 單一 Docker image → ECR → 單台 EC2。
**每個檔的細節請看檔案地圖，本文不重列。**

> ⚠️ **狀態掃描時間：2026-08-03，基準 `origin/main@2c0d268` ＋ 本地兩個 commit（`69c019f`、`df4813e`）。**
> 本快照以實際檔案、已執行驗收與外部 gate 為準；較舊章節若衝突，以本節為準。
>
> **比賽已於 2026-08-02 結束**（Gold local Exit 通過、ECR/EC2 部署上線、CD pipeline 接上 main）。
> 以下 S0-S11 是**已出貨的競賽 MVP**，凍結；新規劃的延續工作是 `tasks.md` **Task 13-21**，
> 詳見本文新增的 [§9 賽後延續工作](#9-賽後延續工作task-13-21)，不在 S0-S11 模板裡重複列。

### 1.1 現況快照（authoritative）

| 階段 | 狀態 | 驗證後結論 |
|---|---|---|
| **S0** preflight | ✅ | 外部模型已成功呼叫（Haiku 4.5 @ `us-west-2`，`invoke_model`）；designated baseline research source 已指定（第一手 RSS ＋ Google News） |
| **S1** 契約與接縫 | ✅ | canonical models/config/clock/ports/fakes 已落地；`_provisional_seams.py` 已退役 |
| **S2** 垂直切片 | ✅ | fixture application、四項 artifacts、繁中 deterministic renderer 已落地；canonical seam swap 完成 |
| **S3** Streamlit Bronze | ✅ | canonical `ui/{presenter,streamlit_app}.py`、`reporting/advice_lint.py`（接進 renderer）、`Dockerfile`/`compose.yaml` 已落地；離線 Bronze Exit 通過、§3.2 人工清單以瀏覽器實測完成 |
| **S4** deadline 編排 | ✅ | per-stage 預算、finalize 保留區、stage 狀態機、`WorkerStatus` 映射、cancel-then-await fork-join、取消落盤與固定跳過順序全部落地並驗收 |
| **S5** 市場證據 | ✅ | Organizer CSV、Binance、deterministic indicators 與 market evidence 已整合 |
| **S6** 研究與 Evidence | ✅ | material conflict 落盤、多事實抽取、port 包裝、optional／反方訊號清單、單次 retry、共用 `AsyncClient`、`evidence/types.py` 已刪除、reliability 改由 processor 指派、fact-grounding（G1）接進 pipeline |
| **S7** bounded reasoning | ✅ | Planner、Research Agent、Arbiter 與 Bedrock boundary 已完成並凍結；`reasoning/{mapping,schemas}.py` 新增（未改凍結檔） |
| **S8** H2-Lite Silver | ✅ | **Silver live Exit 已過（2026-08-02）**：`tests/live/test_live_silver_pipeline.py` → 1 passed in 50.15s，schema-valid Bedrock 結構化輸出 ＋ 四項 artifacts。live composition root `composition.py` ＋ `adapters/live_sources.py` 已落地 |
| **S9** 創意層 | ✅（離線） | Trust Scorecard、regime/unavailable、Evidence-backed invalidation 與 renderer 已通過離線 smoke |
| **S9B** 雙幣比較 | ✅（離線） | 單一 run/cutoff/ledger、UTC 對齊、balanced Arbiter projection、比較 Claim 與第 12 段已通過 |
| **S10** Gold local Exit | 🟡 | 自動 acceptance 已補齊（`tests/acceptance/` 29 passed）、兩資產各兩次獨立單幣 run 已跑並記錄；Bedrock 帳號問題已解除，但 **complete-Evidence（含穩定的推論／結論）的 run 仍未達成**——見下方「未修的 live 缺陷」與 `docs/rehearsals/run-log.md` 尾段（2026-08-02 最後更新，七次 live run 只有一次產出結論層 claim） |
| **S11** 部署與彩排 | 🟡 | CI、smoke test、本地 Docker、**ECR/EC2 部署已上線並驗證**、**rollback 已實跑一次**、secret scan、CSV/Binance 重疊檢查、recorded fallback 全數完成；**只剩 15 分鐘 judged-flow rehearsal（人工，未執行）** |

**目前完成分層：**嚴格完成 S0/S1/S2/S3/S4/S5/S6/S7；離線功能完成 S9/S9B；
**S8 Silver Exit 已完成（2026-08-02）**；S10/S11 各完成大半，剩餘缺口見上表與下方缺陷清單。

**Repository-wide gate 實跑（2026-08-03, branch `post-comp/finish-remaining-gates` @ `df4813e`, Python 3.12.13, `.venv-gate`）：**
`python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q`
→ **1306 passed, 0 failed**（較 2026-08-02 的 1266 多 40：本次工作階段新增 2 個回歸測試並修掉它們
抓到的 2 個真缺陷，另刪除 `p2-etl-mvp/` 71 檔重複樹，測試數不受影響）；`ruff check .` →
**All checks passed!**；`docker compose config` → valid。

**GitHub Actions 已配置**（`.github/workflows/ci.yml`）：verify（ruff ＋ 非 live 測試）、
container（`docker compose config` ＋ image build ＋ 容器內 smoke ＋ 非 root/無 `.env` 檢查）、
secret-scan（gitleaks 掃追蹤內容 ＋ 追蹤檔名檢查）。三個 job 都不需要 AWS 憑證。

**Secret scan 實跑（2026-08-02, gitleaks v8.28.0）：**追蹤內容 315 檔 → **no leaks found**；
全歷史 206 commits → **no leaks found**。（工作樹全掃會有 125 筆，全部落在 `.venv/` 的
botocore／numpy／pyarrow 測試 fixture，非 repo 內容——所以 CI 只掃 `git archive HEAD`。）

**✅ Bedrock 已可用（帳號已換）：**競賽帳號改為主辦方的 AWS Workshop Studio 帳號
`411451203311`；`scripts/diagnose_bedrock.py` → **3/3 成功，每次約 8 秒**。憑證短期、帳號臨時，
**帳號本身也是活動臨時帳號，會被收回——之後要換回自己的帳號才能繼續跑 live**。

**Live run 缺陷現況（2026-08-03 覆核 `docs/rehearsals/run-log.md` 全文與目前程式碼，修正上一版的誤判）：**

1. **Arbiter 撞 45 秒單次呼叫上限——UI 路徑已修，指令碼路徑已補齊，但更深的問題還在。**
   `composition.py`（Streamlit UI 用的 live pipeline）早就把 `max_tokens` 設成 3000 並留註解
   說明 6000/8000 會直接把 Arbiter 推過 45 秒上限；`application.build_research_pipeline`
   （`scripts/run_acceptance.py --live` 等指令碼用的路徑）原本仍用凍結預設的 8000，
   已在 2026-08-02 補齊為同一個 3000（`ARBITER_MAX_TOKENS`）。**但這只解決了逾時，
   沒有解決根因**：`run-log.md` 記錄的七次 live run 裡，即使 Arbiter 在時間內正常完成、
   信心到 `medium`，**仍有六次的第 7 段結論層是空的**（`claims` 本身就是 0 筆，不是渲染端丟的）。
   `main` 上的 `a1d17f2 fix(arbiter): guarantee non-empty structured claims on live runs`
   對此顯然沒有完全覆蓋。**修點在凍結的 `reasoning/`（Arbiter 或 prompt），需推理層 owner
   決定；截至本次覆核仍未修。**
2. **Planner 的資產比對在指令碼路徑仍會誤判，UI 路徑目前繞過它。**
   `application.py:395` 把 `Planner(plan_schema=ResearchPlan, ...)` 接上凍結的
   `models.ResearchPlan`，其 `assets: list[Asset]` 是 enum 型別；Python 3.11 起
   `str(Asset.BTC)` 回傳 `'Asset.BTC'` 而非 `'BTC'`，導致 `reasoning/planner.py:56` 的
   `plan_violations()` 永遠判定「plan changed the requested assets」，LLM 計畫每次被丟棄、
   退回決定論預設計畫。`composition.py`（UI 的 live pipeline）目前用的是完全不同的
   `_BaselinePlanner`，不經過這條比對，所以 UI 路徑不會踩到——**但這代表 UI 路徑的
   Planner 本來就沒有真的讓 LLM 選操作，不是這個 bug 被修好了**。指令碼路徑
   （`scripts/run_acceptance.py --live`、`build_research_pipeline` 的其他呼叫者）仍會踩到。
   修點同樣在凍結的 `reasoning/`，需 owner 決定；截至本次覆核仍未修。

**下一條關鍵路徑：** S8 live Silver ✅ → S10 自動 acceptance ✅ →
**S10 complete-Evidence run（卡在上述結論層不穩定 + Planner 比對兩個 reasoning/ 缺陷，
不再是 Bedrock 帳號問題）** → S11 15 分鐘計時彩排（部署本身已完成）。
其餘賽後延續工作見 [§9](#9-賽後延續工作task-13-21)。

---

## 2. 共用基礎與慣例（適用於每一個階段）

### 2.1 單一派發路徑（相當於「動作層」）

這個系統沒有多個入口。**每一次分析都只有一條路：**

```text
streamlit_app.py  →  ApplicationService.run(request, progress)  →  DeadlineAwarePipeline.execute()
```

- **stage 順序只存在 `orchestration/pipeline.py` 一處。** 任何「先做 X 再做 Y」的決定都不得散落他處。
- **所有外部呼叫都經過 `ports.py` 的 Protocol**，具體實作只在 `application.py` 組裝。
- **所有可用操作來自 static `ToolRegistry`**——設定支撐的 allowlist，
  🚫 無 runtime plugin discovery、無遠端 registry、外部內容不得變更它。
- **UI 不做決策**：`streamlit_app.py` 只送 request、只讀 `ProgressSink` 的事件。
  🚫 商業邏輯不得放進 Streamlit callback。

### 2.2 單一 typed 設定存放

- 環境變數只在 `config.py` 解析一次 → typed `Settings` 傳進 factory。
- 鎖定名稱見 [Features.md §5.7](Features.md)。`run_config.json` 只記 optional key 的**存在布林值**。
- `.env` 只在本機且不進 Git；`.env.example` 只有名稱佔位。

### 2.3 橫切閘門（每個階段的 DoD 都包含它）

[Tech-Stack-Plan.md §6.5](Tech-Stack-Plan.md) 的四條邊界檢查必須是**自動的**：

1. `data/`、`evidence/`、`reporting/`、`orchestration/`、`ui/` 與根層契約檔 🚫 不得 import `boto3`/`httpx`；
2. `reasoning/` 🚫 不得寫檔（`open(`／`Path.write*`／`os.replace`）；
3. production code 🚫 不得 import `tests.fixtures`；
4. `ruff check .` + required test suite 綠。

### 2.4 跨階段政策（每個階段都要守）

| 政策 | 內容 |
|---|---|
| **Artifact-first 順序** | `run_config.json`（run 開始）→ `execution_log.jsonl`（串流）→ `evidence.json`（Ledger 完成即寫，**不等 Arbiter**）→ `final_report.md`（最後）。四份共用一個 `run_id`，一律原子寫入 |
| **Run mode 不可變** | 驗證後不可改；出現在 UI、每一筆 log 與 `run_config.json` |
| **H3 永遠停用** | 只有 `DisabledConflictExtension`；🚫 不得建立 Bull/Bear/Judge 的檔案、prompt、task 或測試路徑 |
| **Coin-agnostic** | pipeline 以 `{asset}` 為參數；🚫 禁止 `if asset == "BTC"` 這類 per-coin 分支、per-coin 特調參數或硬編路徑 |
| **Red → Green → Refactor** | 先寫會失敗的聚焦測試 → 確認它是因缺功能而失敗（不是 import/路徑錯）→ 最小實作 → 跑模組測試 + 相關 regression → 才 commit |
| **一 task 一 commit** | Conventional commits（`feat:`/`fix:`/`test:`/`docs:`/`chore:`）；同一 commit 更新 `tasks.md` 的 checkbox；🚫 不 squash 掉單一 task |
| **誠實回報** | **絕不宣稱測試通過卻沒實際跑過。** 修 bug 先加可重現的 regression test |
| **Kiro 分工** | `tasks.md` 的 Task 1（models/contracts）與 Task 2（fixture 垂直切片）保留給 Kiro 產生，作為「Kiro 用於開發」的證據；Claude Code 🚫 不搶先實作這兩個 task 的核心檔案。時間不夠而改由 Claude Code 補完時，須在 `docs/evidence/kiro/README.md` **誠實記錄實際產出者** |

### 2.5 路徑佔用（四人可同時 commit 的依據）

依 `docs/ACTIVE_WORK.md`（2026-08-01 重新分配）；路徑互不重疊：

| 專長 | 任務 | 分支 | 獨佔路徑 |
|---|---|---|---|
| **agent 用 Kiro** | A 契約與骨幹 | `task/1a-contracts-core` | `pyproject.toml`、`models.py`、`config.py`、`clock.py`、`ports.py`、`orchestration/`、`reasoning/`（除 `research_agent.py`）、所有 `__init__.py` |
| **分析指標** | B 市場數據層 | `task/4-market-data-layer` | `data/`、`adapters/{organizer_csv,binance}.py`、`tests/unit/data/` |
| **資訊整理** | C 證據與敘事層 | `task/5-evidence-layer` | `evidence/`、`adapters/{_assets,cryptopanic,rss,official,alternative_me}.py`、`reasoning/research_agent.py`、`tests/unit/evidence/` |
| **UI** | D 呈現與交付 | `task/0-preflight-and-ui` | `streamlit_app.py`、`ui/`、`reporting/`、`scripts/`、`Dockerfile`、`compose.yaml`、`docs/evidence/` |

**三條協調規則（不遵守一定會撞）：**
1. **一律從 `main` 開分支**，🚫 不要從 `feat/p2-*` 開。要 P2 的檔案時用
   `git checkout origin/feat/p2-report-integration -- <只取自己那半>` 再 `git mv` 進 `src/hoya_agent/`。
   這樣 `p2-etl-mvp/` 從頭到尾不會進 `main`。
2. **S1 落地前，B 與 C 🚫 不要自己建 `pyproject.toml`**——那是 A 的獨佔路徑，自建等於開出第三棵樹。
   用臨時 venv（見 [Tech-Stack-Plan.md §5](Tech-Stack-Plan.md)）。
3. **`evidence/types.py` 與 `evidence/policies.py` 由 gate 負責，B 與 C 都不要碰**——兩邊都 import 它們，各搬各的會產生兩份。

---

## 3. 跨階段測試策略

### 3.1 分層

| 層 | 位置 | 網路 | 覆蓋 | 必跑時機 |
|---|---|---|---|---|
| Unit | `tests/unit/` | 🚫 禁 | schema、指標（golden）、deadline、Evidence policy/processor、renderer、lint、trust、regime | 每次 commit |
| Contract | `tests/contract/` | 🚫 禁（`httpx.MockTransport` / Bedrock stub） | 每個 adapter 的成功／timeout／HTTP error／malformed／空資料；provider 錯誤正規化 | adapter/LLM 的 commit |
| Integration | `tests/integration/` | 🚫 禁 | 垂直切片、fork-join、partial result、降級、run mode、provenance、四項 artifacts | 每次合併 |
| Acceptance | `tests/acceptance/` | 預設禁 | 雙資產 Gold、deadline 預算、artifact 契約 | Day 2 freeze 前 |
| Live | `tests/live/` | **明確 opt-in** | 真實 provider、真實 Bedrock、CSV/Binance overlap、部署 smoke | 手動 |

**預設的 `python -m pytest` 絕對不能碰外網。** Live test 必須同時具備 `@pytest.mark.live`
**與** `RUN_LIVE_TESTS=1`，缺任一條件就 skip。

### 3.2 只能由人驗證的部分（人工檢查清單）

以下無法 headless 驗證。清單直接寫在這裡，S0／S3／S11 的 Definition-of-Done 就以它們為簽核依據；
🚫 不另開測試指南文件。每一項只有兩種結果：**pass** 或 **fail + 一句實際觀察**，
🚫 不接受「應該可以」。簽核結論寫回該階段的現況區塊。

**S0 — 服務可用性 preflight（產出是紀錄，不是測試案例）**

- [ ] `aws bedrock list-foundation-models` 在目標 region 實際列出可用 model ID（🚫 不憑印象填 ID）。
- [ ] 以最小、不含敏感內容的 prompt 完成**一次真實 Converse 結構化輸出**呼叫並取回結果。
- [ ] optional fallback 模型獨立探測一次；不可用**不阻塞** Bronze 或 Silver。
- [ ] 研究來源候選只探測可用性；designated baseline research source 已指定。
- [ ] `docs/rehearsals/service-access-check.md` 記下時間戳／region／model ID／pass-fail
      與 Python 3.12、Docker、AWS CLI 版本；🚫 不記 token、憑證、response header。
- [ ] `git ls-files` 不含任何憑證。

**S3 — Streamlit Bronze（瀏覽器與人眼才看得到的部分）**

> **驗證：2026-08-01,以真實瀏覽器（chrome-cdp)驅動 `streamlit_app.py`（HOYA_DATA_DIR 指向官方資料集、無網路/Bedrock/AWS）逐項實測;截圖留存於 PR。**

- [x] 在**斷網、無 AWS 憑證**的環境 `streamlit run streamlit_app.py` 能開起來且無 console error。（health `ok`、頁面渲染無錯）
- [x] 題目輸入 + 幣種選擇只接受五幣；run mode 選擇器可見。（selectbox 綁 `Asset` 五幣;依 Task 7/278,**第二幣 opt-in 屬 Task 12,Bronze 先停用單幣路徑**;Run mode selectbox 可見）
- [x] 送出後 run 按鈕**立即停用**;重複點擊不會產生第二次 `ApplicationService` 呼叫。（`form_submit_button(disabled=running)` + `st.session_state["_run_in_flight"]` 再入保護）
- [x] 進度依**事件**推進,🚫 不是用「經過多久」假裝的動畫。（`ProgressSink` → `st.status` 串流真實 `ExecutionEvent`;Bronze pipeline 不執行 Planner/Research/Arbiter,故只出現實際觸發的 stage:run/market_worker/evidence_processor/artifact/run,非六列固定動畫)
- [x] `official`／`rehearsal`／`demo` 三種模式在畫面上**一眼可辨**。（`presenter` badge official🔴／rehearsal🟡／demo⚪,單元測試 + 瀏覽器實測;recorded-fallback 常駐警示屬 Silver 範圍,Bronze 純離線不觸發)
- [x] Report／Evidence／Execution Log 三個分頁都能渲染。（`st.tabs`:📄報告 markdown／🧾Evidence Ledger 顯示 evidence.json／🪵Execution Log 顯示 execution_log.jsonl,皆實測渲染)
- [x] 四個下載鈕各自下載到正確檔名的檔案,且四份的 `run_id` 與畫面顯示一致。（final_report.md／evidence.json／execution_log.jsonl／run_config.json,同一 run_id)
- [x] H3 在 UI 上標示為**未實作**。（常駐 caption「🚫 H3 多代理人辯論:未實作(Bronze 範圍外,Future Work)」)
- [x] 報告內文抽樣:無買賣／加減倉／配置用語;confidence 只出現 `high|medium|low`。（renderer 已接 `advice_lint`;五幣輸出瀏覽器抽樣零禁語;confidence 顯示 LOW)

**S11 — 部署與計時彩排（真實延遲、真實網路、真實牆鐘）**

- [ ] `docker compose up -d` 後 `curl -f http://<host>:<port>/_stcore/health` 通過。
- [ ] 推上 ECR 的 immutable tag 與 EC2 實際啟動的 tag **逐字相同**。
- [ ] Binance／CSV 重疊區間（2026-05-01～05-31）五幣 close 差異檢查已跑並留存結果；
      🚫 不得暗示 CSV 來自 Binance。
- [ ] 一次**完整 15 分鐘計時**的評審流程彩排：輸入題目 → 觀察進度 → 檢視三分頁 →
      下載四項 artifacts；記下 run ID、模式、時長、來源缺口與 artifact 路徑。
- [ ] 第 13 分鐘前四項 artifacts 齊全（實際看時間，不是推論）。
- [ ] 真實 provider schema 漂移檢查：live rehearsal 中沒有 adapter 因欄位變動而靜默回空。
- [ ] recorded fallback run 在 UI 與報告都顯示 `run_mode=demo` 與原始取得時間。
- [ ] rollback 指令實際執行過一次（或明確記錄未驗證）。
- [ ] secret scan 通過；截圖與錄影不含 `.env`、憑證、API key。

### 3.3 每階段的 Definition-of-Done（統一標準）

一個階段只有在**全部**成立時才算完成：

- [ ] 該階段的 unit / contract / integration 測試**實際跑過**且綠（不是「應該會過」）；
- [ ] 相關的 regression suite 仍綠（沒弄壞別人已通過的測試）；
- [ ] `ruff check .` 乾淨；
- [ ] §2.3 的四條邊界閘門乾淨；
- [ ] 本階段引入的任何 artifact/log 欄位都能在真實輸出中看到；
- [ ] 若該階段有人工檢查項，其 checklist 已勾完（S0/S3/S11 用 §3.2 的清單）；
- [ ] 該階段的**現況區塊已更新**，包含任何刻意的偏離；
- [ ] `tasks.md` 對應 checkbox 已在同一個 commit 更新。

---

## 4. 階段相依順序

```text
S0 ──┐                    （S0 不依賴任何人，卻能否決所有人 → 排最前）
     ├─▶ S1 ─▶ S2 ─▶ S3 ★Bronze ─┬─▶ S4 ─┐                    ┌─▶ S9  ─┐
S7 ──┘（已完成，早於 S1）          ├─▶ S5 ─┼─▶ S8 ★Silver ─────┤        ├─▶ S10 ★Gold local Exit ─▶ S11
                                  └─▶ S6 ─┘                    └─▶ S9B ─┘
```

- ~~**S0 與 S1 可並行**~~ — **兩者皆已完成（2026-08-01），不再是排程因素。**
- **S4 / S5 / S6 可三路並行**（路徑互不重疊，見 §2.5）；**S4 與 S5 已完成**。
- **S2 已完成（PR #12）；S3 Bronze 已完成（2026-08-01)；S4 已完成（2026-08-01 第二輪）。
  關鍵路徑現在是 S6 → S8 ★Silver。**
- **S7 已經完成**，且是在 S1 之前完成的——這是本專案最大的一個順序偏離，見 S7 的現況區塊。
- **S9（創意層）與 S9B（雙幣比較）互不相依、可並行**，兩者都在 S8 之後、S10 之前的 additive 窗口。
  兩者都對 Bronze 與 Silver 非阻塞，但都必須在 S10 觸發 Feature Freeze 前完成，
  否則各自走自己的退場／降級條款。

---

## 5. 各階段

### S0 — 服務可用性 preflight（含**專案史上第一次真實 Bedrock 呼叫**）

> **現況：✅ 已完成（2026-08-01，由 P2 驗證，非原指派的任務 D）。**
> **全案最高風險項已拆除。** 紀錄在 `p2-etl-mvp/docs/service-access-check.md`。
> **實測結果：** `us.anthropic.claude-haiku-4-5-20251001-v1:0` @ `us-west-2`，
> boto3 `bedrock-runtime` `invoke_model`，`python bedrock_smoke.py` → `[OK]`；
> `python run_agent.py BTC` → 10 篇新聞抽出 30 筆結構化事實。
> **踩過的坑（有價值，別重踩）：** ① 舊 `claude-3-5-haiku-20241022` 已下架，
> 回 `ResourceNotFoundException: model version has reached end of life`，改用現役 Haiku 4.5 即通；
> ② 部分模型需 inference profile，model id 要加 `us.` 前綴；
> ③ 模型回應被 markdown 圍欄包住會導致抽取 0 筆（commit `6ee4b3e` 修）。
> **來源可用性：** 主辦 CSV、Binance/OKX spot、資金費率、九家第一手新聞 RSS、Google News、
> Alternative.me 全部 ✅；Reddit Atom 住宅 IP 可、資料中心 IP 403（降級揭露）；
> CryptoPanic ⏸ 需 token。
> **designated baseline research source 已指定：** 第一手新聞 RSS + Google News 依幣種搜尋
> （免 key、五幣覆蓋、已驗證）；CryptoPanic 取得 token 後可升為主。
> **剩餘尾巴：** `.env.example` 正式位置待團隊統一（目前根目錄與 `p2-etl-mvp/` 各一份）；
> S0 紀錄尚未搬進計畫原訂的 `docs/rehearsals/service-access-check.md`。

**目標**：用最小成本證明「外部服務真的可用」，並把結果記成不含秘密的紀錄。
對應 `tasks.md` Task 0 與 ACTIVE_WORK 的任務 D 第一優先項。

**元件與職責**
- `.env.example`（修改）— 只加**名稱**：`AWS_REGION`、`BEDROCK_PRIMARY_MODEL_ID`、
  `BEDROCK_FALLBACK_MODEL_ID`、`CRYPTOPANIC_API_TOKEN`、`ARTIFACT_ROOT`。🚫 永不加值。
- `docs/rehearsals/service-access-check.md`（新增）— 紀錄表：時間戳 / region / model ID / pass-fail。
- `docs/evidence/kiro/`、`docs/evidence/`（新增）— 一次成功 Converse 的證據（截圖或去識別的回應摘要）。

**本階段處理的契約詞彙**：[Features.md §5.7](Features.md)（環境變數名稱）。

**設定鍵**：上列五個名稱；`run_config.json` 之後只記它們的**存在布林值**。

**演算法與注意**
- 每個設定的 Bedrock 模型**各自獨立**探測一次，用最小、不含敏感內容的 prompt。
- **optional fallback 模型不可用不阻塞 Bronze 或 Silver。**
- 研究來源候選只探測可用性，🚫 不記錄 token、🚫 不記錄 response header。
- 在 Silver 驗收前，必須明確指定**哪一個 adapter 是 designated baseline research source**。

**測試**
- 自動：無（本階段的產出是紀錄，不是測試）。
- 人工：見 [§3.2 的 S0 清單](#32-只能由人驗證的部分人工檢查清單)。

**退出條件**
1. 至少一個 Bedrock 模型完成過一次**真實**的 Converse 結構化輸出呼叫，證據已存檔；
2. `docs/rehearsals/service-access-check.md` 記下 Python 3.12 / Docker / AWS CLI 版本；
3. designated baseline research source 已指定；
4. 已重新確認 Platinum / CoinGecko / 五幣矩陣 / H3 / S3 / CloudWatch / ECS 為 post-hackathon Future Work；
5. `git ls-files` 中沒有任何憑證。

**明確不做**：任何實作。本階段只驗證外部世界，🚫 不寫功能程式碼。

---

### S1 — 凍結共用契約與執行期接縫

> **現況：✅ 已完成（2026-08-01）。1a 與 1b 都已合併進 `main`。**
> **已實作：** `pyproject.toml`、`models.py`、`config.py`、`clock.py`、`ports.py`、
> `tests/fakes.py`、`tests/conftest.py`（PR #6 契約、PR #11 執行期接縫）。
> **Kiro 使用證據：** Task 1a 由 Kiro 從 spec 原生執行，ledger 記在
> `docs/evidence/kiro/README.md`（含兩輪 Codex 契約審查與誠實記錄的三項流程偏離）。
> **契約驗收已完成，🚫 不要重做：** 八組下游替身 ↔ 正式契約逐欄比對，
> **零個欄位在下游存在而契約沒有，且沒有任何改名**。差異全是單向的（契約多出
> `run_id`／`run_mode`／`analysis_as_of`／`time_range` 等），細節見
> `.kiro/steering/work-in-progress.md`。
> **偏離：** 原計畫是「先契約、後推理」，實際是**推理層先完成**（見 S7）。
> 代價是 `tests/unit/reasoning/_stubs.py` 仍是替身，尚未換成真 `models.py`——
> 那一輪機械替換仍待排，且該路徑凍結，需 owner 同意。
> **待辦：** 只剩 `_stubs.py` 替換與 `evidence/types.py` 退場。**已不再阻塞任何人。**

**目標**：讓 `models.py` 成為所有共用契約的唯一擁有者，讓 `ports.py` 成為所有外部面的唯一 Protocol 集合，
使四個人可以對著同一組型別各自實作。

**元件與職責**（→ [檔案地圖 §4.1](Architecture-FileMap.md)、[§4.10](Architecture-FileMap.md)）
- `pyproject.toml` — Python 3.12；執行期 `pydantic`/`httpx`/`pandas`/`boto3`/`streamlit`；
  dev `pytest`/`pytest-asyncio`/`pytest-cov`/`ruff`；marker `integration`/`acceptance`/`live`；src layout + editable install。
- `models.py` — 全部列舉（`str` 為底）＋全部契約模型，一律 `extra="forbid"`、文字欄位 strip 後不得為空。
  `EvidenceDraft` 定義為 `EvidenceItem` 減去 processor 指派的欄位（`evidence_id`、`reliability`、
  `independence_group`、`content_hash`），但保留回指原始來源紀錄的參照。
- `config.py` — `parse_env() -> Settings`；`sanitized_snapshot() -> RunConfigSnapshot`（optional key 只記布林值）。
- `clock.py` — `Clock` 實作：`now_utc() -> datetime`、`monotonic() -> float`。
- `ports.py` — `Clock`、`LLMClient`、`SourceAdapter`、`MarketDataAdapter`、`ResearchSourceAdapter`、
  `ProgressSink`、`ArtifactStore`、`ToolRegistry`、未來 persistence port。
- `tests/conftest.py` + `tests/fakes.py` — fixed clock、fake LLM、fake adapter、in-memory artifact/persistence、
  static fake `ToolRegistry`、in-memory progress sink。**同時把 `tests/contract/conftest.py` 與
  `tests/unit/reasoning/conftest.py` 的臨時 path bootstrap 收上來並刪掉那兩個檔。**

**關鍵簽章**
```python
class LLMClient(Protocol):
    async def converse_structured(self, *, operation: str, messages: list[dict],
                                  schema: type[BaseModel], max_tokens: int,
                                  deadline: float) -> BaseModel: ...

class MarketDataAdapter(Protocol):
    async def fetch_daily_bars(...) -> SourceResult[list[MarketBar]]: ...
    async def fetch_snapshot(...) -> SourceResult[MarketSnapshot]: ...

class ResearchSourceAdapter(Protocol):
    async def fetch(...) -> SourceResult[list[RawSourceRecord]]: ...

class ApplicationService(Protocol):
    async def run(self, request: AnalysisRequest,
                  progress: ProgressSink | None = None) -> RunSummary: ...
```

**本階段處理的契約詞彙**：[Features.md §5.1](Features.md)（輸入契約）、[§5.2](Features.md)（全部列舉與 ID 格式）、
[§5.4](Features.md)（confidence 上限，作為驗證器）、[§5.7](Features.md)（環境變數名稱）。

**設定鍵**：`AWS_REGION`、`BEDROCK_PRIMARY_MODEL_ID`、`ARTIFACT_ROOT`（必要）；
`BEDROCK_FALLBACK_MODEL_ID`、`CRYPTOPANIC_API_TOKEN`、`HTTP_CONNECT_TIMEOUT_SECONDS`、
`HTTP_READ_TIMEOUT_SECONDS`、`MAX_EVIDENCE_FOR_ARBITER`（硬上限 30）、`ALLOW_RECORDED_DEMO_FALLBACK`、
`LOG_LEVEL`（選用）。

**演算法與注意**
- **欄位名必須在 Python / JSON / prompt / fixture / test 之間完全一致**——這是欄位漂移最容易發生的一步，
  所以 Task 1 才被切成 1a（資料契約）+ 1b（執行期接縫）兩次執行。
- 明確拒絕：無效資產、naive datetime、**已廢的 `fetched time` / `fetched_time` 欄位名**、
  `EvidenceItem` 上出現任何 stance 欄位、Link 上出現三個列舉以外的 stance、cache metadata 不一致
  （`is_cached=false` 卻有 `cache_time`）、`fact` 卻帶 `based_on_claim_ids`。
- R16 型別（`TrustScorecard` 五個面向子模型、`MarketRegime`、`InvalidationCondition`）**在這一步就定義**，
  即使 S9 才用——後補會動到已凍結的 `AnalysisResult`。
- 固定 ordinal 映射也在這裡測：`strong` independence 需 ≥3 distinct groups。

**測試**
- 自動：`tests/unit/test_models.py`（先寫失敗版）、`tests/unit/test_config.py`、port 契約測試。
  ```bash
  python -m pip install -e ".[dev]"
  python -m pytest tests/unit/test_models.py -q
  python -m pytest tests/unit tests/contract -q
  ruff check .
  ```
- 人工：契約驗收對照 `docs/ai/P3_CONTRACT_EXPECTATIONS.md`（reasoning 層實際 import 的欄位名清單），
  約 15 分鐘；確認每一個名稱都在 `models.py` 裡且拼字相同。

**退出條件**
`pip install -e ".[dev]"` 成功；`test_models.py` 全綠；**S7 既有的 157 個測試仍然全綠**
（證明新契約沒弄壞下游消費者）；`reasoning/` 只剩一套 LLM 邊界。

**明確不做**：任何業務邏輯、任何 adapter 實作、把 `evidence/types.py` 立刻刪掉
（刪除留到 S5/S6 各自的機械替換那一步，避免一次動到兩個人的分支）。

---

### S2 — Fixture 垂直切片與 artifact 契約

> **現況：✅ 已完成；PR #18 已完成 canonical seam swap。**
> `application.py`、artifact store、renderer 與 fixture vertical slice 均在 `main`；
> `_provisional_seams.py` 與 bridge test 已刪除，runtime imports 已指向 canonical models/ports。

**目標**：在完全沒有網路、Bedrock 與 AWS 憑證的情況下，讓一個 fixture 請求穿過**真正的**
`ApplicationService` 並產出四份可解析的 artifacts。這是 [Tech-Stack-Plan.md §7](Tech-Stack-Plan.md) 的**風險切片 A**。

**元件與職責**（→ [檔案地圖 §4.1](Architecture-FileMap.md)、[§4.7](Architecture-FileMap.md)）
- `application.py` — 驗證 request、凍結 `analysis_as_of`、造 `run_id`、建 run 目錄、組裝相依、回 `RunSummary`。
- `reporting/artifacts.py` — `write(name, payload)`（同目錄暫存檔 → flush → `os.replace`）、
  `append_event(ExecutionEvent)`、`finalize(terminal_state, checksums)`。
- `reporting/renderer.py` — `render(result, ledger) -> str`（繁中 11 段）＋ insufficient-data 的 deterministic fallback。
- `tests/fixtures/vertical_slice/{evidence.json,analysis_result.json}`。

**本階段處理的契約詞彙**：[Features.md §5.5](Features.md)（四項固定 artifacts 與各自欄位）——
這是本階段的核心引用；另引 [§5.1](Features.md)（`run_mode=rehearsal`）。

**設定鍵**：`ARTIFACT_ROOT`。

**橫切新增項**：本階段第一次寫出 `run_config.json` 的 schema/prompt/policy 版本欄位、
`execution_log.jsonl` 的完整事件形狀、`evidence.json` 的 ledger 容器。**這三個形狀之後只准加欄位，不准改名。**

**演算法與注意**
- **寫入順序就是韌性設計**：`run_config.json` 必須在**任何**網路呼叫之前寫出。
- 原子寫入用同目錄暫存檔——跨目錄 rename 在某些檔案系統上不是原子的。
- **缺檔揭露契約**（`design.md §12.1`，這是最容易漏測的一段）：
  - partial/degraded 但目錄可寫 → **四份都要有**，並記錄限制、缺失能力與 terminal state；
  - 某一份寫不出來 → 在 stdout **與所有仍可寫的** `execution_log.jsonl` / `run_config.json`
    指名**確切的**缺檔檔名與寫入失敗原因；
  - 目錄完全不可寫 → stdout 列出全部四個缺檔檔名、寫入失敗與 terminal state。
    **🚫 系統絕不宣稱某個沒寫出來的 artifact 存在。**
- 報告的 11 個段落見 [Features.md §3](Features.md)；🚫 renderer 不得加入 fixture 以外的事實。
  本階段是單幣 fixture，所以只有 11 段；雙幣的第 12 段「跨幣比較」屬 S9B。

**測試**
- 自動：
  ```bash
  python -m pytest tests/unit/reporting tests/integration/test_vertical_slice.py -q
  ```
  必含：11 段渲染、Evidence ID 出現在報告中、confidence 只用 `high|medium|low`、
  原子寫入、partial/degraded 四份齊全、**單一寫入失敗的指名揭露**、目錄完全不可寫的 stdout 揭露。
- 人工：無（本階段完全可 headless 驗證——這正是它先於 S3 的原因）。

**退出條件**
無網路的 fixture 路徑產出四份可解析的 artifacts、共用一個 `run_id`、誠實標為 `rehearsal`；
報告中沒有 fixture 以外的事實；缺分析時走 deterministic fallback。

**明確不做**：Streamlit（S3）、真實 adapter（S5/S6）、編排與 deadline（S4）、R16 區塊（S9）。

---

### S3 — Streamlit Bronze 檢查點 + 禁語 lint + 容器殼 ★ **Bronze Exit**

> **現況：✅ 已完成（2026-08-01）。整合於 post-S2-swap `main`。**
> **已落地：** `src/hoya_agent/ui/{__init__,presenter,streamlit_app}.py`、
> `src/hoya_agent/reporting/advice_lint.py`(禁語 lint,純字串比對,已接進 `application.render(..., lint=advice_violations)`
> —— 補上先前 renderer 未帶 lint 的缺口)、`Dockerfile` + `docker-compose.yml`(`python:3.12-slim`,打包官方資料集、Streamlit healthcheck)。
> **驗證:** 全套 **593 tests 綠**、`ruff check .` 乾淨;離線 Bronze Exit 通過(Streamlit 提交一次 run → 四份 artifact 產出並可下載、標示 rehearsal/demo);
> §3.2 人工清單以 **chrome-cdp 真實瀏覽器**逐項實測完成;Docker image 建置(856MB)+ 容器內完整 end-to-end run 亦驗過(超出 Bronze 要求)。
> **輸出格式:** 報告為 **Markdown** `final_report.md`(非原型的 HTML)。商業邏輯在 `application.py`／`presenter.py`,🚫 不進 Streamlit callback。
> **指派:** 任務 D。**相依:** S2 ✅。

**目標**：讓評審能在瀏覽器裡完成一次完整的離線 run 並下載四份 artifacts。**這是 Bronze 驗收閘門。**

**元件與職責**（→ [檔案地圖 §4.7](Architecture-FileMap.md)、[§4.8](Architecture-FileMap.md)）
- `reporting/lint.py` — `check(text) -> list[LintViolation]`；純字串比對禁語表。
- `ui/presenter.py` — `to_view(summary, events) -> RunView`：stage 進度、成功/失敗來源、
  degradation notes、terminal state、run-mode 標籤、**H3-未實作**狀態、recorded-fallback 警示。
- `streamlit_app.py` — 單一畫面；run 中停用按鈕（確保一次提交＝一次 `ApplicationService` 呼叫）。
- `Dockerfile`、`.dockerignore`、`compose.yaml` — **Bronze 通過之後才做**；non-root、環境變數帶秘密、
  Streamlit healthcheck；🚫 不加 FastAPI。

**本階段處理的契約詞彙**：[Features.md §5.1](Features.md)（三種 run mode 的視覺辨識）、
[§5.2](Features.md)（`Asset` 五幣限制、stage state 對應到六列進度）、
[§5.5](Features.md)（四個下載鈕的檔名）。

**設定鍵**：`ARTIFACT_ROOT`、`ALLOW_RECORDED_DEMO_FALLBACK`、`LOG_LEVEL`。

**演算法與注意**
- 禁語表至少涵蓋：建議買入、建議賣出、加倉、減倉、做多、做空、資產配置、下單、
  以及它們的常見變體。**lint 永遠最後跑**，即使前面全部通過。
- UI 只從 `ProgressSink` 事件取狀態，🚫 不得用「經過多久」推斷成功，🚫 不得檢視內部 task 物件。
- 五幣輸入 allowlist 與一至二幣契約要保留，但 🚫 不做五幣矩陣、不做校準流程。
  **第二幣的加選控制在此階段先停用**——雙幣比較的行為屬 S9B，Bronze 只驗單幣路徑。

**測試**
- 自動：
  ```bash
  python -m pytest tests/unit/ui tests/integration/test_ui_application_contract.py -q
  docker compose config
  ```
- **人工（必要）：** [§3.2 的 S3 清單](#32-只能由人驗證的部分人工檢查清單)。
  瀏覽器渲染、下載鈕、三模式視覺辨識、進度列即時性、重複提交防護都只能人工驗。

**退出條件（★ Bronze Exit）**
在**無網路、無 Bedrock、無 AWS 憑證**的環境下，從 Streamlit 提交一次 run，
產出並下載全部四份 artifacts，標示為 `rehearsal` 或 `demo`。
Docker 支援不重新定義 Bronze 閘門——**Bronze 不要求 Docker 驗收**。

**明確不做**：任何 live 呼叫、任何 UI polish（`product.md` 明列 UI polish 優先序最低）。

---

### S4 — Deadline-aware fork-join 編排

> **現況：✅ 已完成（2026-08-01 第二輪）。原本 PR #18 的 🟡 低估了缺口——當時說「只缺測試」，實際實作缺四塊。**
> ① **`deadline.py` 從單一 flat deadline 變成真正的 per-stage 預算。** 之前只有無參數
> `remaining()`／`can_start()`／`run()`，`Features.md` §5.6 那張表**完全沒有實作**；
> `run_market()` 甚至沒傳 timeout，市場分支合法可吃掉整個 720 秒窗口、餓死 finalize。
> 現在 `Stage`（planner/gather/evidence/reason/artifact）里程碑以「參考 720 秒窗口的比例」保存，
> 短 deadline 依比例縮放；finalize 保留區 = `max(20%, min(60s, 半個 run))`——900 秒剛好得到 180 秒，
> 這正是分析硬停落在 720 的原因。新增 `deadline_for(stage)`、`remaining(stage)`、`budget_for()`、
> `budget_seconds()`、`DeadlineManager.for_run(context, clock)`。
> ② **`run_state.py` 從死碼變成真的狀態機。** 之前整個檔只有 `derive_terminal_state()`，
> 而且**全 repo 沒有任何地方 import 它**（pipeline 自己用 `if notes or result is None` 就地算）。
> 現在有 `RunStateMachine`（pending→running→settled、非法轉換丟 `ValueError`）、
> `stage_state_for()`（`WorkerStatus.completed→completed`、`partial→degraded`、`failed→failed`）、
> stage_start/stage_end 事件串流（含 `duration_ms`）與 `stage_durations_ms()`。
> ③ **`TerminalState.cancelled` 從無法到達變成真的會出現在 artifacts 裡。** 之前它只出現在那個死碼裡。
> 現在分三層：單一分支取消 + 手足完成 = **degraded**（手足證據照樣出貨）；
> 取證窗口取消了市場分支**且 Ledger 為空** = **cancelled**（沒東西可報，原因是取消不是失敗）；
> 呼叫端取消整個 run = **cancelled**，且 `application.py` 會先把四項 artifacts 誠實落盤
> （標 `cancelled`、走 deterministic insufficient-data 報告）**再 re-raise** `CancelledError`。
> ⚠️ 那段 finalize 必須全程**無 await**——在已被取消的 task 裡再 await 會立刻又拋 `CancelledError`，
> 四項 artifacts 就寫不完。`progress_tasks` 因此在取消路徑改為 cancel 而非 await。
> ⑤ **固定跳過順序已實作並且真的會生效。** `deadline.py` 持有 `OptionalWork`、`SKIP_ORDER`
> （H3 → optional context → 反方訊號二次搜尋）與純函數 `plan_optional_work()`；
> 成本由呼叫端給（每個 call 的 per-call timeout × 步數），**不在函數裡編造估值**。
> 執行點是 `DeadlineAwarePipeline._apply_skip_order()`：在 fork-join 之前依剩餘取證時間決定，
> 然後**把被略過的步驟從 `ResearchPlan` 裡裁掉**再交給 Research Agent——
> 走既有介面，`reasoning/research_agent.py`（凍結）一行都不用改。
> baseline 步驟永不被裁；若整個 plan 都是 optional 且一項都放不下，就**不啟動研究分支**
> （啟動一個工作已全被放棄的分支只是做帳）。每次略過都寫進 degradation notes 與 execution log。
> H3 **不參與分類**：它永久停用、從未被排程，把它記成「被略過」會讓人誤以為這次 run 有辯論階段可放棄。
> ④ **fork-join 改為「先取消、再 await」**：`_fork_join()` 用 `asyncio.wait(timeout=gather 窗口)`，
> 逾時後 `task.cancel()` 然後 `gather(..., return_exceptions=True)`，pending task 不再外洩到下一個 stage；
> 外層被取消時也先拆子任務再 re-raise。
>
> **踩過的坑（會咬人，別重踩）：** 一開始讓分支內層 `deadline.run(stage=Stage.gather)` **和**外層
> fork window 用同一個里程碑，兩個 clamp 數值相同 → 「是誰取消了這個分支」變成 race，
> 測試在 `cancelled` 與 `DeadlineExceeded` 之間跳動。定案：**取證窗口只有一個擁有者（fork-join）**，
> 分支內只 clamp 自己的 per-call timeout（45 秒）。連跑 5 次穩定通過。
>
> **實際跑過的驗證（2026-08-01）：**
> `python -m pytest tests/unit/orchestration tests/integration/test_fork_join.py -q` → **66 passed**；
> `python -m pytest tests/unit tests/contract tests/integration -q` → **1100 passed, 15 subtests passed, 0 failed**；
> `ruff check .` → **All checks passed**（本文 §8 第 9 項記的 87 個 error 已不復存在，該列可關）；
> `python scripts/verify_s8_s9_s9b.py` → PASS。
> 新增 `tests/unit/orchestration/test_deadline.py`（17）、`test_run_state.py`（22）、
> `test_skip_order.py`（13）、`tests/integration/test_fork_join.py`（3）、
> `test_cancellation.py`（3）、`test_skip_order_enforcement.py`（6）。
> 全部用注入的 fake clock，**沒有任何真實 45 秒 sleep**；
> 唯一的真實 await 是為了證明 `asyncio.wait_for` 真的接在算出來的預算上，量級是毫秒。
> 取消與 fork-join 相關測試連跑多次穩定通過（真實 event loop 取消，不是模擬）。
>
> **這裡的邊界要說清楚（不要誤讀為已在 live run 生效）：** 「哪些 operation 算 optional context／
> 反方訊號二次搜尋」是**由組裝端宣告**的（`DeadlineAwarePipeline(optional_operations=…,
> counter_signal_operations=…)`，預設空集合）。目前 `application.py` **還沒有組裝 live pipeline**
> （那屬於 S6／S8），所以現階段沒有任何 operation 被標成 optional——
> 跳過順序的政策與執行點都已完成且有測試，但要等 S6 宣告來源清單後才會在真實 run 中被觸發。
> 一句話：**機制完成，來源清單待 S6 填。**
>
> **一個已知的小尾巴：** per-stage 預算本身還沒寫進 `run_config.json`，因為 `RunConfigSnapshot`
> 是 `extra="forbid"` 且 `models.py` 是**凍結路徑**。`DeadlineManager.budget_seconds()`
> 已備好資料，等該檔 owner 同意加欄位即可落盤。stage **實際耗時**已經有寫（`stage_durations_ms`）。

**目標**：讓時間與狀態成為一個地方的決定。

**元件與職責**（→ [檔案地圖 §4.2](Architecture-FileMap.md)）
- `orchestration/deadline.py` — `DeadlineManager(clock, total_seconds)` 與
  `DeadlineManager.for_run(context, clock)`；`Stage` 里程碑列舉、`deadline_for(stage)`、
  `remaining(stage)`、`budget_for(stage, timeout_seconds=…)`、`budget_seconds()`；
  短 deadline 的比例縮放（保留末 20%、可能時至少 60 秒給 finalize，且永不超過半個 run）。
  另持有**固定跳過順序**：`OptionalWork`、`SKIP_ORDER`、`plan_optional_work()`、`skip_note()`。
  ⚠️ `Stage` 是**預算里程碑**，不是 execution-log 的 stage 名稱。
- `orchestration/run_state.py` — `RunStateMachine`（stage 生命週期 + stage_start/stage_end 串流 +
  `stage_durations_ms()`）、`stage_state_for(WorkerStatus)` 映射、
  `derive_terminal_state(states, run_cancelled=…)`。log stage 名稱由這裡持有。
- `orchestration/pipeline.py` — stage 順序、`_fork_join()`（單一取證窗口 → 先取消、再 await）、
  `_apply_skip_order()`（依剩餘取證時間裁掉 `ResearchPlan` 裡被略過的 optional 步驟）。

**本階段處理的契約詞彙**：[Features.md §5.6](Features.md)（deadline 預算表——本階段是它的實作者）、
[§5.2](Features.md)（stage state、terminal run state、`WorkerResult.status`）。

**演算法與注意**
- **`time.monotonic()` 算 budget，UTC 只用於落盤時間戳。** 混用是最常見的 bug。
- 逾時後**先取消、再 await** 所有未完成的 child task，**然後**才進 Evidence Processor——
  否則會留下 pending task 汙染下一個 stage。
- **🚫 絕不吞掉 `asyncio.CancelledError`**；adapter 必須釋放 HTTP response 並重新拋出。
- 狀態映射：`completed→completed`、`partial→degraded`、`failed→failed`、取消→`cancelled`。
- **降級的分支 🚫 不得丟棄已完成的手足分支的輸出。**
- 跳過順序固定為 **H3 → optional context adapter → 反方訊號二次搜尋**
  （H3 在 MVP 永遠是停用的，所以實際上從 optional context 開始跳）。
- 測試用 fake clock / fake sleeper，**🚫 不得真的 sleep 45 秒**。

**測試**
- 自動（**已實跑，2026-08-01：66 passed**）：
  ```bash
  python -m pytest tests/unit/orchestration tests/integration/test_fork_join.py -q
  ```
  已含：兩個分支在時間上**確實重疊**（互相等對方的 `asyncio.Event`，序列執行會失敗）；
  一個分支在取證 deadline 被取消後另一個的證據仍進 Ledger；pending task 不外洩到下一個 stage；
  取消映射到 stage `cancelled`／run `cancelled`；per-stage 預算與 finalize 保留區的比例縮放；
  預算耗盡時連呼叫都不啟動；固定跳過順序（含 H3 排第一、反方訊號最後放棄）。
  另見 `tests/integration/test_cancellation.py`：Ledger 為空 + 市場分支被取消 → run `cancelled`；
  呼叫端取消 run → 四項 artifacts 齊全且標 `cancelled`，`CancelledError` 仍照樣往外拋。
  以及 `tests/integration/test_skip_order_enforcement.py`：optional context 先於反方訊號被裁掉、
  baseline 步驟永不被裁、裁剪後的 plan 仍通得過 `ResearchPlan` 驗證、
  全 optional 且無時間時不啟動研究分支、H3 不被記成「被略過」。
  terminal state 寫進 log 與 config 由 `test_vertical_slice.py` 覆蓋。
- 人工：無。

**退出條件**：單一分支逾時後仍帶著手足的完成 Evidence 抵達 Renderer 且標為 degraded；
terminal state 由編排層決定並輸出，**🚫 不由 UI 推斷**；跳過順序為單一擁有者且有測試。
✅ 三項皆已達成。

**明確不做**：cancellation UI、database、queue、持久化 job record、遠端編排服務。

---

### S5 — Deterministic 市場證據層

> **現況：✅ 已整合進 `main`（2026-08-01，PR #8）。**
> **已實作：** `src/hoya_agent/data/{indicators,market_series,market_worker,price_analysis,regime,text_clean,types}.py`
> 與 `src/hoya_agent/adapters/{organizer_csv,binance}.py`，import 已改成 `from hoya_agent.…`。
> **兩項待裁決已定案：** `price_analysis.py` 保留為獨立模組並入 canonical tree；
> `okx.py`、`reddit.py`、`coingecko.py`、`derivatives.py`、`google_news.py` **不搬**
> （PR #8 移除超出 MVP 的五個來源共十個檔，對齊 `evidence-contracts.md`）。
> **待辦：** 型別仍是 `data/types.py` 的 provisional dataclass，尚未換成 `models.py`；
> 這一輪機械替換與 `evidence/types.py` 退場要一起做。
> **指派：** 任務 B。

**目標**：把 OHLCV 變成可回溯的數字。

**元件與職責**（→ [檔案地圖 §4.3](Architecture-FileMap.md)、[§4.4](Architecture-FileMap.md)）
- `data/market_series.py` — UTC 解析、剔除未完成日 K、CSV↔Binance 合併與 **2026-06-01 切換點**。
- `data/indicators.py` — 報酬、已實現波動、最大回撤、量能變化、rolling z-score、range position。
- `data/market_worker.py` — `execute(plan, ctx) -> WorkerResult`；每個指標 → 一筆 high-reliability `EvidenceDraft`。
- `adapters/organizer_csv.py`、`adapters/binance.py`。

**本階段處理的契約詞彙**：[Features.md §5.3](Features.md)（`high` 那一列的前兩項）、
[§5.2](Features.md)（`SourceType=market`）；市場指標的規範性定義見 `evidence-contracts.md §15`。

**演算法與注意**
- 報酬 `close_t / close_(t-n) - 1`；回撤 `close_t / cummax(close)_t - 1`，最大回撤取 window 最小值；
  波動要**宣告** return 頻率與 window（若年化須標示年化因子）。
- **volume z-score 只與該資產自身的 rolling base-volume 歷史比。**
- **🚫 跨幣不得直接比較 base-asset volume**；跨幣只能用報酬、波動、相對變化、各自 z-score，
  或**同一 provider、同一期間**的 quote volume。
- **缺 bar → 該指標 unavailable，🚫 不 forward-fill。**
  （實測顯示主辦方資料集 0 缺漏、0 NaN，所以這條主要防的是 live API 的缺口。）
- CSV 用來源名 `public_market_data`、group `organizer-public-market-data`，
  **🚫 不得推定其上游是 Binance 或任何特定交易所。**
- baseline live market source 失敗 → typed partial/degraded，**🚫 不得宣稱切到第二個 live provider。**
- 只保留呈現時才做 rounding；內部保留足以重算的精度。
- **`market_worker.py` 🚫 不得有任何到 `LLMClient` 的 import 或呼叫路徑**（這是一條可測的斷言）。

**測試**
- 自動：
  ```bash
  python -m pytest tests/unit/data tests/contract/test_market_adapters.py -q
  ```
  golden fixture 必須是**可手算**的 close/volume 序列 + 明確 expected value；
  浮點用 `pytest.approx` 並指定容許誤差。另含跨幣 base-volume 比較的**拒絕**測試。
- 人工：CSV/Binance overlap 校準（2026-05-01～05-31 收盤差異）屬 live rehearsal，見 §3.2 的 S11 清單。

**退出條件**：golden 值與 UTC 界線通過；baseline 失敗回 typed partial/degraded；
CSV↔live 切換點被明確表示且帶 `fetched_at`；`market_worker` 無 LLM 路徑。

**明確不做**：CoinGecko、五幣完整驗證矩陣、per-coin 校準、R16 的 regime（那是 S9）。

---

### S6 — 研究 adapters 與 Evidence Processor

> **現況：🟡 2026-08-01 第二輪：四項功能缺口已補完並驗收；剩下的是型別統一與 live 驗證。**
>
> **⚠️ 先更正上一版的狀態：** 前一版說「仍缺三塊：`research_extractor.py`、`evidence/ledger.py`、
> `adapters/official.py`」。實測 `main` 後**其中兩項早已存在**——`evidence/ledger.py`（12 個函式）
> 與 `adapters/official.py`（含 `tests/unit/data_evidence/test_official.py`，涵蓋成功／HTTP error／
> malformed／`ReadTimeout`）都在。但 `ledger.py` 當時是**死碼**：全 `src/` 沒有任何地方 import 它，
> 只有它自己的 unit test 用。**檔案存在 ≠ 接線完成**，這是本階段最貴的一個誤判。
>
> **這一輪實際補的四塊：**
> ① **Material conflict 真的會出現在 artifacts 裡了。** 之前 `pipeline.py` 的 `to_contract_ledger()`
> 把 `conflict_indicators=[]` **寫死**，而 `renderer.py`、`evidence/trust.py`、`reasoning/arbiter.py`
> 三處都在讀 `ledger.conflict_indicators`——所以 evidence-contracts §9 與「material conflict →
> confidence 上限 low」這條在真實 run 中**結構上不可能發生**。
> 新增 `evidence/ledger.py::build_conflict_indicators()`（純函數，claim_id 排序、id list 排序，
> 與 link 順序無關）＋ `pipeline.py::finalize_analysis()`：Arbiter 出結果後**才**跑衝突判定
> （stance 在 link 上，claim 層的判定只有等 link 存在才可能），把 indicator 落進 Ledger、
> 補一筆 `material_conflict_detected` degradation event、再套用凍結的 `apply_confidence_caps()`，
> 最後才建 Trust Scorecard（因為 `consistency` 面向要讀剛掛上去的 indicator）。
> **踩過的坑：** `apply_confidence_caps()` 用**純字串**比對 confidence，所以必須用
> `model_dump(mode="json")`；用預設的 python mode 會傳進 `Reliability.low` 這種 enum，
> rank 表查不到、`claim["confidence"]` 會被寫成 `"Reliability.low"`，接著 model_validate 直接炸。
> ② **多事實抽取搬進 `src/` 並與 S7 的 `research_agent.py` 對接（未改任何凍結檔）。**
> 新增 `reasoning/research_extractor.py`，提供 `ResearchAgent` 一直以注入方式索取、但 `src/` 從來
> 沒有人提供的兩半：`ResearchExtraction`／`ExtractedFact`（structured-output schema，一篇文章可回
> 多筆 fact＋relevance 判定）與 `complete_extracted_drafts()`（deterministic 補完）。
> **分工紅線：模型只出文字**；reliability 走靜態表（feed item 未取原頁 → 永遠 `low`）、
> `independence_group` 走 `policies.independence_group()`、時間戳一律取自 record。
> 引用不存在 record 的 fact 直接丟棄並揭露（那是捏造，不是可修補的瑕疵）；每篇上限 3 筆。
> `pipeline.py` 的 Evidence stage 現在先跑補完再 merge——**之前 extracted draft 是 100% 被
> `_merge_research_drafts()` 拒收的**（它要求 draft 已自帶 reliability 等欄位，而模型不該提供那些）。
> ③ **cryptopanic／alternative_me／official 有 port 包裝了。** 之前只有 `RssResearchAdapter`
> 符合 `ResearchSourceAdapter`，另外三個只有 module-level `fetch_*() -> WorkerResult`，
> **在真實 run 裡根本接不上**。新增 `CryptoPanicResearchAdapter`、`FearGreedResearchAdapter`、
> `OfficialAnnouncementsResearchAdapter`（都回 `SourceResult[list[RawSourceRecord]]`）。
> 為了讓 `SourceResult.status` 能分辨 timeout／http_error／malformed／rejected，新增
> `adapters/_errors.py`：adapter 在 degradation note 後面附一個 `[category=…]` token，
> port 包裝再讀回來。**空結果不是錯誤**——`empty` 與 `http_error` 分開，因為只有一種值得 retry。
> CryptoPanic 無 token → `rejected`（揭露，不是靜默消失）；token 永不進 `query_or_parameters`。
> ④ **組裝端終於宣告來源清單，S4 的跳過順序在真實 run 中可以生效了。**
> `application.py` 新增 `build_research_tool_registry()` 與 `build_research_pipeline()`：
> baseline = `fetch_rss_news`（S0 指定）；optional context = `fetch_fear_greed`、
> `fetch_official_announcements`；反方訊號二次搜尋 = `fetch_cryptopanic_news`。
> 另外 `ALLOWED_RESEARCH_HOSTS` 在**建構時**就拒絕非 allowlist host（外部呼叫之前，不是之後）。
> 沒設 LLM 時用 `DeterministicPlanner` 走預設計畫並揭露替代，研究分支照樣執行取證。
> **踩過的坑：** `StaticToolRegistry` 呼叫 handler 時給的是 `assets`／`analysis_as_of`
> **散裝參數**，不是 `RunContext`；原本的 port 簽章只吃 `context`，所以四個研究 adapter
> 的 `fetch()` 都改成 `context: RunContext | None = None` 並用 `_resolve_target()` 兩種都吃。
> 另一個坑：測試用單一 queue 的 `FakeLLM` 會讓 **Planner 先把那顆 response 吃掉**，
> 抽取階段拿不到東西 → 研究分支整段失敗。測試改用依 `operation` 分派的 `ScriptedLLM`。
>
> **實際跑過的驗證（2026-08-01）：**
> `python -m pytest tests/unit tests/contract tests/integration -q` → **1175 passed,
> 15 subtests passed, 0 failed**（前一輪基準是 1100）；
> `ruff check .` → **All checks passed**；`python scripts/verify_s8_s9_s9b.py` → **PASS**。
> 新增測試：`tests/unit/evidence/test_conflict_indicators.py`（8）、
> `tests/unit/reasoning/test_research_extractor.py`（11）、
> `tests/unit/data_evidence/test_research_port_adapters.py`（16）、
> `tests/integration/test_material_conflict.py`（4）、
> `tests/integration/test_research_extraction.py`（4）、
> `tests/integration/test_composed_research_pipeline.py`（8）。
> 另實測 layering：`orchestration/pipeline.py`、`evidence/ledger.py`、
> `reasoning/research_extractor.py`、`reporting/renderer.py` 匯入後 `sys.modules`
> **皆無 `httpx`／`boto3`**。
>
> **仍未完成（不要當成已完成）：**
> - **型別已統一（2026-08-01 第五輪，見下）**，`evidence/types.py` 已刪除。
> - **測試位置偏離**：`tests/contract/test_research_adapters.py` 不存在；mock-transport 測試放在
>   `tests/unit/data_evidence/`（沿用既有慣例，且 `tests/contract/` 是凍結路徑）。
> - **live provider 驗證**已就緒但屬 S11 rehearsal 的完整計時彩排範圍；真實 provider 抽樣已跑
>   （8 passed／4 skipped，見 `docs/rehearsals/live-source-check.md`）。
> - `p2-etl-mvp/` 仍在 `main`（§8 未決事項 8），因此每個 adapter 與其測試都有兩份。
>
> **➕ 2026-08-01 第五輪：型別統一與契約反向修正（§8 未決事項 3 結案）。**
> 先更正一個說法：`data/types.py::MarketBar` **不是**重複型別（`models.py` 沒有 MarketBar），
> 真正的重複是 `evidence/types.py` 的 `EvidenceDraft`／`EvidenceItem`／`EvidenceLedger`。
> **契約反向在哪：** 舊的 provisional `EvidenceDraft` **自帶 `reliability` 與 `independence_group`**，
> 等於讓「取到資料的人自己宣告可信度」；契約定義的 draft 是 `EvidenceItem` **減去**
> processor 指派的四個欄位（`evidence_id`／`reliability`／`independence_group`／`content_hash`）。
> **修法：** 新增 `evidence/drafts.py`——`PendingEvidence` = canonical `models.EvidenceDraft`
> ＋ **provenance**（`source_class` 決定靜態 reliability、`original_publisher`／`provider_id`
> 決定 independence group、`MetricValue` 帶 §16.4 需要的可驗證數值）。
> `evidence/processor.py` 改寫為唯一的指派點：reliability→靜態表、group→§5 規則、
> `content_hash`→正規化事實、`ev_NNN`→排序後配發，並直接輸出 **canonical
> `models.EvidenceLedger`**。`pipeline.to_contract_ledger()` 因此從 100 行列舉映射縮成
> 一層薄 seam，`_map_enums()` 整個刪除——**不支援的資產／source type 現在在「產生處」就被
> Pydantic 拒絕**，不再是落盤時才靜默丟掉。
> **順手處理掉的兩筆債：** `evidence/evidence_json.py`（非 canonical 的第二個 evidence writer，
> schema 與 `evidence-contracts.md` §12 衝突、且全 `src/` 無人 import）連同其測試一併刪除，
> canonical writer 只有 `reporting/artifacts.py`；`evidence/types.py` 刪除。
> **踩過的坑：** ① merge 會重新配發 `ev_NNN`，若 metric index 仍以舊 id 為 key，
> 量化 invalidation 的門檻就會指到**別筆證據**——`build_ledger(existing=…, existing_metrics=…)`
> 因此以 `content_hash` 重新對應（有回歸測試）。② regime 的「metric」是標籤不是數字，
> 舊 draft 只填 `metric_name` 不填值；現在 `MetricValue` 需要成對，故 regime 不再進 metric index，
> 標籤本身仍可由 `content_reference` 回溯。
>
> **➕ 2026-08-01 第五輪（同批）：共用 `httpx.AsyncClient` 與 official-mode 測試。**
> ③ 五個 HTTP adapter（rss／cryptopanic／alternative_me／official／binance）全部改為
> `async def` + `await client.get(...)`，`asyncio.to_thread` 只剩 `load_organizer_csv`
> （那是磁碟 I/O，本來就該進 thread）。`build_research_tool_registry()` 建立**單一**
> `httpx.AsyncClient`（明確 connect/read/write/pool timeout）交給所有研究 adapter，
> registry 持有它並提供 `aclose()`，由 `scripts/live_silver_run.py` 在 `finally` 關閉。
> ④ 新增 `tests/unit/data_evidence/test_official_mode_sources.py`（8 測試）：
> official mode 的承諾多半靠「不存在」保證，所以直接**掃描原始碼**——production 不得 import
> `tests`、不得引用 fixtures 目錄、**不存在任何 recorded-response loader**（有人日後加上去，
> 測試就會紅並強迫同時寫 run-mode 閘門）；另含 official mode 真的發出請求、
> `build_request` 在 official 拒絕呼叫端自訂 cutoff、`RunConfigSnapshot` 不得把 official
> 標成 `fixture`／`recorded_fallback`。
>
> **實際跑過的驗證（2026-08-01 第五輪）：**
> `python -m pytest tests/unit tests/contract tests/integration -q` → **1215 passed,
> 15 subtests passed, 0 failed**；`ruff check .` → **All checks passed**；
> `python scripts/verify_s8_s9_s9b.py` → **PASS**；預設 `tests/live` → 12 skipped；
> `RUN_LIVE_TESTS=1` 真實 provider → **8 passed / 4 skipped**（async 改寫後重跑，無 schema 漂移）；
> `python scripts/live_silver_run.py --mode fallback --asset SOL` → `run_20260801_165337_s5337`，
> degraded、四項 artifacts 齊全。
> `src/` 已**零處**引用 `evidence.types`，該檔已不存在。
>
> **凍結路徑處理方式：** `reasoning/` 是凍結路徑，本輪**只新增** `research_extractor.py`
> 與其測試，**沒有修改** `research_agent.py`／`arbiter.py`／`planner.py`／`prompts/` 任何一行；
> 新增檔對應本文原訂的「① `reasoning/research_extractor.py` 尚未搬進 `src/`」。
> `apply_confidence_caps()` 是被**呼叫**，不是被改。
>
> **原始狀態（保留供對照）：** 已在 `main`：`evidence/{policies,types,processor,evidence_json}.py`、
> `adapters/{_assets,cryptopanic,rss,alternative_me}.py`、`data/text_clean.py`。
> **`reddit.py` 已定案不搬**（PR #8 一併移除）。
> **指派：** 任務 C。**相依：** S1 ✅、S5 ✅。
>
> **➕ 加入(2026-08-01,additive、契約安全):事實接地驗證(fact-grounding)。**
> 新模組 `evidence/grounding.py`(純 deterministic、🚫 無 `boto3`/`httpx`):抽取 LLM 抽出事實
> 中的「硬原子」(百分比/金額/數字/日期)並比對是否出現在 `content_reference`,擋掉模型自行
> 補寫的數值/日期(跨語言:英文原文「fell 8%」可佐證中文「下跌 8%」)。分級 verified/partial/
> unverified(contradicted 需語意複核,屬 reasoning 層)。**設計紅線:不動靜態 `reliability`、
> 不加 `EvidenceItem` 欄位**——只走 confidence 上限 + `degradation_notes`/execution_log 揭露
> (路線 A)。若日後要把 grounding 狀態秀在 UI(路線 B,加欄位),需改 `evidence-contracts.md`
> 並經團隊簽核、且趁 Feature Freeze 前。已有 golden 測 `tests/unit/evidence/test_grounding.py`。

**目標**:把新聞與社群的雜訊變成無立場、可查證、去重過的證據。

**元件與職責**（→ [檔案地圖 §4.4](Architecture-FileMap.md)、[§4.5](Architecture-FileMap.md)）
- `adapters/{cryptopanic,rss,official,alternative_me}.py`、`adapters/_assets.py`。
- `adapters/_errors.py` — 正規化錯誤分類（`timeout|http_error|malformed|rejected`），
  以 `[category=…]` token 附在 degradation note 上供 port 包裝讀回。
- `adapters/port_adapters.py` — `RssResearchAdapter`、`CryptoPanicResearchAdapter`、
  `FearGreedResearchAdapter`、`OfficialAnnouncementsResearchAdapter`：
  `fetch(...) -> SourceResult[list[RawSourceRecord]]`，`context` 與散裝參數兩種呼叫皆可。
- `evidence/ledger.py` — ID 配發、排序、排名、`top(n)`、`build_conflict_indicators()`。
- `evidence/processor.py` — `design.md §9` 的八步 deterministic 序列。
- `evidence/grounding.py` — 事實接地驗證（已接進 pipeline）。
- `reasoning/research_extractor.py` — `ResearchExtraction`／`ExtractedFact` schema
  ＋ `complete_extracted_drafts()` deterministic 補完（**新增檔，未改凍結檔**）。
- `application.py` — `build_research_tool_registry()`、`build_research_pipeline()`、
  host allowlist、baseline／optional／反方訊號操作清單。
- `evidence/text_clean.py`（由 P2 的 `data/text_clean.py` 搬來）。

**本階段處理的契約詞彙**：[Features.md §5.3](Features.md)（**靜態 reliability 表——本階段是它的實作者**）、
[§5.2](Features.md)（`SourceType`、`Reliability`、`Stance`）、[§5.4](Features.md)（confidence 上限的輸入端）。

**設定鍵**：`CRYPTOPANIC_API_TOKEN`（缺 → 停用該 adapter 而非讓 run 失敗）、
`HTTP_CONNECT_TIMEOUT_SECONDS`、`HTTP_READ_TIMEOUT_SECONDS`。

**演算法與注意**
- **所有 API / RSS / 研究 payload 一律視為 untrusted data。** 內嵌的指令或政策式文字只能當**引用資料**保存，
  🚫 不得改寫系統政策、deadline、token 上限、工具/網域 allowlist 或 artifact 契約。
- **外部呼叫前**就拒絕未在 allowlist 的 URL / host / provider / operation；
  並驗證 ingestion **不會**變更 static `ToolRegistry`。
- 45 秒 per-call timeout、最多一次受 deadline 約束的 retry；
  缺源或被拒的來源正規化成 typed degradation/gap，**🚫 不讓例外穿過 port**。
- **optional adapter 只在 baseline 路徑穩定後才跑，且其失敗 🚫 不得讓 Silver 失敗。**
- CryptoPanic 的 `independence_group` 用**原始發布者網域**（不是 `cryptopanic.com`）；
  但未實際取得原頁時 reliability 仍是 `low`。
- Fear & Greed：`asset=null`、`source_type=social`、`reliability=low`、group `alternative.me`；
  stale 標記但**不再往下降**；**🚫 不得單獨支撐單幣結論**。
- `content_hash` 只涵蓋正規化後的內容，**排除** source name / URL / 轉載時間戳，
  好讓 byte-equivalent 轉載塌縮。🚫 精確比對，不做模糊。
- 缺 `published_at` → 保留 `null` + 揭露限制，**🚫 不捏造**；
  🚫 `fetched_at` 不得被用來暗示內容比其來源時間新。
- material conflict 只在「同一 claim、雙方 reliability ≥ medium、來自不同 independence group」時成立。

**測試**
- 自動（**已實跑，2026-08-01 第二輪**）：
  ```bash
  # 計畫原訂的 tests/contract/test_research_adapters.py 不存在；
  # mock-transport adapter 測試沿用既有位置 tests/unit/data_evidence/。
  python -m pytest tests/unit/evidence tests/unit/data_evidence tests/unit/reasoning -q
  python -m pytest tests/integration/test_material_conflict.py \
                  tests/integration/test_research_extraction.py \
                  tests/integration/test_composed_research_pipeline.py -q
  python -m pytest tests/unit tests/contract tests/integration -q   # → 1175 passed
  ruff check .                                                      # → All checks passed
  ```
  每個 adapter 至少覆蓋：成功／timeout／HTTP error／malformed payload／空資料。
  另含：注入式文字被當引用資料而非控制輸入、非 allowlist host 在呼叫前被拒、
  allowlist 不可變更、轉載不算獨立來源（byte-equivalent 收合成一筆）、
  material conflict 落盤＋信心上限＋雙方渲染。
  **仍缺：** official mode 拒絕 fixture/recorded 的 adapter 層專門測試。
- 人工：無（provider schema 漂移的驗證在 S11 的 live rehearsal）。

**退出條件**：designated baseline research adapter 能產出正規化、schema-valid 的 Evidence；
optional 來源失敗非阻塞；重複轉載不被算成獨立來源；缺源產生明確 gap 而不是編造事實。

**明確不做**：近似/語意去重、動態 reliability、鏈上/宏觀 adapter、Trust Scorecard（S9）。

---

### S7 — Bounded Planner / Research Agent / Arbiter ✅

> **現況：✅ 已完成並凍結。**
> **已實作：** `adapters/bedrock.py`（371 行）、`reasoning/{planner,research_agent,arbiter,conflict_extension,prompt_library}.py`、
> `prompts/{planner,research-extraction,arbiter}-v1.md`、`tests/contract/test_bedrock_client.py` 與
> `tests/unit/reasoning/`（5 檔）。已合併進 `main`（gate `fc517e7`）。
> `main` 現為 **598 passed，零失敗**（2026-08-01 實跑於 `b84622c`，Python 3.12.13 + 完整 dev 依賴）。
> **⚠️ 已測到的與尚未測到的：** 契約測試是對著 **Bedrock stub** 跑的，而 stub 不做 botocore
> 的參數驗證。Bedrock 本身已由 P2 驗證可用，但**經 `adapters/bedrock.py` 的 `converse` +
> forced `toolConfig` 取回結構化輸出，仍是零次**（→ S0）。
> 「reasoning 完成」不等於「這條路可用」。
> **偏離 ①：順序。** 本階段在 S1（契約凍結）**之前**完成，用 `evidence/types.py` 的 provisional dataclass
> 與 `tests/unit/reasoning/_stubs.py` 頂著。這是刻意的（讓 P3 不必等人），代價是 S1 後要做一輪機械替換並刪 `_stubs.py`。
> **偏離 ②：曾經有兩套 LLM 邊界。** P2 另寫了 `reasoning/llm_client.py` + `gpt_client.py`。
> **已裁決：留 `adapters/bedrock.py`，刪 P2 那兩個**（見 [檔案地圖 §4.6](Architecture-FileMap.md)）。
> **凍結路徑（改動前先找 owner）：** `adapters/bedrock.py`、`reasoning/`、`prompts/`、
> `tests/contract/`、`tests/unit/reasoning/`。
> **指派：** 原 P3；後續型別替換併入任務 A，多事實抽取併入任務 C。

**目標**：在固定 schema 與固定次數的 LLM 呼叫內產生分層、可回溯、保留反方的主張。

**元件與職責**（→ [檔案地圖 §4.6](Architecture-FileMap.md)）

| 元件 | 關鍵簽章／常數 |
|---|---|
| `adapters/bedrock.py` | `BedrockLLMClient.converse_structured(...)`、`effective_timeout()`、`is_retryable_error()`、`build_repair_messages()`、`drain_events()`；`MAX_CALL_TIMEOUT_SECONDS=45.0`、`STRUCTURED_TOOL_NAME` |
| `reasoning/planner.py` | `Planner.run()`、`plan_violations()`、`default_plan_payload()`；`DEFAULT_LOOKBACK_DAYS=14`、`MAX_PLANNED_STEPS=8` |
| `reasoning/research_agent.py` | `ResearchAgent.run()`、`looks_like_injection()`；`INJECTION_MARKERS`、`STATUS_{COMPLETED,PARTIAL,FAILED}` |
| `reasoning/arbiter.py` | `select_evidence()`、`build_evidence_payload()`、`detect_cycle()`、`structural_violations()`、`apply_confidence_caps()`、`Arbiter.run()`、`_fallback()`；`MAX_EVIDENCE_FOR_ARBITER=30` |
| `reasoning/conflict_extension.py` | `DisabledConflictExtension.evaluate()`；`ARBITER_ROUTE`、`DISABLED_STATUS`、`UNIMPLEMENTED_LABEL` |
| `reasoning/prompt_library.py` | `load_prompt()`、`cached_prompt()`、`prompt_versions()`、`Prompt.version_label` |

**本階段處理的契約詞彙**：[Features.md §5.2](Features.md)（`ClaimType`、`Stance`）、
[§5.4](Features.md)（**confidence rubric 與 deterministic 上限——`apply_confidence_caps()` 是它的實作者**）。

**設定鍵**：`BEDROCK_PRIMARY_MODEL_ID`、`BEDROCK_FALLBACK_MODEL_ID`、`MAX_EVIDENCE_FOR_ARBITER`（硬上限 30）。

**演算法與注意**
- Arbiter 的證據挑選順序：**先保全部 high reliability → 再保 material-conflict pair →
  剩餘名額以最大化 distinct independence group 填滿**。
- 送給 LLM 的只有 **ID + normalized fact**，🚫 不送無界原始網頁。
- 一次生成 + **最多一次** repair（共用同一 stage deadline）→ 仍失敗則 `_fallback()`。
- 備援模型**只**用於可重試的可用性/節流失敗，且仍在同一 stage deadline 內。
- log 只記 model ID、operation、latency、attempt、token usage、**prompt 版本**；
  🚫 永不記 prompt 全文、秘密、chain-of-thought。

**測試**（已跑過）
```bash
python -m pytest tests/contract/test_bedrock_client.py tests/unit/reasoning -q
```
- 人工：**S0 的真實 Bedrock 呼叫**——這是本階段唯一還沒被驗證的部分。

**退出條件**（已達成，但 S0 是後補的必要條件）
Arbiter 由 fake LLM 產出 schema-valid `AnalysisResult`；malformed 輸出 repair 一次後走 deterministic fallback；
prompt/schema 版本可供 run config 使用；Research Agent 逃不出靜態 tool plan；
H3 不做任何 Bull/Bear/Judge 呼叫。

**明確不做**：H3 實作、寫 artifact（`reasoning/` 永遠不寫檔）。

---

### S8 — H2-Lite 整合與降級路徑 ★ **Silver Exit**

> **現況：✅ Silver Exit 已於 2026-08-02 實跑通過。**（以下保留通往該結果的工程紀錄）
> PR #18 已接通 canonical seams、deadline-aware H2-Lite、降級與 artifacts；
> `scripts/verify_s8_s9_s9b.py` 離線通過。仍需一次 schema-valid live Bedrock run
> 同時走 designated baseline market/research，以及獨立 deterministic fallback acceptance。
>
> **✅ 2026-08-01 第三輪：先前記錄的「無 Arbiter LLM-output schema」阻塞已解除。**
> 新增 `reasoning/arbiter_output.py`（新增檔，未改任何凍結檔）：
> `ArbiterOutput`／`ArbiterClaim`／`ArbiterLink`／`ArbiterMarketContext`
> ＝ `AnalysisResult` **減去凍結請求脈絡**（`run_id`／`question`／`assets`／
> `analysis_as_of`），且 `market_context.time_range` 與 claim 的 `time_range` 可為 null
> ——這正是凍結 `_fallback()` 產出的形狀。`project_to_analysis_result()` 把凍結脈絡蓋回去、
> 把字串映射為 canonical 列舉、缺失時間範圍以**證據窗口**（最早證據日期 → cutoff）補齊
> 並收斂超出 cutoff 的範圍。投影失敗 = Arbiter 失敗（走 deterministic fallback），不是 run 失敗。
> `pipeline._run_arbiter()` 負責呼叫投影；`application.build_research_pipeline()`
> 在有 `llm` 且未給 arbiter 時自動接上 `Arbiter(result_schema=ArbiterOutput)`。
>
> **踩過的坑（三個，全都會「安靜地」讓 live run 退化，務必別重踩）：**
> ① **LLM 邊界不能用列舉。** 凍結的 `apply_confidence_caps()` 以 `str(...)` 比對
> confidence 與 stance；`str`-mixin 列舉會渲染成 `"Reliability.low"`／`"Stance.supports"`，
> rank 表查不到、`"supports"` 也對不上。若 schema 用列舉，**任何一次信心下修都會弄壞 payload**，
> Arbiter 自己的 re-validate 失敗 → 靜默走 fallback，但外觀看起來像推理成功。
> 因此 `ArbiterOutput` 全部用 `Literal` 字串，列舉只在投影之後出現。
> ② **凍結層讀 evidence 也用 `str()`。** 傳 canonical `EvidenceItem` 時
> `_reliability_rank()` 得到 `"Reliability.high"` → rank 3（未知），於是
> `select_evidence()` 的「先保全部 high」優先序失效、`_fallback()` **一筆 fact 都挑不到**
> （降級報告變成零 claim、零 evidence link，剛好毀掉 fallback 存在的理由）、
> caps 的「只有 low 證據」規則永不觸發。解法沿用既有慣例（`ReasoningRequest` 就是字串化請求視圖）：
> 新增 `EvidenceView`／`ledger_view()` 字串化 ledger 視圖，凍結檔一行都不用改。
> ③ **`_fallback()` 用 `str(item.asset)`** → `"Asset.BTC"`；投影的 `_coerce_asset()`
> 同時吃 `BTC`／`btc`／`Asset.BTC`，無法辨識時改用本次 run 的資產清單並揭露。
>
> **實際跑過的驗證（2026-08-01 第三輪）：**
> `python -m pytest tests/unit tests/contract tests/integration -q` → **1196 passed,
> 15 subtests passed, 0 failed**；`ruff check .` → **All checks passed**；
> `python scripts/verify_s8_s9_s9b.py` → **PASS**。
> 新增 `tests/unit/reasoning/test_arbiter_output.py`（16）、
> `tests/integration/test_arbiter_projection.py`（5，含**強制模型失敗仍產出可回溯降級報告**
> ——Silver 的第二半在離線層已具備）。
> layering 實測：`orchestration/pipeline.py` 與 `reasoning/arbiter_output.py`
> 匯入後皆無 `httpx`／`boto3`；`arbiter_output.py` 無任何寫檔呼叫。
>
> **Silver 仍缺的，只有 live 那一次：** 一次真實 Bedrock Converse + forced `toolConfig`
> 的結構化輸出（經 `adapters/bedrock.py`，至今 0 次），同時走 baseline market 與 research 路徑。
> `application.build_research_pipeline(clock=…, llm=BedrockLLMClient(…))` 即為入口。
>
> **➕ 2026-08-01 第四輪（Move 2）：retry 與 live 腳手架已就位；live Bedrock 仍卡環境。**
> ① **研究來源補上「至多一次」retry**（契約要求，先前是 0 次）：
> `port_adapters.fetch_with_single_retry()`——只對 `timeout`／`http_error` 重試，
> `malformed`／`rejected`／`empty` **不重試**（malformed 再打一次還是 malformed、
> rejected 是缺憑證、empty 是真答案）；jittered backoff 上限 `DEFAULT_RETRY_BACKOFF_SECONDS=1.5`，
> **不自帶時鐘**——取證窗口（`_fork_join`）已擁有 deadline 並會直接取消穿過它，
> 因此 `CancelledError` 原樣重拋（往被取消的窗口裡重試正是 deadline 要防的事）。
> 這條的價值是「正式 run 只有一次」：沒有它，一個瞬時 timeout 就等於那一次 run 的永久來源缺口。
> ② **踩過的坑：揭露通道會被靜默切斷。** retry 成功後 note 原本消失在 registry handler 裡
> （`ResearchAgent` 只聽得到例外）。加了 note 通道後又發現第二層問題：
> 呼叫端自備 `tool_registry=` 時，`build_research_pipeline` 另建的空 list 沒人寫入 → 揭露再次消失。
> 定案：**sink 隨 registry 走**（`ResearchToolRegistry.note_sink`，subclass 不動凍結的 `ports.py`），
> pipeline 以 `getattr(registry, "note_sink", …)` 取用，並在 `execute()` 開頭 `clear()`
> 避免跨 run 誤植。第二個坑：整合測試真的睡掉了 10 秒 → 工廠加
> `retry_backoff_seconds`，測試傳 0.0（steering 明訂測試不得真的 sleep）。
> ③ **live 腳手架**：`tests/live/conftest.py`（`live` marker **與** `RUN_LIVE_TESTS=1` 雙條件，
> 缺一即 skip）、`tests/live/test_bedrock_access.py`（Converse→forced tool→`ArbiterOutput`，
> 並斷言 call event 不含 prompt 全文與任何憑證字樣）、`tests/live/test_live_sources.py`、
> `scripts/live_silver_run.py`（`--mode live|fallback`，印出 run id／terminal state／
> evidence 計數／source types／independence groups／四項 artifact 路徑，即 run-log 需要的欄位）。
>
> **實際跑過的驗證（2026-08-01 第四輪）：**
> `python -m pytest tests/unit tests/contract tests/integration -q` → **1207 passed,
> 15 subtests passed, 0 failed**；`ruff check .` → **All checks passed**；
> 預設 `python -m pytest tests/live -q` → **12 skipped**（確認預設不碰外網）；
> `python scripts/verify_s8_s9_s9b.py` → **PASS**。
> **真實 provider 實跑**（`RUN_LIVE_TESTS=1`）→ **8 passed, 4 skipped**：
> Binance 五幣日 K、baseline RSS、Fear & Greed（`asset=None`）、官方 feed best-effort 全部通過，
> **未發現 schema 漂移**；紀錄在 `docs/rehearsals/live-source-check.md`。
> `python scripts/live_silver_run.py --mode fallback` → `run_20260801_160034_s0034`，
> degraded、3.3 秒、**四項 artifacts 齊全**、5 筆市場證據。
>
> **✅ 2026-08-02：先前卡住的環境阻塞已解除，Silver Exit 通過。**
> 上述「本機無 AWS 憑證、live Bedrock 呼叫 0 次」的狀態已在 D 槽 credentialed
> 環境補完。PR #25 補上 run/data-mode 傳遞與最終
> `RunConfigSnapshot` 重新驗證，並新增 run-mode、provenance、research timeout、
> invalid Evidence、Arbiter failure，以及兩個 opt-in live gate。
> 2026-08-02 已在 Python 3.12.10、`main@21e6f14` 實跑：完整非 live suite
> `1143 passed, 3 skipped`，`ruff check . --exclude .venv312` 為
> `All checks passed!`；另有 Organizer／Binance／baseline RSS component live
> test `1 passed`，Bedrock structured-output component live test `1 passed`。
> PR #26 新增 `test_live_silver_pipeline.py`，把兩條 baseline、Research Agent、
> Arbiter、Renderer 與四項 artifacts 放進同一次 `ApplicationService` run。
> D 槽 credentialed 環境實跑結果：`1 passed in 50.15s`；輸出為 schema-valid
> Bedrock result，且 `run_config.json`、`execution_log.jsonl`、`evidence.json`
> 與 `final_report.md` 四項 artifacts 全數存在。
> **要記下的環境偏離：** 本機 shell 是 **Python 3.13.11**，而專案鎖 3.12、image 用
> `python:3.12-slim`；測試在兩者都綠，但計時與行為結論應在 3.12 上做。

**目標**：把六個 stage 接成一條真的會跑的 pipeline，並讓每一種失敗都有被測過的降級路徑。

**元件與職責**：修改 `application.py`、`orchestration/pipeline.py`、`reporting/artifacts.py`；
新增 `tests/integration/test_{h2_lite_pipeline,degradation,run_modes,provenance}.py`、
`tests/live/test_{live_sources,bedrock_access,live_silver_pipeline}.py`。

**本階段處理的契約詞彙**：全部——本階段是第一次讓 [Features.md §5](Features.md) 的每一張表同時生效。

**演算法與注意**
- 只接 typed same-process port（`SourceAdapter`、static `ToolRegistry`、`ProgressSink`、本機 `ArtifactStore`）。
- **每個 stage 之後都要發 progress event**，並保持增量 artifact。
- **Silver 需要兩個獨立的檢查，缺一不可：**
  1. 一次使用 designated baseline market **與** research 路徑、且產出 **schema-valid Bedrock 結果**的 live run；
  2. **另一次**強制 Bedrock 失敗、走 deterministic fallback 且誠實標示的降級測試。
  **🚫 fallback-only 執行不滿足 Silver。**
- 失敗注入必須覆蓋：market timeout、research timeout、baseline 來源失敗、外部來源全滅、
  optional provider 失敗、無效 Evidence 進場、Arbiter repair 後仍失敗、時間驅動的 optional stage 跳過。
- provenance 測試：報告裡**每一個**市場數字與 conclusion link 都要能解析到 Ledger Evidence；
  每一個 inference/conclusion 依賴都要能回溯到 fact。
- run mode 測試：`official` 拒 fixture；`rehearsal` 允許 deterministic fixture；
  `demo` 可見地標記 recorded；stale/missing/mock/degraded Evidence 全部揭露。

**測試**
```bash
python -m pytest tests/unit tests/contract tests/integration -q
ruff check .
# 另外手動跑（opt-in）：
python -m pytest tests/live/test_live_sources.py tests/live/test_bedrock_access.py -m live -q
python -m pytest tests/live/test_live_silver_pipeline.py -m live -vv -s
```
- 2026-08-02 traps：自訂 venv 名稱 `.venv312` 不在 Ruff 預設排除範圍，需顯式
  `--exclude .venv312`；component source／Bedrock tests 分開通過仍不等於同一次完整
  Silver run；沙盒 pytest 須指定可寫的 `--basetemp`，否則 Windows temp ACL 會產生
  setup errors（非產品測試失敗）。
- 人工：live Silver 的部分見 [§3.2 的 S11 清單](#32-只能由人驗證的部分人工檢查清單)。

**退出條件（★ Silver Exit）**
Bronze 仍綠；一次單幣 live run 經兩條 baseline 路徑產出 schema-valid Bedrock 結果；
**另有**一次 deterministic fallback/降級測試通過；optional 來源失敗非阻塞；
所有被接受的 claim 仍可回溯到 Evidence；artifact 失敗遵守揭露契約。

**2026-08-02 結果：上述退出條件全部滿足，S8／Silver Exit = ✅。

**明確不做**：R16（S9）、雙資產驗收（S10）、部署（S11）。

---

### S9 — 創意層：信任提煉與市場洞察（Requirement 16）

> **現況：✅ 離線功能完成。**
> `evidence/trust.py`、canonical regime/unavailable、Evidence-backed invalidation 與 renderer
> 已由 PR #18 合併並通過離線驗收；完整 repository pytest/Ruff 仍屬全案 gate。

**目標**：把既有的嚴謹度「顯影」成評審一眼看得懂的東西，而**不**變成第二個真相來源。

**元件與職責**（→ [檔案地圖 §4.3](Architecture-FileMap.md)、[§4.5](Architecture-FileMap.md)、[§4.7](Architecture-FileMap.md)）
- `evidence/trust.py` — 純函數 `(ledger, links, conclusions) -> TrustScorecard[]`；🚫 無網路、無 LLM、無檔案系統。
- `data/regime.py` — `classify(bars, thresholds) -> MarketRegime`。
- 修改 `data/market_worker.py`（發出 regime 與門檻 Evidence）、`models.py`、
  `reporting/renderer.py`、`reasoning/arbiter.py` + `prompts/arbiter-v1.md`。

**本階段處理的契約詞彙**：[Features.md §5.2](Features.md) 的 `TrustLevel`、`RegimeLabel`、`InvalidationOperator`；
規範性映射在 `evidence-contracts.md §16`。

**演算法與注意**
- **Trust Scorecard 的固定映射**：`source_independence` — `strong` 需 ≥3 distinct groups、`moderate`=2、
  `weak`=1、`unavailable`=0；`source_diversity` 同理但看 distinct `source_type`；
  `consistency` — 有 `ConflictIndicator` 就是 `weak`（硬上限），否則 `opposing_count==0` 為 `strong`、其餘 `moderate`；
  `freshness` — 最新支持證據在設定的新鮮窗內且無 stale 為 `strong`、有關鍵 stale 為 `weak`、
  其餘 `moderate`、無可用時間為 `unavailable`。
- **只為 `conclusion` 產生 scorecard。** 標了 `strong` independence 卻只連到 <2 個 group 是**驗證錯誤**，不是警告。
- **Market Regime 判定順序（先中先贏，全部對該資產自身 rolling 歷史）：**
  ① `realized_vol_pctile >= high_vol_pctile` → `high_volatility`；
  ② `abs(return_window) >= trend_return_abs_min` → `trending_up`/`trending_down`（看正負號）；
  ③ `abs(return_window) <= range_return_abs_max` → `range_bound`；④ 其餘 → `mixed`。
- regime 打包成 `reliability=high`、`source_type=market` 的 `EvidenceItem`，
  **保留 metrics 與 thresholds**（同時進 `run_config.json`）；🚫 LLM 不得指派或改寫。
- 量化 invalidation：`threshold` 必須**等於**被引用的 deterministic `EvidenceItem` 攜帶的值；
  `basis_evidence_id` 必須能在 ledger 解析。**🚫 LLM 不得自造數字。** 無法量化才退回純文字。
- **任何面向/標籤/門檻算不出來 → 標 `unavailable` + 揭露原因，🚫 不編造，
  且 🚫 不得阻塞四項 artifacts、Bronze 或 Silver。**
- scorecard 用 ordinal pips + 計數 + 一行理由呈現，**🚫 不用單一未校準百分比**。禁語 lint 仍最後跑。

**測試**
```bash
python -m pytest tests/unit/evidence/test_trust.py tests/unit/data/test_regime.py \
                tests/unit/reporting/test_creativity_render.py -q
ruff check .
```
golden 測試要用**可手算**的 OHLCV fixture；驗證 coin-agnostic（門檻用各資產自身歷史）
與缺 bar → `label="unavailable"`。

**退出條件**：scorecard / regime / 量化 invalidation 都是 deterministic、coin-agnostic、
與 confidence 一致、無 LLM 自造數字、無投資建議、無未校準機率，
且缺資料時明確降級為 `unavailable` 而不阻塞核心閘門。

**明確不做**：任何新外部來源、任何 LLM 呼叫、任何合成分數。

---

### S9B — 雙幣比較（Requirement 17）

> **現況：✅ 離線功能完成。**
> PR #18 已完成單一 run/cutoff/ledger、交集 UTC 日期比較 Evidence、
> asset/source-balanced Arbiter projection、雙資產比較 Claim 與雙幣限定第 12 段。
> UI 第二資產控制仍由 S3 接線；這不影響本階段離線核心判定。

**目標**：讓一次雙幣 run 真的回答「這兩個幣相比如何」，而不是把兩份單幣分析並排。

**為什麼是單一 run**（這一點決定了整個階段的形狀）
比較只有在兩個資產的證據進入**同一個 Arbiter payload** 時才可能存在。拆成兩個 run 還會同時破壞三條已凍結的不變量：
Evidence ID 是 **run-local**，所以 `ev_007` 會有兩種意思；每個 run 各自凍結 `analysis_as_of`，
比較本身就沒有單一 cutoff；跨 run 的比較產物需要第五項 artifact 或新檔名，兩者都被禁。
所以雙 run 是**被契約否決**，不是被排序延後。

**元件與職責**（→ [檔案地圖 §4.3](Architecture-FileMap.md)、[§4.6](Architecture-FileMap.md)、[§4.7](Architecture-FileMap.md)、[§4.8](Architecture-FileMap.md)）
- `data/market_series.py` — 多資產載入路徑，回傳對齊同一 UTC `date` 索引的各資產序列；
  對不齊或缺 bar → 該比較 `unavailable`，🚫 不 forward-fill。
- `data/indicators.py` — 只用 Requirement 13 允許的尺度：區間報酬差、以**各自百分位**表達的波動比較、
  相對強弱比值與其自身歷史百分位、同 provider 同期間的 quote volume 比較。
  相關性／beta 為 optional，若輸出必須宣告 window。
- `data/market_worker.py` — 除各資產指標外，另發比較型 `EvidenceDraft`，
  每筆記錄兩個資產、共同 `time_range`、所用尺度與參數；`reliability=high`、`source_type=market`。
- `reasoning/arbiter.py` — `select_evidence()` 加**per-asset 配額**。
  ⚠️ **凍結路徑**，動之前必須取得 owner 同意（見下方「已知技術阻塞」）。
- `reporting/renderer.py` — 只在 `assets` 有兩個資產時輸出「跨幣比較」段落。
- `ui/presenter.py`、`streamlit_app.py` — 第二幣為**明確加選**，預設仍是單幣。

**本階段處理的契約詞彙**：[Features.md §5.1](Features.md)（`assets` 一至二）、
[§5.2](Features.md)（`Asset`）、[§5.5](Features.md)（四項 artifacts 不變）；
規範性定義在 `requirements.md` Requirement 17 與 Requirement 13、`design.md §20`。

**已知技術阻塞（動工前先解決）**
`select_evidence()` 目前**完全沒有資產概念**：它先無上限地收下**所有** high-reliability 項目，
再收 conflict pair，最後才按 `independence_group` round-robin。而市場證據**全都是** `high`——
所以雙幣 run 很可能在還沒碰到任何新聞證據之前就把 30 個名額用完，
而且不保證兩個資產各拿到多少。這是**必須修的正確性問題**，不是調參。
`asset=null` 的全市場項目（如 Fear & Greed）不計入任一資產配額。

**演算法與注意**
- **🚫 永遠不比較不同幣的 base-asset `volume`。** 跨幣流動性只用同 provider、同期間的 quote volume，
  否則標 `unavailable`。這條是三份文件的硬規則，也是讓比較誠實的那條線。
- 比較型 Claim 的 `assets` 必須同時含兩個資產；數值全部來自 deterministic tool output 且可回溯 Evidence ID。
- **Market Regime 維持每個資產各一個標籤**，🚫 不得合併成單一標籤。
- confidence 上限與 material conflict 規則**完全不變**，照 claim 逐一套用。
- **🚫 比較不得變成相對買賣建議**（例如「A 優於 B 所以換倉」）；禁語 lint 仍最後跑。
- 取證預算：兩個資產在**同一個 270 秒**窗口內約兩倍工作量，per-call timeout 仍是 45 秒。
  預算吸收不了時依既有跳過順序處理，🚫 不得延長 stage。

**測試**
```bash
python -m pytest tests/unit/data/test_cross_asset.py \
                tests/unit/reporting/test_comparison_render.py \
                tests/integration/test_dual_asset_run.py -q
python -m pytest tests/unit tests/contract tests/integration -q   # 單幣路徑不得退化
ruff check .
```
必含：單一 `run_id`／單一 cutoff／一份 Ledger／四項 artifacts（🚫 無第二個 run、🚫 無第五項 artifact）；
可手算的跨幣 golden 值；base-volume 比較被**拒絕**；兩個資產都進得了 Arbiter payload；
段落只在雙幣 run 出現；缺一個資產時比較標 `unavailable` 且四項 artifacts 仍齊全。

**退出條件**
一次雙幣 run 產出至少一個 `assets` 含兩個資產的比較型 Claim，其每個數字都可回溯 Evidence；
只用 Requirement 13 的尺度；兩個資產都有 Evidence 進入 Arbiter；「跨幣比較」段落正確渲染；
單幣路徑的既有測試全部仍綠。

**退場條款（Feature Freeze 前未完成時）**
UI 停用第二幣加選、只接受單幣請求，並在文件與簡報揭露此能力未交付。
**🚫 不得交付半完成或未驗證的比較路徑，🚫 不得以單幣結果冒稱比較結果。**

**明確不做**：新 model 欄位、新 artifact、新檔名、改 `run_id` 語意、
為比較另開第二個 run、雙幣的視覺化 polish。

---

### S10 — Gold local Exit：兩個資產各跑一次獨立單幣 run

> **現況：🟡 自動 acceptance 與兩資產獨立 run 已完成；complete-Evidence run 卡在 Bedrock 帳號開通。**
>
> **2026-08-02（`agent/s11-delivery` @ `c844a38`）實跑：**
> - `tests/acceptance/test_{gold_assets,artifact_contract,deadline_budget}.py` 建立 → **29 passed**。
> - `scripts/run_acceptance.py` 建立；離線（organizer CSV）與 live baseline 各跑一次 BTC/ETH
>   獨立單幣 run，共四次 run，全部四項 artifacts 齊全、run_id 互異、ledger 不互相污染。
> - `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q`
>   → **1266 passed**；`ruff check .` → **All checks passed!**。
> - run ID／時長／降級／artifact 路徑全部記在 `docs/rehearsals/run-log.md`。
>
> **踩到的坑（留給後面的人）：**
> 1. `tests/acceptance/` 先前不存在，但 `tasks.md` 的 Final Required Gate 與本文 S11 的閘門指令
>    逐字包含它 → pytest 會 `ERROR: file or directory not found`。閘門指令根本跑不完。
> 2. 「deterministic rendering」不等於 byte-identical：`fetched_at` 是 provenance（本 process
>    何時讀到來源），CSV 讀取的取得時間本來就是當下牆鐘，兩次相同輸入必然差幾秒。
>    acceptance 測試把它正規化後比對，並另有一條測試釘住「唯一容許漂移的欄位就是 `fetched_at`」。
> 3. ~~Bedrock 帳號未開通~~ **已解除**（帳號換成主辦方 AWS Workshop Studio 帳號後 3/3 呼叫成功）。
>    但解除之後才發現真正的阻塞：`docs/rehearsals/run-log.md` 尾段記錄七次 live run，
>    Arbiter 都在時間內完成，**卻只有一次真的產出結論層 claim**——其餘六次結論層是空的
>    （`claims` 本身 0 筆，非渲染端丟棄），而且 Planner 的資產比對在指令碼路徑會因
>    `str(Asset.BTC) != 'BTC'`（Python 3.11+ enum `__str__` 行為）永遠判定計畫違規、
>    退回決定論預設計畫。兩者都在凍結的 `reasoning/`，需 owner 決定才能修。**因此 S10
>    仍不得記為完成**——阻塞的性質從「帳號」變成「reasoning 層兩個未修的正確性缺陷」。
>
> **指派：** 全員；任務 A 擁有這個閘門。相關缺陷修復已寫成 Kiro 任務，見
> [§9](#9-賽後延續工作task-13-21)（本文未新增獨立 task 編號給這兩個缺陷本身——它們是
> 既有 reasoning/ 凍結路徑的 bug fix，不是新範圍，建議 owner 直接在 `reasoning/` 修，
> 修完後回頭勾選本節與 `docs/rehearsals/run-log.md`）。

**目標**：用兩個**不同**資產各自的獨立單幣 run，證明 pipeline 真的是 coin-agnostic。

**元件**：`tests/acceptance/test_{gold_assets,deadline_budget,artifact_contract}.py`、
`scripts/run_acceptance.py`、`docs/rehearsals/run-log.md`。

**本階段處理的契約詞彙**：[Features.md §5.2](Features.md)（`Asset` allowlist）、
[§5.5](Features.md)（四項 artifacts）、[§5.6](Features.md)（deadline 預算）。

**演算法與注意**
- 選兩個 baseline 路徑能產出完整 Evidence 的資產，**各跑一次獨立單幣 run**；
  **🚫 不要合併成雙幣比較**——這個閘門證明的是「流程幣種無關」，
  雙幣比較有自己的階段與驗收（S9B / Requirement 17），兩者不得互相代替。
- 保留五幣**請求 allowlist** 測試，但 🚫 不要求五幣完整驗證矩陣或五幣校準。
- fake-clock deadline 驗收：證明第 12 分鐘取消非必要呼叫、finalize 在保留期之前開始。
- 把兩個 run 的 run ID、資產、模式、時長、降級結果與 artifact 路徑記進 `docs/rehearsals/run-log.md`。

**測試**
```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
```

**退出條件（★ Gold local Exit）**
Silver 已過；兩個不同資產各自以獨立單幣 run 通過；必要的降級檢查通過；deterministic artifact 檢查通過。
**明確排除在這個本地閘門之外：** Docker build/runtime 驗收、ECR 部署、EC2 部署、
完整計時的評審流程彩排、提交驗證。
**達到這個閘門即觸發 Feature Freeze**（若 Day 2 中午尚未先觸發）。

**明確不做**：部署、彩排、任何新功能。

---

### S11 — Feature Freeze、部署與計時彩排

> **現況：🟡 本地交付層完成；雲端與彩排未開始。**
>
> **2026-08-02（`agent/s11-delivery` @ `c844a38`）實跑：**
>
> | 項目 | 狀態 | 實際證據 |
> |---|---|---|
> | `.github/workflows/ci.yml` | ✅ | verify／container／secret-scan 三個 job，皆不需 AWS 憑證 |
> | `scripts/smoke_test.py` | ✅ | 純標準庫；HTTP health/root ＋ 四項 artifact 解析與 run_id 一致 |
> | `docker build` | ✅ | `hoya-agent:c844a38`，860 MB |
> | 本地 runtime | ✅ | 容器 `Up (healthy)`；`/_stcore/health` → `ok`；`/` → 200、10 626 bytes |
> | **容器內** smoke | ✅ | `docker cp` ＋ `docker exec` → 四項 artifacts、6 log events、5 evidence、run_id 一致 |
> | 非 root | ✅ | `docker exec … id` → `uid=10001(appuser)` |
> | image 無秘密 | ✅ | `/app` 內無 `.env`、無 `*.pem`／`*.key` |
> | `docker compose config` | ✅ | VALID |
> | secret scan | ✅ | gitleaks v8.28.0：追蹤內容 315 檔 no leaks；全歷史 206 commits no leaks |
> | ECR repository | ✅ | `hoya-agent`，IMMUTABLE ＋ scanOnPush；tag `2cd9b43`、`c844a38` |
> | EC2 部署 | ✅ | `i-000a2cdc6d3c1afab`，t3.small AL2023 @ us-west-2a |
> | 公開 healthcheck | ✅ | `http://35.91.36.186:8501/_stcore/health` → `ok` |
> | tag 逐字相同 | ✅ | `docker inspect` → `…/hoya-agent:2cd9b43`，與推上 ECR 的完全一致 |
> | EC2 上容器內 smoke | ✅ | 四項 artifacts、6 log events、5 evidence、run_id 一致 |
> | 零金鑰 | ✅ | IAM instance role `hoya-agent-ec2`；SG 只開 8501 給單一來源 IP，**不開 22**，管理走 SSM；IMDSv2 強制 |
> | rollback 演練 | ✅ | 回退 `c844a38`（20 秒健康）→ 前滾 `2cd9b43`（20 秒健康） |
> | CSV/Binance 重疊檢查 | ✅ | 五幣 31 天，close 差異 **0.0000%**；🚫 但不得因此宣稱 CSV 來自 Binance |
> | recorded fallback（版控外） | ✅ | `hoya-demo-fallback
un_20260802_015425_demo1`，報告標示 demo ＋ 原始時間 |
> | **15 分鐘計時彩排** | 🔴 | **未執行 —— 人工項目，腳本見 `docs/demo-runbook.md`** |
>
> **踩到的坑：**
> 1. **UI 的 artifacts 寫在容器內的 `tempfile.mkdtemp()`**（`ui/streamlit_app.py`），host 端程序看不到。
>    所以 smoke test 必須用 `docker exec` **在容器內**跑，才是在驗「部署的那個 image」而不是 host 的碼。
>    而 `.dockerignore` 排除了 `scripts/`，所以要先 `docker cp` 進去。
> 2. **gitleaks 不能直接掃 checkout 目錄**：整棵依賴樹會噴 125 筆 false positive（botocore／numpy／
>    pyarrow 自帶的範例金鑰），真發現會被淹掉。CI 改成掃 `git archive HEAD` 解出來的追蹤內容。
> 3. 在 Git Bash 下 `docker exec … /tmp/x.py` 會被 MSYS 改寫成 Windows 路徑，要 `MSYS_NO_PATHCONV=1`。
>
> **指派：** 任務 A 與 D 共同主導；全員參與彩排。

**目標**：在不加新功能的前提下把東西送上去，並完成一次完整計時的評審流程彩排。

**元件**：`.github/workflows/ci.yml`、`docs/deployment.md`、`docs/demo-runbook.md`、
`docs/architecture.md`、`scripts/smoke_test.py`、修改 `README.md`。

**演算法與注意**
- **Feature Freeze 在 Gold local Exit 或 Day 2 中午（取較早者）立即開始。**
  之後只准：bug fix、可靠性修復、部署、彩排、文件、rollback 準備、提交驗證。
- **凍結後拒絕**：新功能、新 provider、新 artifact 格式、PDF/HTML 需求、額外視覺化、
  五幣矩陣、Platinum 能力、H3 實作。
- 建 image → 驗本地 runtime → push commit-SHA tag 到 ECR → 用 `docker compose` 部署**那個 immutable tag** 到單台 EC2。
  文件記環境變數名稱、healthcheck 與 rollback 指令，🚫 不含秘密。
- 在**原始碼控制之外**保存一次完整的 recorded fallback run，並記錄 `demo` 模式如何呈現其原始時間戳與 recorded 狀態。
- 完成**一次**完整 15 分鐘計時的評審流程彩排（從輸入題目到檢視 artifacts），
  記下 run ID、模式、時長、來源缺口、artifact 路徑。**額外彩排是 optional，且不得延誤部署或提交。**

**測試**
```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short
```
- **人工（必要）：** [§3.2 的 S11 清單](#32-只能由人驗證的部分人工檢查清單)。

**退出條件**：Feature Freeze 用了較早的核准觸發點；Docker 本地 runtime、ECR 與 EC2 交付檢查完成；
恰好一次完整計時的評審流程彩排已完成；demo fallback 誠實；rollback 與提交證據有文件；
H3 三處都標示未實作；secret scan 通過。

**明確不做**：任何凍結後的新功能。

---

## 6. 里程碑地圖

| 里程碑 | 階段 | 交付的成果 |
|---|---|---|
| **M0 可執行性** | S0 · S1 | 外部服務證實可用；共用契約凍結；四人可並行 |
| **M1 Bronze** ★ | S2 · S3 | **完全離線**從 Streamlit 產出並下載四項 artifacts |
| **M2 能力層** | S4 · S5 · S6 · S7 | deadline 編排、市場證據、研究證據、bounded reasoning 各自可驗證 |
| **M3 Silver** ★ | S8 | 一次 live schema-valid Bedrock run **＋** 一次獨立的 deterministic fallback |
| **M4 洞察** | S9 · S9B | Trust Scorecard、Market Regime、量化 invalidation、雙幣比較（皆非阻塞，皆須在 Freeze 前） |
| **M5 Gold local Exit** ★ | S10 | 兩個不同資產各一次獨立單幣 run + 降級檢查 → **觸發 Feature Freeze** |
| **M6 交付** | S11 | ECR/EC2 部署 + 一次 15 分鐘計時彩排 + 提交驗證 |

---

## 7. 可追溯性：能力目錄 → 階段

| [Features.md](Features.md) 章節 | 由哪些階段實作 |
|---|---|
| §1 取證 — 建立分析請求 | S1（契約）· S2（application 驗證）· S3（UI 輸入） |
| §1 取證 — 市場資料與指標 | **S5**（＋ S9 的 regime 與門檻 Evidence） |
| §1 取證 — 研究資料 | **S6**（＋ S7 的 bounded 抽取） |
| §1 取證 — Evidence 處理 | **S6**（policies 已在 `main`） |
| §2 推理 — Planner / Arbiter / Claim 分層 / conflict / H3 | **S7 ✅**（＋ S8 的整合驗證） |
| §3 交付 — 四項 artifacts | **S2**（契約）· S8（降級路徑）· S10（驗收） |
| §3 交付 — 繁中報告與禁語 lint | **S2**（renderer）· **S3**（lint）· S9（R16 區塊）· S9B（跨幣比較段落） |
| §3 交付 — 執行紀錄與可重現性 | S2（形狀）· S4（stage 事件）· S8（完整串接） |
| §3 交付 — 誠實性機制（三模式） | S3（UI 標示）· S8（run mode 測試） |
| §3 交付 — Deadline 治理 | **S4**（＋ S10 的 fake-clock 驗收） |
| §3 交付 — Streamlit 介面 | **S3** |
| §4 信任提煉（R16） | **S9** |
| §5.1 `assets` 一至二 / 跨幣比較（R17） | **S9B**（＋ S1 契約、S3 的 UI 加選控制） |
| §6 系統與基礎設施 | S1（設定/時鐘）· S3（容器殼）· S11（部署） |
| §7 外部相依面 | S1（`ports.py`）· S5/S6（adapter 實作）· S7 ✅（`bedrock.py`） |

**沒有任何一個 Features.md 章節沒有對應階段。**

---

## 8. 帶著往前走的未決事項

這些**不假裝已經解決**；每一項都標了必須在哪個階段之前裁決。

| # | 未決事項 | 必須在何時裁決 | 目前傾向 |
|---|---|---|---|
| ~~1~~ | ~~`price_analysis.py`、`analogs.py` 不在 canonical tree~~ | ~~S5 搬檔之前~~ | ✅ **已定案（PR #8）**：`price_analysis.py` 保留為獨立模組並納入 canonical tree；`analogs.py` 未建立 |
| ~~2~~ | ~~`okx.py`、`reddit.py` 不在 canonical tree~~ | ~~S5 / S6 搬檔之前~~ | ✅ **已定案（PR #8）**：`okx`、`reddit`、`coingecko`、`derivatives`、`google_news` 五個來源共十個檔**不搬**，對齊 `evidence-contracts.md` |
| 3 | ~~`evidence/types.py` 的退場時機~~ | ~~S6 完成之前~~ | ✅ **已結案（2026-08-01 第五輪）**：`evidence/types.py` 已刪除；`evidence/drafts.py` 的 `PendingEvidence`（canonical draft ＋ provenance）成為唯一 draft 型別，reliability／independence group／hash／id 全由 `evidence/processor.py` 指派。順帶刪除非 canonical 的 `evidence/evidence_json.py`。`data/types.py::MarketBar` 保留——`models.py` 沒有 MarketBar，它不是重複型別 |
| ~~4~~ | ~~designated baseline **research** source 是哪一個~~ | ~~S8 Silver 驗收之前~~ | ✅ **已定案（S0 實測）**：第一手新聞 RSS + Google News 依幣種搜尋（免 key、五幣覆蓋）；CryptoPanic 取得 token 後可升為主 |
| ~~8~~ | ~~`p2-etl-mvp/` 的退場時機~~ | ~~S3 完成之前~~ | ✅ **已結案（2026-08-03，`69c019f`）**：71 個檔已整批刪除，確認 `src/`／`tests/` 無任何 import 依賴後執行，刪除前後測試數不變（1304 → 1304，`ruff check .` 全綠）；`.dockerignore` 同時移除死掉的排除規則 |
| ~~9~~ | ~~`ruff check .` 的 87 個錯誤~~ | ~~下一階段開工前~~ | ✅ **已清空（2026-08-01 實測）**：`ruff check .` → All checks passed |
| ~~10~~ | ~~`_provisional_seams.py` swap procedure~~ | ~~S3 或 S4 開工前~~ | ✅ **已結案**：`_provisional_seams.py` 與 `test_s1_seam_bridge.py` 已刪除，runtime imports 全部指向 canonical `models.py`／`ports.py`（見 `docs/ACTIVE_WORK.md` S1 現況） |
| ~~8b~~ | ~~`reasoning/arbiter.py` 的 `select_evidence()` 需加 per-asset 配額，但它是凍結路徑~~ | ~~S9B 動工之前~~ | ✅ **已結案**：S9B 現況記錄「balanced Arbiter projection」已落地，兩個資產各自都能進 Arbiter payload |
| 5 | 15 分鐘是否含題目輸入與評審檢視時間 | 主辦方確認前不阻塞 | 實作一律**從 run 開始**計時；比賽已結束，此項不再會有主辦方回覆，維持現行判斷即可 |
| 6 | 主辦方 CSV 算不算一個獨立 `independence_group` | 同上 | 暫計為一個（`organizer-public-market-data`） |
| 7 | 「第一手/官方來源」的界定 | 同上 | 暫指原始資料產生者：交易所 API、專案官方公告、主辦方 CSV |
| 11 | **Arbiter 結論層 claim 在 live run 下不穩定**（七次 live run 僅一次產出結論層 claim，其餘信心正常但 claims 為空） | **S10 complete-Evidence run 之前** | 新增項（2026-08-03 覆核 `run-log.md` 發現）。**2026-08-03 offline 覆核（無 live AWS 憑證，僅讀程式碼）：** `composition.py::MappingArbiter.run()` 的重試/揭露機制本身是對的——`claims=[]` 且 `insufficient_data=False` 會觸發第二次嘗試，兩次都退化才用 `ensure_honest_insufficiency()` 誠實揭露，不會謊報信心；`reasoning/mapping.py::build_analysis_result` 也沒有靜默丟棄 claim（`run-log.md` 自己用 spy 驗過，模型原始輸出就是 0 筆）。也就是說**不是安全網漏了，是模型在 `max_tokens=3000` 下常常真的沒輸出 claims**——3000 是為了不撞 45 秒上限才調低的（6000 就 `DeadlineExceeded`），但可能同時讓模型在讀完 20-30 筆證據後沒有預算再產出結構化 claims。這只是一個**假說**，沒有 live Bedrock 憑證無法驗證（例如：固定證據數、只調 `max_tokens`/`max_evidence` 掃描哪個組合能穩定產出 claims 又不逾時）。修點在凍結的 `reasoning/`，需 owner 決定；**建議在比賽帳號被收回前優先跑這組實驗**，之後可能再也無法用同一組帳號重現 |
| ~~12~~ | ~~指令碼 live 路徑的 Planner 資產比對永遠判定違規~~（`str(Asset.BTC) != 'BTC'`） | ~~S10 complete-Evidence run 之前~~ | ✅ **已結案（2026-08-03，不需 live AWS 即可驗證）**：`reasoning/planner.py` 新增 `_asset_str()`（讀 `.value`，同 `orchestration/pipeline.py::_enum_value` 的既有寫法），`plan_violations()` 改用它比對雙方。用真正的 `models.ResearchPlan`/`Asset.BTC` 寫回歸測試，修前紅（`"plan changed the requested assets to ['Asset.BTC']"`）、修後綠。全部套用既有 fake-LLM 測試基礎設施，未動任何需要 live Bedrock 才能驗證的路徑 |

> 主辦方若給出不同的正式解釋，**先更新 steering 與 requirements，再改行為**；🚫 不得只改 prompt。
> 項目 11、12 兩條 live 缺陷的修復尚未寫成獨立 Kiro task——它們是既有 Task 6/8（reasoning／Silver）
> 凍結路徑裡的 bug，不是新範圍。建議直接指派給熟悉 `reasoning/` 的 owner 修，紅→綠→重跑
> S10 的 complete-Evidence acceptance，而不是併入 Task 13-21 的新功能開發。

---

## 9. 賽後延續工作（Task 13-21）

> 比賽已於 2026-08-02 結束；S0-S11（= `tasks.md` Task 0-12）是已出貨的競賽 MVP，凍結不動
> （除非修真的 bug，如上方項目 11、12）。這裡不重複 S0-S11 的完整範本，只記重點與指到哪裡看細節——
> **規範性內容一律在 `.kiro/specs/hoya-market-agent/tasks.md` Task 13-21**，本節只是索引。

`.kiro/steering/competition-rules.md` 與 `development-workflow.md` 已同步更新（2026-08-03），
明確解除「不得擴張 MVP 到 H3／S3／CloudWatch／額外 adapter」與「Day 2 feature freeze」這兩條規則
對 Task 13 起的效力，否則 Kiro 每次啟動都會讀到這兩份 always-included steering 檔而拒絕動工。
除了範圍限制解除，本檔案其餘每一條規則（誠實揭露、deterministic 邊界、無 secret、deadline）
對 Task 13-21 仍然全部有效。

| Task | 一句話 | 狀態 | 備註 |
|---|---|---|---|
| **13** 刪除 `p2-etl-mvp/` | 移除 71 個檔的重複原型樹 | ✅ 已完成（2026-08-03，`69c019f`） | 見 §8 項目 8 |
| **14** 接上跨源三角驗證（G2） | `evidence/triangulation.py` 已寫好、有測試，但沒接進 pipeline | ✅ 已完成（2026-08-03） | 實作時發現原規劃有誤：`triangulate()` 需要 `anomaly_days(bars)`，而 `bars`（原始 OHLCV）不在 `evidence.json` 裡，純 UI 端算不出來——G3 的「只讀 evidence.json」模式不適用。改為讓 `OrganizerCsvPipeline`／`DeadlineAwarePipeline` 在 `execute()` 後暴露 `last_bars_by_asset`（沿用既有 `last_metric_index` 的寫法），UI 直接複用 run 已經載入的 bars,不重抓、不碰契約。全部測試綠、`ruff` 乾淨 |
| **15** agent 判斷可視化（G4） | Planner 其實已經依題目挑不同 operation，但選擇本身與理由從未呈現給評審 | ✅ 已完成（2026-08-03） | 新增 `plan_decision` execution_log 事件 + presenter `agent_judgment_view` + Streamlit「Agent 判斷」面板。實作時抓到一個真的回歸：新事件原本插在 Planner 既有的 try/except 裡,`test_fork_join.py` 的 `FastPlanner`(裸 `object()`,沒有 `allowed_operations()`)一撞就是 `AttributeError`,被 except 接住後想再 settle 一次已經 settle 過的 stage,炸掉 3 個原本綠的測試。已修(搬到 try/except 外、`allowed_operations` 改防禦性讀取) |
| **16** G1 語意複核 | 純質性事實的語意層複核（走 `LLMClient`），確定性硬原子比對已完成 | 🟡 引擎完成，未接進 live pipeline（2026-08-03） | 實作時發現 `confidence_signals_for_claim` 全倉庫零呼叫點——Task 5 做的確定性版本本身就還沒接進 live Arbiter。沒有 live AWS 憑證的情況下，在自己的前置依賴都還沒上線時搶先接一個新的 live LLM 呼叫，判斷順序不對。已交付：`reasoning/semantic_grounding.py`（fake LLM 測試）＋ `evidence/ledger.py` 的 `semantic_status` 參數，兩者都是惰性的，不呼叫就不影響現有行為 |
| **17** H3 條件式辯論 | 真正實作 Bull/Bear/Judge，`enable_conditional_debate` opt-in | 🔴 未開始 | 觸碰目前唯一的凍結元件 `DisabledConflictExtension`，需 owner 同意 |
| **18** CoinGecko 次要來源 | 接成 optional，永不當 baseline | ✅ 核心已完成（2026-08-03） | 用 `/simple/price` 快照(非原規劃的 `/market_chart`)；`SourceClass.MARKET_AGGREGATOR` 早就在 `evidence/policies.py` 裡且註解寫著給 CoinGecko 用，直接沿用。`extra_drafts` 一個 pipeline 只吃一個 callable，新增 `combine_extra_drafts()` 讓它跟既有的 Fear & Greed 共用同一個插槽。**未做：** 與 Binance 價差的揭露比對——`metric_value` 已經備好，但要嘛改 `extra_drafts` 的呼叫簽章、要嘛跑完 ledger 後再對 `metric_index` 做一次後處理，兩者都比這次的核心驗收再重一截，留給下一手 |
| **19** 五幣完整驗證矩陣 | 把 Task 9 的兩資產模式擴到全部五幣 | ✅ 已完成（2026-08-03，offline） | 新開 `tests/acceptance/test_five_asset_matrix.py`，刻意不動 Task 9 自己的 `test_gold_assets.py`（已通過的 Gold 閘門，避免被本次擴充的工作連帶弄壞）。五幣 offline 皆為 `degraded`（`OrganizerCsvPipeline` 本來就無 Arbiter），與 BTC/ETH 基準一致，非新缺口；live 基準線的已知缺口（帳號臨時、結論層不穩）與資產無關，未逐幣重跑 |
| **20** PDF/HTML 匯出與額外視覺化 | 在 PR #29 既有的自包含 HTML report 基礎上加 | 🟡 PDF 已完成（2026-08-03）；圖表視覺化未做 | HTML 早就有了。PDF 踩到兩個真的坑：① 既有畫面版 CSS 用 `var(--x)` 等現代語法，直接餵給 `xhtml2pdf` 直接炸掉，改成從 `final_report.md` 的純文字轉出一份極簡、xhtml2pdf 安全的 HTML；② 繁體中文完全不顯示（`xhtml2pdf` 內建字型沒有 CJK 字形），註冊 Adobe 標準 CJK CID 字型 `MSung-Light` 後解決——用 `pypdf` 把 PDF 文字層抓出來逐字比對驗證，因為這個 session 自己用來看 PDF 的工具本身也沒有 CJK 字型可用，畫面驗證不了 |
| **21** S3 鏡像／CloudWatch／ECS | Platinum 基礎設施擴充 | 🔴 未開始 | 沿用既有 IAM role、無金鑰模式 |

**與 §8 項目 11、12 的關係：** 那兩條是**既有** reasoning 層的 bug（Silver/Gold 範圍內的正確性
缺陷），修好它們是讓 S10 complete-Evidence run 真正達成的必要條件，**不算**新範圍，
也不在 Task 13-21 之列——建議優先於 14-21 處理，因為它們卡的是已經凍結、已經出貨的能力，
而 14-21 是全新的加分/延伸能力。

---

**這是 design-pipeline 的最後一份。** 無法 headless 驗證的階段（S0／S3／S11）
其人工檢查清單在本文 [§3.2](#32-只能由人驗證的部分人工檢查清單)。
接著要看的是 `docs/ACTIVE_WORK.md`（誰正在做什麼）與 `.kiro/specs/hoya-market-agent/tasks.md`（規範性任務，含 Task 13-21 完整規格）。

## 2026-08-02 S8/S9/S9B + live composition root implementation checkpoint

- S8: **Silver live Exit passed 2026-08-02** — `tests/live/test_live_silver_pipeline.py` →
  1 passed in 50.15s, schema-valid Bedrock structured output ＋ four artifacts. The live
  composition root is `src/hoya_agent/composition.py::build_live_pipeline()` (Binance ＋ Fear &
  Greed → `MappingArbiter` over凍結 Arbiter via `reasoning/mapping.py` + `reasoning/schemas.py`).
  `adapters/live_sources.py` bridges async fetchers into the deterministic pipeline's sync hooks.
  Arbiter output capped to 3000 tokens (45s call limit); claim `time_range` clamped to cutoff;
  empty claim `assets` default to run's assets; any mapping failure → deterministic fallback.
- S9: deterministic Trust Scorecard, canonical regime/unavailable, Evidence-backed invalidation
  and rendering implemented offline.
- S9B: single run/cutoff/ledger, aligned UTC comparison Evidence, balanced Arbiter projection,
  comparative Claim and dual-only section 12 implemented offline.
- UI: Streamlit Bronze (`ui/{presenter,streamlit_app}.py`) with live progress, trust funnel (G3),
  enforced `reporting/advice_lint.py`, self-bootstrap onto `sys.path`.
- Evidence: fact-grounding (G1, `evidence/grounding.py`) wired into pipeline/confidence;
  triangulation (G2, `evidence/triangulation.py`) exists but is **not wired into the run**.
- Parallel tool packages `src/calc/` and `src/skills/` tracked on `main`; not part of the agent
  pipeline.

**Real run results (2026-08-02, commit `6f914dc`, Python 3.12, this update):**
`python -m pytest tests/unit tests/contract tests/integration -q` → **1235 passed, 0 failed**
(75 warnings, 18.39s); `ruff check .` → **All checks passed!**.
Traps observed this pass: none new — prior traps (retired `claude-3-5-haiku-20241022`,
`us.` inference-profile prefix, markdown-fenced model output) remain documented in S0 above.
Note: `tests/unit/skills/` raises a NumPy `Timedelta` `DeprecationWarning` from
`src/skills/a9_verification.py:72` (non-fatal, in a parallel tool package, not the agent pipeline).

Verification evidence and remaining gates are recorded in [S8-S9-S9B implementation](S8-S9-S9B-implementation.md).
Remaining: S10 Gold local Exit and S11 deploy/timed rehearsal.

## 2026-08-02 five-year local market cache

Binance daily klines now have a paginated five-year prefetch path via
`scripts/prefetch_market_data.py`. The generated per-asset CSVs use the existing
validated OHLCV schema. `build_live_pipeline()` and `binance_bar_loader()` read
`HOYA_MARKET_CACHE_DIR` first, so the interactive path can reuse local history
and only fall back to the existing one-page live request when no cache is present.

## 2026-08-03 post-competition planning + two real bugs found closing Task 5

Branch `post-comp/finish-remaining-gates`, based on `origin/main@2c0d268` (the prior local
branch, `fix/task1b-contract-alignment`, was abandoned — its 3 commits targeted problems
`main` had already solved independently; its uncommitted WIP is preserved in `git stash`,
not lost, not applied here).

- Re-verified the whole "current state" picture against `origin/main` directly rather than
  trusting this file or `tasks.md`'s checkboxes, both of which had drifted (e.g. `tasks.md`
  Task 5 was still unchecked for two items that turned out to hide real bugs, not just missing
  tests; this file's S10 status still blamed a Bedrock account problem that had already been
  resolved, while the real blocker — reasoning-layer output instability — went unrecorded).
- Removed `p2-etl-mvp/` (Task 13; see §8 item 8).
- Closed `tasks.md` Task 5's last two open items. Both were meant to be "just write the missing
  test," and both instead surfaced a real defect:
  1. `OrganizerCsvPipeline.execute()` derived `effective_data_mode` from `run_mode` alone, so a
     fixture-backed instance used under `run_mode=official` would have self-reported `live` and
     silently defeated the official-mode fixture-rejection gate. Fixed to derive it from whether
     a live `load_bars` loader was actually injected.
  2. A missing `published_at` was invisible in reports (the evidence table only shows
     `fetched_at`). Added an explicit limitations-section disclosure.
  Both confirmed red before the fix, green after; full suite 1304 → 1306 passed, `ruff check .`
  clean throughout.
- Added `tasks.md` Tasks 13-21 for the post-competition continuation (§9 above indexes them)
  and amended `.kiro/steering/competition-rules.md` / `development-workflow.md` so the
  always-loaded steering context stops telling Kiro to reject H3/CoinGecko/S3/CloudWatch/ECS
  and post-freeze feature work — those rules applied only through the shipped Task 0-12 MVP.
- While re-reading `docs/rehearsals/run-log.md` in full (not just its opening runs) to write
  this update honestly, found the S10 blocker had changed shape: Bedrock access itself is fine
  now, but seven live runs recorded there show the Arbiter completing on time yet returning zero
  conclusion-layer claims six times out of seven, and a separate Planner asset-matching bug
  (`str(Asset.BTC) != 'BTC'` under Python 3.11+ enum semantics) that discards every LLM-generated
  plan on the script-driven live path specifically. Neither is fixed; both are frozen-`reasoning/`
  bugs requiring owner sign-off before anyone touches them. Recorded as §8 items 11-12 — these
  block S10's complete-Evidence run and should be prioritized over Tasks 14-21, since they are
  correctness bugs in already-shipped Silver/Gold capability, not new scope.
- Commits: `69c019f` (the bug fixes + p2-etl-mvp removal), `df4813e` (Task 13-21 + steering
  updates). Neither pushed to `origin` yet.
