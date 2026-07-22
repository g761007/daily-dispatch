#!/usr/bin/env python3
"""驗證某一天的每日分析與公開摘要是否已經完整、可以發布。

用法：
    python scripts/validate_report.py --date 2026-07-22
    python scripts/validate_report.py            # 使用 Asia/Taipei 今天日期

檢查項目：
    1. reports/YYYY-MM-DD.md 是否存在。
    2. 五個時段標記（start/end）是否完整。
    3. status 是否為 ready。
    4. site/_summaries/YYYY-MM-DD.md 是否存在。
    5. 公開摘要的 YAML Front Matter 是否包含必要欄位。
    6. 公開摘要內文是否非空。

任何一項失敗都會印出清楚但「不含 Secrets」的錯誤訊息，並以非零 Exit Code 結束。
"""
from __future__ import annotations

import argparse
import re
import sys

import yaml

import _common as c


REQUIRED_FRONT_MATTER_KEYS = ["title", "date", "description", "layout", "published"]


def split_front_matter(content: str) -> tuple[dict, str] | None:
    """將 Jekyll 風格的 YAML Front Matter 從內文中拆出來。"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not match:
        return None
    raw_yaml, body = match.group(1), match.group(2)
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        c.die(f"公開摘要 YAML Front Matter 解析失敗：{exc}")
        raise  # pragma: no cover
    if not isinstance(data, dict):
        c.die("公開摘要 YAML Front Matter 格式錯誤（必須是 key: value 物件）")
    return data, body


def validate(date_str: str) -> None:
    problems: list[str] = []

    report_file = c.report_path(date_str)
    if not report_file.exists():
        c.die(f"找不到 reports/{date_str}.md，尚未開始今日分析")

    content = c.read_text(report_file)

    missing = c.missing_slots(content)
    if missing:
        c.die(
            f"reports/{date_str}.md 缺少或不完整的時段：{', '.join(missing)}"
        )

    status = c.get_status(content)
    if status != "ready":
        c.die(
            f"reports/{date_str}.md 狀態為 {status!r}，尚未標記為 ready，"
            "不可發布"
        )

    summary_file = c.summary_path(date_str)
    if not summary_file.exists():
        c.die(f"找不到 site/_summaries/{date_str}.md，最終摘要尚未產生")

    summary_content = c.read_text(summary_file)
    parsed = split_front_matter(summary_content)
    if parsed is None:
        c.die(f"site/_summaries/{date_str}.md 缺少 YAML Front Matter")
    front_matter, body = parsed

    missing_keys = [key for key in REQUIRED_FRONT_MATTER_KEYS if key not in front_matter]
    if missing_keys:
        c.die(
            "site/_summaries/"
            f"{date_str}.md Front Matter 缺少必要欄位：{', '.join(missing_keys)}"
        )

    if front_matter.get("published") is not True:
        c.die(f"site/_summaries/{date_str}.md 的 published 必須是 true")

    if front_matter.get("layout") != "summary":
        c.die(f"site/_summaries/{date_str}.md 的 layout 必須是 summary")

    if not body.strip():
        c.die(f"site/_summaries/{date_str}.md 內文為空")

    if problems:  # 保留擴充用；目前每個檢查都直接 die，不會走到這裡
        c.die("；".join(problems))

    print(f"[daily-dispatch] {date_str} 驗證通過：五個時段完整、status=ready、公開摘要格式正確")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="YYYY-MM-DD，預設為 Asia/Taipei 今天日期")
    args = parser.parse_args()

    date_str = c.parse_date_arg(args.date)
    validate(date_str)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - 頂層防護，避免印出完整 traceback（可能含路徑等資訊）
        c.die(f"未預期的錯誤：{exc}")
