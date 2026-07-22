---
layout: default
title: 關於
description: 關於 DailyDispatch 每日新聞摘要專案
permalink: /about.html
---

# 關於 DailyDispatch

DailyDispatch 是一個自動化每日新聞分析與摘要系統。每天固定在五個時段（Asia/Taipei
03:00 / 07:00 / 12:00 / 17:00 / 22:00）搜尋並分析當日重要新聞，最後一個時段結束後
整合成一份「每日摘要」，透過 GitHub Pages 公開發布，並在每天固定時間以 Telegram
傳送給訂閱者。

## 內容產製方式

所有分析內容由自動化流程產生，包含新聞搜尋、事件整理與影響分析。內容會盡量：

- 標註來源連結，方便查證原始報導。
- 區分「已確認事實」與「尚待證實的消息」。
- 合併相同事件的重複報導，避免資訊重複與雜訊。

## 免責聲明

本網站內容為自動化流程產生之整理與分析，**不代表任何機構或個人的正式立場**，
亦不構成投資、法律或其他專業建議。重要資訊請務必以原始來源為準。

## 原始碼

本專案原始碼公開於
[GitHub]({{ "https://github.com/" | append: site.github_username | append: "/" | append: site.repository }})，
歡迎參考或提出建議。
