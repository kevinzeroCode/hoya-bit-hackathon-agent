# Demo runbook — the 15-minute judged flow

One page, followed literally. The competition allows **one run of at most 15 minutes**, and
in principle only one attempt. Everything below is about not needing a second one.

Deployment procedure: [deployment.md](deployment.md). Architecture: [architecture.md](architecture.md).

## Before the judges arrive

| # | Check | Command / action |
|---|---|---|
| 1 | The host is up and healthy | `curl -f http://35.91.36.186:8501/_stcore/health` → `ok` |
| 2 | The running tag is the intended tag | `docker inspect --format '{{.Config.Image}}' hoya-agent` → must end `:2cd9b43` |
| 2b | The demo IP is in the security group | 8501 is open to named sources only — add it to `sg-09d81b95b733a1a5a` beforehand |
| 3 | The image is already pulled | it is 860 MB — never pull during the judged window |
| 4 | Bedrock answers | `python scripts/diagnose_bedrock.py` → 3/3 |
| 5 | Browser tab open on the app, zoom set, no `.env` or terminal with secrets visible on screen | |
| 6 | The recorded fallback run is reachable | see [Fallback](#fallback-when-the-live-path-fails) |
| 7 | A timer is running and visible to you | wall clock, not a guess |

## The run

The clock starts when the run starts, not when the question is read.

1. **Enter the question and the asset.** 幣種 accepts 1–2 of BTC / ETH / SOL / BNB / XRP.
   Picking two switches on the cross-asset comparison and adds report section 12 — only do
   that if the question is genuinely comparative.
2. **Pick the mode.** Three choices, visually distinct on screen:

   | Selector | Badge | What it does |
   |---|---|---|
   | 即時 official(Binance + 情緒) | 🔴 official | live data, cutoff frozen at run start, no fixtures |
   | 離線 rehearsal(官方 CSV) | 🟡 rehearsal | organizer CSV only, replayable cutoff |
   | 離線 demo(官方 CSV) | ⚪ demo | recorded/offline path, labelled as such in UI *and* report |

   **For the judged run: 即時 official.** `demo` must never be presented as a live analysis.
3. **Press 執行分析 once.** The button disables itself while the run is in flight; a second
   press is ignored rather than starting a second run.
4. **Narrate the progress panel while it streams.** Those are real `ExecutionEvent`s from the
   pipeline, not a timed animation — stages appear only when they actually fire. This is the
   most convincing 60 seconds of the demo; do not talk over it.
5. **Walk the three tabs** once the run completes:
   - 📄 報告 — 11 fixed sections. Point at §3 已確認事實 and §9 限制與資料缺口: every number
     carries an Evidence ID, and the gaps are stated rather than smoothed over.
   - 🧾 Evidence Ledger — `evidence.json`. Show that `reliability` and `independence_group`
     were assigned by the processor, not claimed by the source.
   - 🪵 Execution Log — `execution_log.jsonl`. Show a degraded stage if there is one.
6. **Download all four artifacts** and open at least one. The four filenames are fixed and
   the four files share one `run_id`.

**Minute 12** cancels every non-essential external call. **Minute 13** is the hard artifact
deadline. If the wall clock passes 13 minutes with fewer than four files on screen, that is a
failure to report, not to explain away.

## What to say when something degrades

Degradation is the designed behaviour, and saying so plainly is stronger than apologising.

| On screen | Say |
|---|---|
| A source shows `SourceUnavailable` | 「這個來源這次沒回來，報告第 9 段把它列成資料缺口，結論不會靠它。」 |
| Bedrock unavailable | 「推理層這次不可用，所以報告只留 deterministic 市場證據，沒有推論與結論——我們不會用模型補一個看起來像結論的東西。」 |
| `insufficient_data` / 目前無法可靠判定 | 「證據不足以支撐結論，系統就說不知道。這是刻意的：寧可誠實降級，不做預測。」 |
| Only one independence group | 「只有一個獨立上游，信心上限就被規則壓低了——這個上限是決定論的，不是模型自評。」 |

Never say a fallback provider was used. There is no second live market provider in the MVP;
a failed baseline source degrades and discloses.

## Fallback: when the live path fails

A complete recorded run is kept **outside source control** so it can be shown if the network,
the provider or Bedrock is unusable at demo time:

```
C:\Users\USER\Documents\AWS\hoya-demo-fallback\run_20260802_015425_demo1\
    run_config.json  execution_log.jsonl  evidence.json  final_report.md
```

Saved 2026-08-02. `run_mode: demo`, `analysis_as_of: 2026-05-31T00:00:00Z`, terminal state
`degraded`, 5 evidence items. The report header table says it in words:
"執行模式 | demo（可能包含 recorded fallback，非現場新分析）"。

Switch the UI mode to **離線 demo(官方 CSV)** to show the offline path live, or open the saved
artifacts directly. In either case `demo` is disclosed in three places: the ⚪ demo badge in the
UI, `run_mode: "demo"` in `run_config.json`, and the run-mode line in the report, along with the
original acquisition time. **Presenting a recorded run as a fresh live analysis is prohibited**
by the competition rules and by our own honesty contract.

## Questions the judges are likely to ask

| Question | Answer |
|---|---|
| 「數字是模型算的嗎？」 | 不是。市場數值只由 Python 從具名來源算出，每個都有 Evidence ID。模型只能挑選與連結證據，不能產生數字。 |
| 「怎麼證明沒有預寫答案？」 | official 模式在 run 開始時凍結 `analysis_as_of`，禁止 fixture，`run_config.json` 記下模式與時間戳。 |
| 「來源可信度誰決定？」 | `evidence/policies.py` 的靜態規則，由 Evidence Processor 單點指派。來源不能自稱可信。 |
| 「信心分數是模型自評嗎？」 | 模型提出，然後決定論規則**只能往下壓**：獨立上游少於 2 組就不能是 strong，出現實質衝突就降級。 |
| 「多代理人辯論呢？」 | H3 未實作。介面在、預設關閉，UI 與報告都標示未實作——我們不展示做不到的東西。 |
| 「跑失敗會怎樣？」 | 四個 artifact 一定產出，就算全部外部服務掛掉、就算 run 被取消。寫檔是 tmp → fsync → `os.replace`，不會有半寫檔。 |

## After the run

- Record run ID, mode, duration, source gaps and artifact paths in
  [`docs/rehearsals/run-log.md`](rehearsals/run-log.md).
- Note anything that surprised you, even if it did not break.
- Stop or terminate the EC2 instance if no further demo is scheduled.
