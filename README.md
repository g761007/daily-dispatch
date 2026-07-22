# daily-dispatch

daily-dispatch 是一個「每日新聞分析與摘要」自動化系統：每天由 Claude Cowork
在五個固定時段搜尋、分析新聞並累積寫入當日檔案，最後一個時段結束後整理成一份
最終每日摘要，透過 **GitHub Pages** 公開發布，並在每天固定時間以 **GitHub
Actions** 驗證、經由 **Telegram Bot** 發送一次通知。

> ⚠️ 本 repository 預設為 **Public**。請務必先閱讀下方
> [安全注意事項](#安全注意事項) 與
> [Public Repository 會公開哪些內容](#public-repository-會公開哪些內容)。

---

## 目錄

- [系統架構圖](#系統架構圖)
- [資料流程](#資料流程)
- [目錄結構](#目錄結構)
- [快速啟用步驟](#快速啟用步驟)
- [啟用 GitHub Pages](#啟用-github-pages)
- [建立 Telegram Bot](#建立-telegram-bot)
- [如何取得 Chat ID](#如何取得-chat-id)
- [設定 GitHub Secrets](#設定-github-secrets)
- [設定 Claude Cowork 五個排程](#設定-claude-cowork-五個排程)
- [如何修改排程時段](#如何修改排程時段)
- [如何手動補發指定日期](#如何手動補發指定日期)
- [如何避免重複發送](#如何避免重複發送)
- [本機測試 Jekyll](#本機測試-jekyll)
- [本機測試-python-scripts](#本機測試-python-scripts)
- [安全注意事項](#安全注意事項)
- [Public Repository 會公開哪些內容](#public-repository-會公開哪些內容)
- [不應放入報告的私人或公司內部資訊](#不應放入報告的私人或公司內部資訊)
- [常見問題排除](#常見問題排除)

---

## 系統架構圖

```
Claude Cowork 每日排程（Asia/Taipei）
        │
        ├─ 排程一 03:00：分析並更新當日累積檔案
        ├─ 排程二 07:00：分析並更新當日累積檔案
        ├─ 排程三 12:00：分析並更新當日累積檔案
        ├─ 排程四 17:00：分析並更新當日累積檔案
        └─ 排程五 22:00：
             ├─ 完成第五次分析
             ├─ 讀取當日全部分析
             ├─ 確認五個時段都齊全
             ├─ 產生最終每日摘要（site/_summaries/YYYY-MM-DD.md）
             └─ 將 reports 狀態改為 ready
                        │
              git push 到 main 分支
                        │
                        ▼
        GitHub Actions：Deploy GitHub Pages
        （site/** 有變更時自動觸發）
                        │
                        ▼
              GitHub Pages 網站更新
                        │
        （隔天 08:00 Asia/Taipei，此時 Pages 已部署完成超過 30 分鐘）
                        ▼
        GitHub Actions：Publish Daily Summary
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
      驗證前一日摘要已 ready   （驗證失敗則整個 workflow 失敗，不發送）
             │
             ▼
      傳送 Telegram（僅發送最終摘要，不含五時段原文）
             │
             ▼
      建立 .state/published/YYYY-MM-DD 並 commit + push
      （避免同一天重複發送）
```

## 資料流程

1. **內容產製**：Claude Cowork 在五個時段負責「內容分析」，直接寫入
   `reports/YYYY-MM-DD.md` 並 push 到 GitHub。這一步**不會**用到任何 Secrets，
   也**不會**呼叫 Telegram 或觸發正式發布 workflow。
2. **最終整理**：第五個排程（22:00）額外負責讀取當天全部五個時段內容，重新
   整理（不是直接拼接）成 `site/_summaries/YYYY-MM-DD.md`，並把
   `reports/YYYY-MM-DD.md` 的狀態改成 `ready`。
3. **網站部署**：`site/**` 有變更時，`deploy-pages.yml` 會自動建置 Jekyll 網站
   並部署到 GitHub Pages。這個 workflow **完全不會**接觸 Telegram Secrets。
4. **正式發布**：`publish-daily.yml` 每天固定在 Asia/Taipei 08:00（對應「前一天」
   的摘要）執行，依序：驗證摘要完整 → 產生 Telegram 版本 → 傳送 Telegram →
   確認成功 → 建立已發布狀態檔 → commit + push。任何一步失敗，整個 workflow
   都會失敗，且**不會**建立已發布狀態、**不會**視為已發送。

## 目錄結構

```
daily-dispatch/
├── README.md                     本文件
├── LICENSE                       MIT License
├── .gitignore
│
├── config/
│   └── schedule.json              排程時段設定（僅供參考／文件用途）
│
├── reports/
│   └── YYYY-MM-DD.md              每日累積分析（五個時段寫入同一份）
│
├── site/                          Jekyll 網站原始碼（GitHub Pages 來源）
│   ├── _config.yml
│   ├── Gemfile                    本機測試用（pin jekyll 版本）
│   ├── index.html                 首頁
│   ├── archive.html               歷史摘要頁（含前端搜尋）
│   ├── about.md                   關於頁
│   ├── _layouts/
│   │   ├── default.html
│   │   └── summary.html
│   ├── _includes/
│   │   ├── header.html
│   │   └── footer.html
│   ├── _summaries/
│   │   └── YYYY-MM-DD.md          最終每日摘要（Jekyll collection）
│   └── assets/
│       ├── style.css
│       └── site.js
│
├── scripts/                       發布流程用的 Python 腳本
│   ├── _common.py                 共用工具（時區、路徑、slot 解析）
│   ├── requirements.txt
│   ├── validate_report.py
│   ├── extract_summary.py
│   ├── send_telegram.py
│   └── mark_published.py
│
├── docs/
│   └── cowork-schedules.md        五份可直接使用的 Claude Cowork 排程提示詞
│
├── .state/
│   └── published/                 已發布狀態檔（避免重複發送）
│
└── .github/
    └── workflows/
        ├── publish-daily.yml      每日正式發布（驗證 + Telegram + 標記已發布）
        └── deploy-pages.yml       GitHub Pages 部署
```

## 快速啟用步驟

1. 在 GitHub 建立一個新的 **Public** repository，名稱建議為 `daily-dispatch`。
2. 把這個專案 push 上去（見下方「[初始化並推送到 GitHub](#初始化並推送到-github)」，
   或直接參考終端機輸出的指令）。
3. 到 repository 的 **Settings → Pages**，Source 選擇 **GitHub Actions**
   （詳見 [啟用 GitHub Pages](#啟用-github-pages)）。
4. 建立 Telegram Bot 並取得 Token 與 Chat ID（見下方兩節）。
5. 到 **Settings → Secrets and variables → Actions**，新增
   `TELEGRAM_BOT_TOKEN` 與 `TELEGRAM_CHAT_ID` 兩個 Secrets。
6. 依照 [設定 Claude Cowork 五個排程](#設定-claude-cowork-五個排程) 建立五個
   排程任務。
7. 等待第一個完整的一天跑完（或手動先跑一次），確認：
   - `reports/YYYY-MM-DD.md` 五個時段都有內容、狀態變成 `ready`。
   - `site/_summaries/YYYY-MM-DD.md` 已產生。
   - GitHub Pages 網站已顯示該篇摘要。
   - 隔天 08:00（Asia/Taipei）`Publish Daily Summary` workflow 成功執行，
     Telegram 收到通知。

## 啟用 GitHub Pages

1. 到 repository 的 **Settings → Pages**。
2. **Build and deployment → Source** 選擇 **GitHub Actions**（不要選
   「Deploy from a branch」）。
3. 第一次需要有一次 `site/**` 的變更（例如本專案內建的示範摘要
   `site/_summaries/2026-07-21.md`）觸發 `deploy-pages.yml`，或直接到
   **Actions → Deploy GitHub Pages → Run workflow** 手動觸發一次。
4. 部署完成後，網站網址會是：
   `https://<你的 GitHub 使用者名稱>.github.io/daily-dispatch/`
   （注意結尾有 repository 名稱路徑，因為這是 Project Pages，不是
   `<username>.github.io` 這種 User/Org Pages）。
5. 若你的 GitHub 使用者名稱不是 `g761007`，或 repository 名稱不是
   `daily-dispatch`，請同步修改：
   - `site/_config.yml` 的 `url`、`baseurl`、`github_username`、`repository`。
   - `.github/workflows/publish-daily.yml` 中的 `base-url` 參數已經是用
     `${{ github.repository_owner }}` / `${{ github.event.repository.name }}`
     動態帶入，通常不需要改。

## 建立 Telegram Bot

1. 在 Telegram 搜尋並開啟官方帳號 **[@BotFather](https://t.me/BotFather)**。
2. 傳送 `/newbot`，依照指示輸入 Bot 名稱與使用者名稱（必須以 `bot` 結尾）。
3. BotFather 會回傳一組 **Bot Token**，格式類似
   `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`。
   **這組 Token 請直接貼到 GitHub Secrets，不要貼到任何程式碼、commit 或聊天記錄以外的地方。**
4. 若日後懷疑 Token 外洩，回到 @BotFather 用 `/revoke` 或 `/token` 重新產生。

## 如何取得 Chat ID

依你想接收通知的對象選擇一種方式：

**方式一：發送給你自己（個人聊天）**

1. 在 Telegram 找到你剛建立的 Bot，點擊 **Start**（或傳送任意訊息）。
2. 瀏覽器打開：
   `https://api.telegram.org/bot<你的BotToken>/getUpdates`
   （這一步只在你自己的瀏覽器操作，不要把這個網址貼到公開地方，因為它包含 Token）
3. 在回傳的 JSON 中找 `"chat":{"id": 123456789, ...}`，這組數字就是 Chat ID。

**方式二：發送到群組**

1. 把 Bot 加入群組，並在群組內傳送一則訊息。
2. 同樣打開 `getUpdates` 網址，找到該群組的 `"chat":{"id": -1001234567890, ...}`
   （群組 ID 通常是負數）。

**方式三：發送到頻道**

1. 把 Bot 設為頻道管理員。
2. 頻道的 Chat ID 通常是 `@你的頻道使用者名稱`，或同樣可用 `getUpdates` 取得
   數字 ID。

## 設定 GitHub Secrets

到 repository 的 **Settings → Secrets and variables → Actions → New repository
secret**，新增兩個 Secrets：

| Name | Value |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | 從 BotFather 取得的 Bot Token |
| `TELEGRAM_CHAT_ID` | 上一節取得的 Chat ID |

這兩個值**只能**存在這裡。專案中的程式碼只會用
`${{ secrets.TELEGRAM_BOT_TOKEN }}` / `${{ secrets.TELEGRAM_CHAT_ID }}` 這種
方式引用，不會出現在任何檔案、commit 或 workflow log 中。

## 設定 Claude Cowork 五個排程

1. 打開 `docs/cowork-schedules.md`，裡面有五份完整、可直接複製的排程提示詞
   （對應 03:00 / 07:00 / 12:00 / 17:00 / 22:00，Asia/Taipei）。
2. 在 Claude 建立 5 個 Scheduled Task，各自貼上對應的提示詞，並依文件內建議的
   cron（UTC 時間）設定排程頻率為「每天一次」。
3. 五個排程只負責「內容分析、寫入 reports、產生最終摘要」，**不會**接觸
   Telegram 或任何 Secrets——這些交給 GitHub Actions 處理，職責分離、降低
   Secrets 外洩風險。

## 如何修改排程時段

1. `config/schedule.json` 是排程時段的「文件用途」設定檔，修改
   `analysis_slots` / `final_slot` 只是更新文件紀錄，**不會**自動改變實際排程
   時間（Claude Cowork 排程與 GitHub Actions cron 都需要手動同步修改）。
2. 若要改變五個分析時段：
   - 修改 `config/schedule.json` 的 `analysis_slots` 與 `final_slot`。
   - 到 `docs/cowork-schedules.md`，把五份提示詞中的時段文字、slot 標記
     （`<!-- slot: HH:MM:start -->` 等）與 cron 對照表都同步更新。
   - 到 Claude 的 Scheduled Task 設定頁，更新對應排程的執行時間。
3. 若要改變正式發布時間（目前預設 Asia/Taipei 08:00，對應最後分析時段
   22:00 之後 10 小時）：
   - 修改 `.github/workflows/publish-daily.yml` 的 `schedule.cron`
     （記得 cron 是 UTC 時間，Asia/Taipei = UTC+8）。
   - 更新 `config/schedule.json` 的 `publish_time` 與 `publish_time_note`。
   - 請保留「最後分析時段」到「正式發布」之間至少 30 分鐘的間隔，讓
     GitHub Pages 有時間完成部署（見 `publish-daily.yml` 內的註解）。

## 如何手動補發指定日期

如果某天忘記執行、或想重新驗證某一天：

1. 到 **Actions → Publish Daily Summary → Run workflow**。
2. `date` 欄位填入要補發的日期（`YYYY-MM-DD`，Asia/Taipei），留空則預設為
   「前一天」。
3. 執行前請確認該日期的 `reports/YYYY-MM-DD.md` 狀態已經是 `ready`，且
   `site/_summaries/YYYY-MM-DD.md` 已存在——否則 `validate_report.py` 會讓
   workflow 失敗（這是刻意設計，避免發送不完整的內容）。
4. 若該日期已經發布過（`.state/published/YYYY-MM-DD` 已存在），workflow 會
   直接顯示「已發布過，略過」並正常結束，**不會**重複發送 Telegram。

## 如何避免重複發送

- 每次成功傳送 Telegram 後，`mark_published.py` 會建立
  `.state/published/YYYY-MM-DD` 並 commit + push。
- `publish-daily.yml` 在傳送 Telegram「之前」一定會先檢查這個檔案是否存在；
  存在就直接跳過，不再呼叫 Telegram API。
- 只有 Telegram **成功**送出後，才會建立這個狀態檔；若傳送失敗，workflow
  會直接失敗，不建立狀態檔，下次重跑仍會正常嘗試發送。

## 本機測試 Jekyll

需要 Ruby 與 Bundler（本專案已提供 `site/Gemfile`）：

```bash
cd site
bundle install
bundle exec jekyll build   # 建置到 site/_site
bundle exec jekyll serve   # 本機預覽，預設 http://127.0.0.1:4000/daily-dispatch/
```

若只是想快速檢查 HTML/Liquid 語法錯誤，也可以只執行 `bundle exec jekyll build`
並檢查是否有錯誤訊息與 `_site/daily/2026-07-21/index.html` 是否正確產生。

## 本機測試 Python Scripts

需要 Python 3.11+：

```bash
cd scripts
pip install -r requirements.txt --break-system-packages   # 視環境調整

# 驗證某一天的報告與摘要是否完整（本專案內建 2026-07-21 示範資料）
python validate_report.py --date 2026-07-21

# 產生 Telegram 版本（不會真的發送，只會寫入本機暫存檔）
python extract_summary.py --date 2026-07-21 \
  --base-url "https://g761007.github.io/daily-dispatch" \
  --output-dir /tmp/daily-dispatch-test

cat /tmp/daily-dispatch-test/telegram-message-1.txt

# 標記已發布（本機測試用，會建立 .state/published/2026-07-21）
python mark_published.py --date 2026-07-21 --run-id local-test

# 實際發送 Telegram（需要先在本機環境變數設定 Token / Chat ID，測試完務必清除）
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python send_telegram.py --manifest /tmp/daily-dispatch-test/manifest.json
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
```

> 測試完 `mark_published.py` 後，記得刪除 `.state/published/2026-07-21`
> （若不想讓示範日期被標記為已發布並被 commit 上去）。

## 安全注意事項

- `TELEGRAM_BOT_TOKEN` 與 `TELEGRAM_CHAT_ID` **只能**存放在 GitHub Secrets，
  不會出現在任何 repository 檔案、commit 訊息、workflow YAML 明碼、
  Actions log 或網頁內容中。
- workflow 中一律使用 `env: TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}`
  的方式引用，且**不會**執行 `echo "$TELEGRAM_BOT_TOKEN"`、`set -x`、
  `curl -v` 等可能洩漏 Secrets 的指令。
- `scripts/send_telegram.py` 刻意不輸出完整 Telegram API URL（因為 URL 本身
  包含 Token），錯誤訊息也會用正規表示式遮蔽任何長得像 Bot Token 的字串。
- `publish-daily.yml` 只接受 `schedule` 與 `workflow_dispatch` 觸發，**沒有**
  `pull_request` / `pull_request_target`，也不會 checkout 或執行外部 Fork 的
  程式碼，避免外部 PR 觸發 Telegram 發送。
- `deploy-pages.yml`（Pages 部署）與 `publish-daily.yml`（Telegram 發布）是
  **兩個獨立的 workflow**：Pages workflow 的 `permissions` 只有
  `contents: read` / `pages: write` / `id-token: write`，完全不會、也不需要
  存取 Telegram Secrets；Telegram workflow 也不需要 Pages 部署權限。
- 兩個 workflow 都設定了 `concurrency`，避免同一個 workflow 同時重複執行。

## Public Repository 會公開哪些內容

因為這個 repository 是 **Public**，以下內容任何人都看得到：

- `reports/` 內的每日累積分析全文（含來源連結、分析內容）。
- `site/_summaries/` 內每一篇最終每日摘要全文。
- GitHub Actions 的執行紀錄（Actions Logs），包含 workflow 每個步驟的輸出
  （但不含 Secrets 本身——腳本已刻意避免把 Token / Chat ID 印到 log 裡）。
- 這份 README 與所有原始碼、Workflow 設定。

**Secrets 不代表「報告內容」會保密**——`TELEGRAM_BOT_TOKEN` /
`TELEGRAM_CHAT_ID` 這兩個值本身是保密的，但它們發送出去的「每日摘要內容」，
連同 `reports/` 累積分析全文，只要 push 上這個 Public repository，就是公開
資訊。請務必確認分析內容本身不含不該公開的資料（見下一節）。

## 不應放入報告的私人或公司內部資訊

在撰寫或審閱每日分析、最終摘要時，請避免放入：

- 任何人的個人身分資訊（住址、電話、身分證字號、健康狀況等）。
- 公司內部尚未公開的財務數字、策略規劃、人事異動或機密文件內容。
- 未經授權轉載的付費新聞全文（引用摘要與來源連結即可，避免整段複製）。
- 任何帳號密碼、API Key、內部系統網址或憑證。
- 未經證實、可能構成誹謗或造成當事人困擾的指控性內容。

## 常見問題排除

**Q: `Publish Daily Summary` workflow 失敗，說找不到 reports 檔案？**
A: 代表當天（前一天）五個分析排程可能沒有跑完，或還沒 push。請確認
`reports/YYYY-MM-DD.md` 是否存在、五個時段是否齊全、狀態是否為 `ready`。

**Q: workflow 顯示「已發布過，略過」，但我沒收到 Telegram？**
A: 檢查 `.state/published/YYYY-MM-DD` 是否真的存在且對應正確日期——如果存在，
代表系統認為已經發布過。可以先確認 Telegram Bot 是否被封鎖 / Chat ID 是否
正確，再考慮刪除該狀態檔並手動重跑 workflow 補發。

**Q: GitHub Pages 顯示 404 或樣式跑掉？**
A: 通常是 Project Pages 的路徑問題。請確認 `site/_config.yml` 的 `baseurl`
設定為 `/daily-dispatch`（或你的實際 repository 名稱），且所有連結都使用
`relative_url`（本專案的 layout / include / page 都已經這樣處理）。

**Q: 五個 Claude Cowork 排程會不會不小心把 Secrets 寫進 reports？**
A: 五個排程提示詞（`docs/cowork-schedules.md`）明確要求「不得寫入任何
Secrets」，且排程本身也沒有被賦予讀取 GitHub Secrets 的權限（Secrets 只存在
GitHub Actions 環境中）。

**Q: Telegram 訊息裡的連結打開是 404？**
A: 確認 `publish-daily.yml` 執行時間與 `deploy-pages.yml` 部署完成時間有
足夠間隔（預設間隔 10 小時，遠超過建議的 30 分鐘）。如果你調整了排程時間，
請重新確認這個間隔是否仍然足夠。

**Q: 想要暫停某一天的自動發送？**
A: 手動在該日期建立一個空的 `.state/published/YYYY-MM-DD` 檔案並 push，
系統就會判斷「已發布」而跳過；或直接停用/刪除 `publish-daily.yml` 的排程
觸發（但這樣會停用所有日期的自動發送，請視情況選擇合適作法）。
