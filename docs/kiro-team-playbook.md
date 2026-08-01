# HOYA Market Agent Kiro Team Playbook

> Status: ready to use; implementation tasks have not started  
> Scope: four people, two days, one shared Kiro spec  
> Source of truth: [Kiro tasks](../.kiro/specs/hoya-market-agent/tasks.md) and [team workflow](superpowers/specs/2026-07-17-four-person-team-workflow-design.md)

## 1. Team Operating Model

每個人使用自己的 clone、自己的 task branch、同一份 `.kiro/specs/hoya-market-agent/`。不要建立四份 spec，也不要讓 Kiro 自動跑完所有 tasks。P1 是整合與契約 owner；P4 的工作刻意放在穩定介面後，且 AWS 由 P1 陪同，不讓較弱成員成為單點失敗。

### Start order

| Time | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| 現在 | Task 1 shared contracts | 唯讀 review data contracts | 唯讀 review reasoning contracts | Task 0 service preflight |
| Task 1 merged | 與 P3 結對 Task 2 | 繼續準備 fixtures | 在 P1 branch 結對 Task 2 | 檢查 UI-facing result shape |
| Task 2 merged | Task 3 pipeline | Task 4 market data | Task 6 Bedrock/reasoning | Task 7 Streamlit shell |
| Task 4 merged | 持續 Task 3／review | Task 5 research/evidence | 持續 Task 6 | 持續 Task 7 |
| Tasks 3-7 green | Task 8 integration | 修復 owned module | 修復 owned module | UI exercise |
| Day 2 | Task 9 gate；與 P4 Task 10 | 五幣與資料 failure drills | Arbiter/schema failure drills | 與 P1 部署、runbook、demo |

## 2. One-Time Setup for Every Member

首次在自己的電腦執行：

```powershell
git clone https://github.com/kevinzeroCode/hoya-bit-hackathon-agent.git
Set-Location hoya-bit-hackathon-agent
git switch main
git pull --ff-only
git status
```

必須從 repository root 開啟 Kiro，不能只開 `.kiro` 目錄。

### Kiro IDE

```powershell
kiro .
```

團隊建議統一使用 IDE。若已安裝 Kiro Command Router 且 `kiro` 被設為啟動 CLI，請執行 `kiro ide`，再用 `File > Open Folder` 選 repository root。

1. 開啟左側 Kiro panel。
2. 在 Specs 區找到既有的 `hoya-market-agent`。
3. 先讀 `requirements.md`、`design.md`、`tasks.md`。
4. 在 task 清單只點自己被分配的單一 task。
5. 不點 `Run all Tasks`，也不建立新 spec。

### Kiro CLI v3 Early Access（optional）

```text
PS repository-root> kiro-cli --v3
> /spec hoya-market-agent
```

Spec CLI 目前屬於 v3 Early Access，必須以 `--v3` opt in。`/spec hoya-market-agent` 是接續既有 spec；不要使用 `/spec new hoya-market-agent`，也不要使用會自動跑全部 tasks 的 `/spec run hoya-market-agent`。若任何人的 v3 行為不一致，直接改用 IDE，不在兩天內排查 CLI preview。

## 3. Rules Kiro Must Follow

- 一個 branch 只做一個編號 task；branch 格式為 `task/<number>-<short-name>`。
- 先讀 `.kiro/steering/`、三份 spec artifacts 與本手冊，再開始修改。
- 嚴格 Red -> Green -> Refactor；先寫 task 指定的 failing test。
- 不提前實作其他 task，不碰其他 owner 的檔案。
- 不以 live network 取代 fixture/contract tests。
- 不把 credential、token、header、完整 provider response 寫入 repo 或 Kiro 對話摘要。
- Kiro 完成修改後先停下，人工看 `git diff`；不要讓它自行 commit/push。
- Shared contracts 只由 P1 合併。任何 contract 變更先列出受影響 owner，不自行擴充 schema。

所有人先貼這段共用提示詞，再接角色提示詞：

```text
請使用既有 `.kiro/specs/hoya-market-agent/`，不要建立新 spec，
不要執行 Run all Tasks。先讀 requirements.md、design.md、tasks.md、
`.kiro/steering/` 與 `docs/kiro-team-playbook.md`。

只執行 Task <N>，不得提前實作其他 Task，也不得修改其他 Owner 的檔案。
先列出依賴、預計修改檔案與精確測試，再依 Red -> Green -> Refactor 執行。
不得用 live 網路取代 fixture test，不得寫入或顯示 secrets。
測試通過後只勾選 Task <N> 已實際完成的 checkbox。
先不要 commit 或 push，停下來讓我檢查 diff。
```

## 4. P1: Integration and Release

### Start now: Task 1

```powershell
git switch main
git pull --ff-only
git switch -c task/1-shared-contracts
kiro .
```

在 Kiro 選 `hoya-market-agent` 的 Task 1，貼上共用提示詞並補充：

```text
你是 P1 Integration/Release。只執行 Task 1，凍結 models.py、config.py、
clock.py、ports.py 與 tests/fakes.py。Schema 必須逐欄符合
evidence-contracts.md；不要開始 ApplicationService 或 pipeline。
任何契約歧義先停止並指出，不要自行新增欄位。
最後執行 Task 1 指定 pytest 與 ruff。
```

Task 1 合併後，P1 建立 `task/2-fixture-vertical-slice`，與 P3 採 driver/navigator 結對，不讓兩台電腦同時改同一 branch。Task 2 merged 後，P1 開 `task/3-deadline-pipeline`；Tasks 3-7 全綠後再開 Task 8。

P1 同時負責：merge gate、保留其他 task checkbox、統一更新 Kiro evidence ledger、Task 9 acceptance gate，以及陪同 P4 完成 Task 10 AWS 部署。

## 5. P2: Data and Evidence

### Start now: read-only review

P2 現在留在 `main`，Kiro 只做唯讀分析，不建立 branch、不修改檔案：

```text
只做唯讀 review，不修改檔案。檢查現有 Task 1 contracts 是否足以支援
Task 4、5，列出 MarketSource、ResearchSource、EvidenceItem 所需介面、
fixtures 與可能的 ownership 衝突。不要產生實作。
```

Task 2 merged 後開始 Task 4：

```powershell
git switch main
git pull --ff-only
git switch -c task/4-market-data
kiro .
```

```text
你是 P2 Data/Evidence。只執行 Task 4。Market Worker 必須完全 deterministic，
不得匯入 LLMClient。先寫 golden indicator、UTC cutoff、adapter contract 與
跨幣 base-volume rejection tests，再做最小實作。最後執行 Task 4 指定測試。
```

Task 4 合併後，從最新 `main` 另開 `task/5-research-evidence`。Task 5 不和 Task 4 共用 branch；research adapter failures 必須轉為 typed gaps，Evidence Processor 不得使用 LLM 動態評可信度。

## 6. P3: Reasoning and Report

### Start now: read-only review

```text
只做唯讀 review，不修改檔案。針對 Task 2 與 Task 6 檢查 AnalysisResult、
Claim graph、Bedrock structured output、prompt version 與 deterministic
fallback 契約，列出需要 P1 凍結的介面。不要產生實作。
```

Task 1 merged 後，P3 與 P1 在 `task/2-fixture-vertical-slice` 結對；P3 專注 fixture `AnalysisResult`、11 個報告段落（雙幣另加「跨幣比較」段落）、Evidence 回溯與 renderer review，branch 仍由 P1 操作。

Task 2 merged 後開始 Task 6：

```powershell
git switch main
git pull --ff-only
git switch -c task/6-bedrock-reasoning
kiro .
```

```text
你是 P3 Reasoning/Report。只執行 Task 6。所有 LLM 行為必須 bounded，
最多一次 schema repair，且共用 stage deadline；不得抓 provider data、
寫 artifact 或實作 H3 debate。先用 fake LLM 或 Stubber 完成 contract tests。
```

P3 不計算市場數值、不直接抓資料、不落 artifacts；它只接收 validated Evidence IDs，輸出 validated `AnalysisResult`。

## 7. P4: UI and Demo Support

### Start now: Task 0

```powershell
git switch main
git pull --ff-only
git switch -c task/0-service-preflight
kiro .
```

```text
你是 P4 UI/Demo Support。只執行 Task 0。所有服務結果必須來自實際執行，
不得推測或補寫成功；只記 timestamp、region、model ID、endpoint 與 pass/fail。
.env.example 只能放變數名稱，絕不顯示 token、credentials、headers 或完整回應。
若服務無法使用，誠實記錄 failure 與 fixture/fallback，不得宣稱通過。
AWS 與 Bedrock 操作請 P1 陪同確認。
```

Task 2 merged 後，從最新 `main` 開 `task/7-streamlit-shell`：

```text
你是 P4。只執行 Task 7，僅透過 ApplicationService 與 presenter 工作。
先以 fixture vertical slice/fakes 建立 presenter tests；UI 不得匯入 concrete
adapter 或 pipeline stage。Docker 變更交給 P1 review。
最後執行指定 pytest 與 docker compose config。
```

P4 在 Day 2 操作 UI、下載四項 artifacts、維護 rehearsal/runbook；P1 co-own ECR/EC2 與 rollback，P4 不獨自處理 production credentials 或核心部署決策。

## 8. Finish One Task Safely

1. 執行該 task 列出的 focused tests 與 `ruff check .`。
2. 用 `git diff --check`、`git diff`、`git status --short` 檢查範圍、secret、artifact 與 checkbox。
3. 只 stage 明確路徑，禁止 `git add .`。
4. 使用 `tasks.md` 指定的 commit message。
5. Push task branch，開 PR；P1 檢查介面、測試與其他 checkbox 沒被覆蓋。
6. Owner 把 task、branch、測試命令與結果、commit SHA、Kiro session 摘要交給 P1。
7. P1 在 merge/checkpoint 後集中更新 `docs/evidence/kiro/README.md`，避免四人同時改 evidence ledger。

範例收尾命令；`<paths>` 必須換成這個 task 的明確檔案：

```powershell
python -m pytest <task-focused-tests> -q
ruff check .
git diff --check
git status --short
git add <paths>
git commit -m "<tasks.md specified message>"
git push -u origin task/<number>-<short-name>
```

## 9. Checkpoint Handoffs

| Gate | Required handoff |
|---|---|
| Task 1 | P1 發布 frozen Pydantic models、ports、fake clock/adapters/progress sink |
| Task 2 | 一個 BTC rehearsal request 可產生四個正確命名 artifacts |
| Tasks 3-7 | 每位 owner 提供 focused test command/result 與 PR SHA |
| Task 8 | 完整 H2-Lite fixture run；partial/fallback 行為可見 |
| Task 9 | 五幣、雙幣比較 run、failure injection、deadline gates 全過 |
| Task 10 | EC2 可達、四個 downloads、recorded fallback 誠實標示、三次 timed rehearsal |

卡住 20 分鐘就找 interface owner 結對，不要私自繞過契約。可刪工作依序為 H3、optional AWS sinks、optional adapters、UI polish；deterministic fallback 與四項 artifacts 不得刪。

## 10. Kiro References

- [Kiro IDE: open a project and execute individual spec tasks](https://kiro.dev/docs/getting-started/first-project/)
- [Kiro CLI v3 Early Access: opt in with `kiro-cli --v3`](https://kiro.dev/docs/cli/v3/)
- [Kiro CLI v3: resume an existing spec with `/spec <name>`](https://kiro.dev/docs/cli/v3/specs/)
