#!/usr/bin/env python3
"""建立「當日已發布」狀態檔，避免同一天重複發送 Telegram。

用法：
    python scripts/mark_published.py --date 2026-07-22 --run-id 123456789

行為：
    1. 若 .state/published/YYYY-MM-DD 已存在，直接印出訊息並正常結束（不重複建立）。
    2. 否則建立該檔案，內容包含 date / published_at（Asia/Taipei ISO8601）/ workflow_run。

只有在 Telegram 成功傳送「之後」才應該呼叫本腳本。
"""
from __future__ import annotations

import argparse
import os

import _common as c


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="YYYY-MM-DD，預設為 Asia/Taipei 今天日期")
    parser.add_argument(
        "--run-id",
        help="GitHub Actions Workflow Run ID，預設讀取環境變數 GITHUB_RUN_ID",
    )
    args = parser.parse_args()

    date_str = c.parse_date_arg(args.date)
    run_id = args.run_id or os.environ.get("GITHUB_RUN_ID", "local")

    marker_path = c.published_marker_path(date_str)
    if marker_path.exists():
        print(f"[daily-dispatch] {date_str} 先前已標記為已發布，略過（不重複建立）")
        return

    published_at = c.taipei_now().isoformat(timespec="seconds")
    content = (
        f"date={date_str}\n"
        f"published_at={published_at}\n"
        f"workflow_run={run_id}\n"
    )
    c.write_text_atomic(marker_path, content)
    print(f"[daily-dispatch] 已建立發布狀態檔：.state/published/{date_str}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        c.die(f"未預期的錯誤：{exc}")
