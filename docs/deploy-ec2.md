# EC2 部署指南 → 已併入 `deployment.md`

**這份文件已停用。** 部署的唯一權威文件是 **[`docs/deployment.md`](deployment.md)**。

兩份會各自漂移的部署文件比一份糟：2026-08-02 這份的「§7 目前狀態」還寫著
「新聞抽取（Planner + Research + RSS）尚未接（下一步）」，但 first-party RSS 與 Google News
已於 `34d2744` / `6444434` 接進 live pipeline，那句話已經是假的。與其修兩份，不如只留一份。

`deployment.md` 涵蓋原本這裡的全部內容，並補上這裡沒有的東西：

| 你原本在這裡找的 | 現在在 |
|---|---|
| IAM 最小權限 | [deployment.md §3](deployment.md#3-iam-instance-role) — 另加 SSM，取代開 SSH |
| ECR build / push | [§4](deployment.md#4-ecr) — 加上 immutable tag ＋ scan on push |
| EC2 執行（零金鑰） | [§5](deployment.md#5-ec2) |
| 驗證 | [§5 Verify](deployment.md#verify) — 加上**容器內** smoke test（UI 的 artifacts 寫在容器內的暫存目錄，host 端驗不到） |
| Rollback | [§5 Rollback](deployment.md#rollback) |
| 安全清單 | [Pre-submission checklist](deployment.md#pre-submission-checklist) |
| — | [Secret scan](deployment.md#2-secret-scan) 的可重現指令與實跑結果 |
| — | [Verified / not verified](deployment.md#verified--not-verified)：哪些真的驗過、哪些還沒 |

評審當天的操作腳本另見 [`docs/demo-runbook.md`](demo-runbook.md)。
