# Claude Code 雲端排程（daily-dispatch routines）

本文件說明 daily-dispatch 的每日自動化排程。**2026-08 起，所有排程都改用
Claude Code 雲端排程（routines）**，取代先前的 Claude Cowork Scheduled Task。

## 為什麼改用雲端 routines

- **跑在 Anthropic 雲端環境**：每個 routine 觸發時，會在雲端自動 clone 本
  repository（透過 `session_context.sources` 設定），在雲端執行分析、寫檔，
  再以**原生 `git push`** 寫回 `main`。
- **不再需要 GitHub Personal Access Token**：push 認證由 claude.ai 綁定的
  GitHub 連線處理，不必把任何 token 貼進排程設定（舊版曾在 prompt 裡放 PAT，
  已全面移除）。
- **不再依賴裝置連線**：排程完全在雲端執行，凌晨或無人值守時段也能穩定
  push。舊版最主要的失敗原因，就是排程實際跑在「已連線裝置」上，裝置離線時
  commit 看似成功、實際完全沒有推送到 GitHub——雲端 routine 徹底解決了這點。

> **這份文件與 routine 的關係**：實際被執行的 prompt 存放在各 routine 的設定
> 裡（source of truth）。本文件是它們的對照說明；調整內容時，請同步更新對應
> routine 的 prompt（見文末「如何檢視與修改」）。

## 排程總覽

共六個 routine（時區換算：Asia/Taipei = UTC+8）：

| routine 名稱 | 時段（Asia/Taipei，節目表式記法） | 實際觸發時刻（Asia/Taipei） | cron（UTC） | 工作 |
| --- | --- | --- | --- | --- |
| 📰 每日新聞分析 1/5 | 05:00 | 當天 05:00 | `0 21 * * *` | 內容分析，寫入 reports |
| 📰 每日新聞分析 2/5 | 10:00 | 當天 10:00 | `0 2 * * *` | 內容分析 |
| 📰 每日新聞分析 3/5 | 15:00 | 當天 15:00 | `0 7 * * *` | 內容分析 |
| 📰 每日新聞分析 4/5 | 20:00 | 當天 20:00 | `0 12 * * *` | 內容分析 |
| 📰 每日新聞分析 5/5＋最終摘要 | 24:00 | **隔天 00:00** | `0 16 * * *` | 24:00 分析＋產生最終摘要＋標記 ready |
| 📮 每日發布觸發 | 07:07 | 隔天 07:07 | `7 23 * * *` | push `.github/publish-trigger` 觸發正式發布 |

> **關於「24:00」**：這是節目表式記法，代表「當天最後一次」。它的實際觸發時刻
> 是**隔天 00:00**（Asia/Taipei），但邏輯上仍屬於「前一個日曆日」的最後彙整
> ——05:00 / 10:00 / 15:00 / 20:00 這四次分析寫入的 `reports/YYYY-MM-DD.md`，
> 由 24:00（隔天 00:00 觸發）這次負責收尾。因此第五個 routine 的日期計算方式
> 跟前四個「不一樣」（見下方「24:00 排程」的日期換算說明）。

## 共用規則（六個 routine 都適用）

- 內容一律以四大類別為主軸（定義見
  [`config/categories.json`](../config/categories.json)）：
  1. 國際重大新聞（政治、外交、重大事件）
  2. 臺灣/兩岸相關新聞
  3. 科技與 AI 產業動態（新產品、重大技術發布、公司動向）
  4. 財經與市場（股市、匯率、重大經濟數據，若有明顯波動請標註）
- 一律使用 **Asia/Taipei** 日期與時間（可用 `TZ=Asia/Taipei date` 取得），
  不可直接使用執行環境的 UTC 日期。
- routine 在雲端已自動 clone 好 repository（cwd 即 repo 根目錄，`origin` 已設定
  好、具備 push 權限）；直接在工作目錄讀寫、commit、`git push origin main` 即可，
  **不需要、也不可以**再自己用帶 token 的 URL 重新 clone。不執行 `git remote -v`
  之類可能印出認證資訊的指令。
- 內容 routine 只更新 `reports/YYYY-MM-DD.md`，使用固定的
  `<!-- slot: HH:MM:start -->` / `<!-- slot: HH:MM:end -->` 標記；同一時段重跑時
  「取代」該時段內容，不可重複附加、不可刪改其他時段。
- 內容 routine **不可**呼叫 Telegram、不可觸發或執行 `publish-daily.yml`、不可
  讀寫任何 GitHub Secrets。
- 完成後 commit 並 `git push origin main`（push 被拒時先
  `git pull --rebase origin main` 再 push）。
- 全程使用台灣正體中文撰寫分析內容。
- **不要求五個時段全部齊全才能發布**：只要當天至少有一個時段收集到內容，
  24:00 排程就會產生最終摘要並標記 ready；缺一兩個時段仍會照常發布，只有
  「五個時段全部沒內容」才會維持 collecting、暫不發布。

## 內容分析時段（05:00 / 10:00 / 15:00 / 20:00）

四個內容 routine 的工作相同，差別只在：負責的時段、搜尋「自上一時段之後」的
新消息、以及寫入對應的 slot 區塊。寫入（或取代）
`<!-- slot: HH:MM:start -->` 到 `<!-- slot: HH:MM:end -->` 之間的內容，格式：

```
## HH:MM 分析

### 重要更新（依四大類別整理，定義見 config/categories.json）

依序寫出下面四個類別小節，四個標題都要保留；某類別本時段沒有值得報告的新消息
時，該小節底下寫「本時段本類別無重要更新。」，不可省略標題、也不可為填滿而加入
低品質新聞。

#### 1. 國際重大新聞（政治、外交、重大事件）
##### 事件標題
- 事件摘要：
- 最新進展：
- 重要性：
- 可能影響：
- 後續觀察：
- 來源：
  - [來源名稱](來源網址)
  - 若要同時附上文章標題，格式固定為 `[文章標題 - 來源名稱](網址)`；連結文字
    （方括號中間的文字）裡絕對不可以出現 `|` 符號——網站用 kramdown 的 GFM
    解析器，行內未跳脫的 `|` 會被誤判成表格分隔符，導致連結顯示錯誤
    （2026-07-26 已發生過實際案例）。一律用「-」分隔。

#### 2. 臺灣/兩岸相關新聞
（格式同上；若無則寫「本時段本類別無重要更新。」）

#### 3. 科技與 AI 產業動態（新產品、重大技術發布、公司動向）
（格式同上；若無則寫「本時段本類別無重要更新。」）

#### 4. 財經與市場（股市、匯率、重大經濟數據）
（格式同上；若股市、匯率或重大經濟數據出現明顯波動，請在事件標題前加註
「⚠️ 波動」並在「重要性」說明幅度與可能原因；若無則寫「本時段本類別無重要更新。」）

### 趨勢觀察
（本時段觀察到的跨類別共同趨勢）

### 低確定性消息
（尚未獲得足夠確認的內容，可跨類別彙整；若無則寫「無」）
```

規則：取代不附加、不動其他時段、保持 `<!-- status: collecting -->`（內容 routine
不可把狀態改成 ready）。若當日檔案不存在，先建立骨架：檔案開頭
`# YYYY-MM-DD 每日分析`、`<!-- status: collecting -->`、以及五個時段各自的
`<!-- slot: HH:MM:start -->` / `<!-- slot: HH:MM:end -->` 標記（可先留空）。

## 24:00 排程（第 5/5，含最終摘要）

這是當天最後一個分析排程，除了完成 24:00 分析，還要視情況產生當日最終公開摘要。

**日期換算（跟前四個不一樣）**：本 routine 實際觸發時刻是隔天 00:00。先取得
Asia/Taipei 實際日期，**目標日期 = 實際日期減一天**；後面所有 `YYYY-MM-DD` 都指
這個減一天後的目標日期。

流程：

1. 完成 24:00 時段分析（格式同上，寫入 `<!-- slot: 24:00:... -->` 區塊）。
2. 檢查涵蓋範圍：只要「至少一個時段」有內容，就繼續產生摘要並標記 ready；
   只有「五個時段全部無內容」才維持 collecting、在 reports 檔頂端加
   `<!-- missing_slots: 05:00,10:00,15:00,20:00,24:00 -->` 後結束。
3. 產生（或覆蓋）`site/_summaries/YYYY-MM-DD.md`（目標日期），格式：

```
---
title: "YYYY-MM-DD 每日新聞摘要"
date: YYYY-MM-DD 23:59:59 +0800
description: "當日重要新聞、產業趨勢與後續觀察"
layout: summary
published: true
---

## 本日笑話
（短篇故事型笑話，4～8 句：讀來像真實小故事、語氣自然、不刻意搞笑；前半建立
讀者直覺預期，最後一句出現合理但出乎意料的認知翻轉——建立在重新定義詞義/數字/
因果/立場/價值觀，不可用諧音、迷因、雙關；故事結尾再用一句把翻轉比喻自然連結到
今日新聞主軸；不涉真實在世個人、不冒犯特定族群。）

## 今日重點
（五到十點，最重要的事件，可註明類別。這個區塊會被完整送進 Telegram 通知。）

## 重要事件
（依四大類別整理，四個標題都要保留；某類別無事件寫「今日無重要事件。」。
每則事件：發生了什麼／為什麼重要／可能影響／後續觀察／來源。來源連結文字不可
含 `|`，一律用「-」。）

## 今日趨勢
## 可能影響
## 明日觀察
## 資訊聲明
本摘要由自動化分析流程產生，重要資訊請以原始來源為準。
```

4. 確認摘要產生且格式正確後，把 `reports/YYYY-MM-DD.md` 的
   `<!-- status: collecting -->` 改為 `<!-- status: ready -->`（即使缺一兩個時段
   也照改 ready，發布才不會被卡住）。
5. `git add` reports 與 summary、commit、`git push origin main`。**不**呼叫
   Telegram、**不**觸發 publish workflow、**不**接觸 Secrets——正式的 Telegram
   發送與 GitHub Pages 部署由 GitHub Actions 在隔天 07:07 處理。

> Telegram 版本會由 GitHub Actions 用 `scripts/extract_summary.py` 另外產生
> （擷取「本日笑話／今日重點／今日趨勢／明日觀察」），24:00 routine 不需要自己做。

## 發布觸發 routine（07:07）

正式發布（驗證摘要 + 部署 GitHub Pages + 發送 Telegram）由 GitHub Actions 的
[`publish-daily.yml`](../.github/workflows/publish-daily.yml) 執行，因為它需要
GitHub Secrets（Telegram token）。

**觸發它的排程已從 GitHub 原生 `schedule` cron 改成一個 Claude Code 雲端
routine**——因為 GitHub Actions 的 schedule cron 長期不穩定（延遲超過一小時、
甚至整次被跳過）。這個「📮 每日發布觸發」routine 每天 07:07（Asia/Taipei）在雲端
更新並 push `.github/publish-trigger`，藉由 workflow 的 `on.push`（只針對這個
檔案）觸發正式發布。它只負責「觸發」，不判斷內容、不碰 Telegram、不碰 Secrets；
是否重複發送交給 `publish-daily.yml` 自己的 `.state/published/YYYY-MM-DD` 機制與
`concurrency` 判斷。

`publish-daily.yml` 已移除 `schedule` cron，只保留 `workflow_dispatch`（手動補發）
與 `on.push`（發布 routine 觸發）。

## 如何檢視與修改

1. 到 <https://claude.ai/code/routines> 檢視、編輯、啟用/停用或手動執行每個
   routine；也可以用 Claude Code 的排程工具 / RemoteTrigger API 管理。
2. 每個 routine 的設定包含：
   - `environment_id`：Anthropic 雲端環境。
   - `session_context.sources`：指向本 repository（`https://github.com/g761007/daily-dispatch`），
     觸發時自動 clone。
   - `session_context.allowed_tools`：內容 routine 為
     `Bash / Read / Write / Edit / Glob / Grep / WebSearch / WebFetch`；發布觸發
     routine 只需 `Bash / Read / Write / Edit`。
   - `session_context.model`：目前為 `claude-haiku-4-5`（可視內容品質需求調整）。
   - `events[].message.content`：該時段的 prompt（即上述工作指示）。
3. 修改時段或分類時，請同步更新 `config/schedule.json`、`config/categories.json`
   與本文件（見 README「如何修改排程時段」「新聞分類」）。

> **注意**：routines 無法用 API 刪除，只能到 <https://claude.ai/code/routines>
> 手動刪除。若曾在舊版設定裡放過 GitHub Personal Access Token，建議到 GitHub
> 撤銷（revoke）該 token——雲端原生 push 已不再需要它。
