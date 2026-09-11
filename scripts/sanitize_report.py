#!/usr/bin/env python3
"""把某一天的分析／摘要裡「機械上可以自動修正」的格式問題就地修好。

用法：
    python scripts/sanitize_report.py --date 2026-09-10      # 就地修正
    python scripts/sanitize_report.py --date 2026-09-10 --check  # 只檢查不修改
    python scripts/sanitize_report.py --all                   # 掃描全部日期

目前處理的項目：
    1. Markdown 連結文字（[ ] 中間的文字）裡未跳脫的 | 符號 → 改成「-」。
       網站用 kramdown 的 GFM 模式解析，行內未跳脫的 | 會被誤判成表格分隔符，
       導致連結被切成兩半、顯示錯誤。2026-07-26、2026-08-25、2026-09-10 都
       因為這個問題讓 publish-daily.yml 的驗證失敗、當日摘要無法如期發布。

為什麼要有這支腳本（而不是只靠 validate_report.py 擋下來）：
    validate_report.py 是「發布前的最後一道防線」，它只會擋、不會修，而且要
    等到隔天 07:07 的發布流程才跑——內容在前一天 05:00 就寫壞了，中間隔了
    十幾個小時沒有人知道。這支腳本讓同一條規則可以在「寫入當下」就自動修好：
    內容排程 commit 前會呼叫它（見 docs/cloud-schedules.md），
    content-guard.yml 也會在內容 push 進 main 後立刻再跑一次並自動修正。

    修正規則刻意只做「機械上明確、不會改變語意」的替換，絕不重寫分析內容。
"""
from __future__ import annotations

import argparse
import sys

import _common as c


def sanitize_text(content: str) -> tuple[str, list[str]]:
    """回傳 (修正後內容, 說明每一處修正的訊息清單)。

    只替換「連結文字」範圍內的 | 字元，不動網址、不動內文其他地方的 |
    （例如程式碼區塊或表格本身需要的分隔符）。
    """
    fixes: list[str] = []
    out_lines = []
    for lineno, line in enumerate(content.splitlines(keepends=True), start=1):
        new_line = c.LINK_WITH_PIPE_PATTERN.sub(
            lambda m: m.group(0).replace("|", "-"), line
        )
        if new_line != line:
            fixes.append(f"  第 {lineno} 行：{line.strip()}\n    → {new_line.strip()}")
        out_lines.append(new_line)
    return "".join(out_lines), fixes


def sanitize_file(path, check_only: bool) -> list[str]:
    if not path.exists():
        return []
    content = c.read_text(path)
    new_content, fixes = sanitize_text(content)
    if fixes and not check_only:
        c.write_text_atomic(path, new_content)
    if fixes:
        rel = path.relative_to(c.REPO_ROOT)
        verb = "需要修正" if check_only else "已修正"
        return [f"{rel} {verb}："] + fixes
    return []


def targets_for_date(date_str: str):
    return [c.report_path(date_str), c.summary_path(date_str)]


def all_targets():
    yield from sorted(c.REPORTS_DIR.glob("*.md"))
    yield from sorted(c.SUMMARIES_DIR.glob("*.md"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="YYYY-MM-DD，預設為 Asia/Taipei 今天日期")
    parser.add_argument(
        "--all",
        action="store_true",
        help="掃描 reports/ 與 site/_summaries/ 底下所有檔案（忽略 --date）",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只檢查並回報，不修改檔案；有問題時以 Exit Code 1 結束",
    )
    args = parser.parse_args()

    if args.all:
        paths = list(all_targets())
        scope = "全部日期"
    else:
        date_str = c.parse_date_arg(args.date)
        paths = targets_for_date(date_str)
        scope = date_str

    reports = []
    for path in paths:
        reports.extend(sanitize_file(path, args.check))

    if not reports:
        print(f"[daily-dispatch] {scope}：沒有需要修正的格式問題。")
        return

    print("\n".join(reports))
    if args.check:
        c.die(f"{scope} 有可自動修正的格式問題（上面列出），請執行不帶 --check 的同一指令修正")
    print(f"[daily-dispatch] {scope}：已完成自動修正，請記得 commit 修改後的檔案。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - 與其他腳本一致，避免印出完整 traceback
        c.die(f"未預期的錯誤：{exc}")
