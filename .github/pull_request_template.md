<!--
四個人平行開發，這份清單只擋一件事：讓別人相信一份已經過時的狀態表。
純文件 PR 可以跳過第 1、2 項。
-->

## 這個 PR 做了什麼

<!-- 一到三句。做了什麼、為什麼。 -->

## 開 PR 前的必要檢查

- [ ] **已更新 `docs/Implementation-Plan.md`** — §1.1 現況快照那一列 **與** 我這個階段的「現況」區塊
- [ ] 現況區塊寫的是**真的跑過的事實**（實際測試數字、`ruff` 結果、踩過的坑），不是計畫
- [ ] 已更新 `.kiro/specs/hoya-market-agent/tasks.md` 的對應 checkbox
- [ ] 沒有動到 `.kiro/steering/work-in-progress.md` 列出的凍結路徑（若有，已取得 owner 同意）
- [ ] 沒有 `.env`、API key、AWS 憑證、CryptoPanic token 進到 diff、log 或截圖

## 驗證結果（貼實際輸出，不要寫「應該會過」）

```
python -m pytest tests -q
→

ruff check .
→
```

## 踩過的坑

<!--
這一欄價值最高，別留空。
S0 的三個 Bedrock 陷阱（舊 Haiku 下架、us. inference profile 前綴、markdown 圍欄導致抽取 0 筆）
就是靠這樣留下來的，省了後面每個人各撞一次。
沒踩到坑就寫「無」。
-->

## 這個 PR 之後，誰被解鎖了 / 誰被擋住了

<!-- 例：S3 現在可以開工了 / `_provisional_seams.py` 還沒刪，S2 swap 仍待處理 -->
