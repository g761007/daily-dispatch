#!/usr/bin/env python3
"""將公開每日摘要（site/_summaries/YYYY-MM-DD.md）轉換成適合 Telegram 傳送的版本。

用法：
    python scripts/extract_summary.py --date 2026-07-22 \
        --base-url "https://YOUR_GITHUB_USERNAME.github.io/daily-dispatch"

行為：
    1. 讀取 site/_summaries/YYYY-MM-DD.md，移除 YAML Front Matter。
    2. 只保留「今日重點」「今日趨勢」「明日觀察」三個區塊（不傳送完整五時段原文）。
    3. 加入當日 GitHub Pages 網址。
    4. 做好 HTML escape（Telegram 使用 HTML 解析模式，不用 MarkdownV2）。
    5. 若總長度超過建議長度，先縮短「今日趨勢」「今日觀察」等次要區塊。
    6. 若縮短後仍超過 Telegram 單則訊息長度限制，安全地拆成多則訊息，
       且第一則訊息一定包含標題與頁面網址。
    7. 將結果寫入暫存目錄，並輸出 manifest.json 供 send_telegram.py 讀取。

本腳本不會讀取或輸出任何 Secrets。
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from html import escape as _html_escape
from pathlib import Path

import _common as c

TELEGRAM_HARD_LIMIT = 4096  # Telegram 單則訊息（HTML 模式）字元上限
SOFT_TARGET = 3000  # 專案建議的目標長度
SECTION_TRUNCATE_LIMIT = 700  # 縮短時，次要區塊最多保留的字元數

SECTION_HEADINGS = {
    "highlights": "今日重點",
    "trends": "今日趨勢",
    "tomorrow": "明日觀察",
}


def html_escape(text: str) -> str:
    return _html_escape(text, quote=False)


def strip_front_matter(content: str) -> str:
    match = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)$", content, re.DOTALL)
    return match.group(1) if match else content


def extract_section(body: str, heading: str) -> str:
    """取出 `## {heading}` 到下一個 `## ` 之間的內容（純文字，已去除多餘空白）。"""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return ""
    return match.group(1).strip()


def truncate_section(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_break = cut.rfind("\n")
    if last_break > limit * 0.5:
        cut = cut[:last_break]
    return cut.rstrip() + "\n…（內容已縮短，完整內容請見網頁版）"


def pack_blocks(blocks: list[str], limit: int) -> list[str]:
    """把多個「不可再切」的段落，貪婪地打包進多則訊息，每則 <= limit 字元。"""
    messages: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            messages.append(current)
            current = ""

    for block in blocks:
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= limit:
            current = candidate
            continue
        flush()
        if len(block) <= limit:
            current = block
            continue
        # 單一段落本身就超過上限，改以「行」為單位繼續打包
        for line in block.split("\n"):
            candidate_line = line if not current else current + "\n" + line
            if len(candidate_line) <= limit:
                current = candidate_line
                continue
            flush()
            if len(line) <= limit:
                current = line
            else:
                # 單一行本身就超過上限：依長度切成多個 limit 大小的區塊，
                # 全部併入訊息佇列，不捨棄任何內容（避免內容被靜默截斷遺失）。
                for i in range(0, len(line), limit):
                    chunk = line[i : i + limit]
                    if len(chunk) == limit:
                        messages.append(chunk)
                    else:
                        current = chunk  # 最後不足 limit 的一段，留給後續內容接續打包
    flush()
    return messages


def build_messages(date_str: str, url: str, sections: dict[str, str]) -> list[str]:
    escaped = {key: html_escape(value) if value else "本時段沒有可整理的內容。" for key, value in sections.items()}

    lead = f"📰 {date_str} 每日新聞摘要\n{url}"
    highlight_block = f"【{SECTION_HEADINGS['highlights']}】\n{escaped['highlights']}"
    trend_block = f"【{SECTION_HEADINGS['trends']}】\n{escaped['trends']}"
    tomorrow_block = f"【{SECTION_HEADINGS['tomorrow']}】\n{escaped['tomorrow']}"
    footer_block = f"完整內容：\n{url}"

    full_blocks = [lead, highlight_block, trend_block, tomorrow_block, footer_block]
    full_text = "\n\n".join(full_blocks)
    if len(full_text) <= SOFT_TARGET:
        return [full_text]

    shortened_sections = {
        "highlights": escaped["highlights"],  # 今日重點是核心內容，不縮短
        "trends": truncate_section(escaped["trends"], SECTION_TRUNCATE_LIMIT),
        "tomorrow": truncate_section(escaped["tomorrow"], SECTION_TRUNCATE_LIMIT),
    }
    shortened_blocks = [
        lead,
        f"【{SECTION_HEADINGS['highlights']}】\n{shortened_sections['highlights']}",
        f"【{SECTION_HEADINGS['trends']}】\n{shortened_sections['trends']}",
        f"【{SECTION_HEADINGS['tomorrow']}】\n{shortened_sections['tomorrow']}",
        footer_block,
    ]
    shortened_text = "\n\n".join(shortened_blocks)
    if len(shortened_text) <= TELEGRAM_HARD_LIMIT:
        return [shortened_text]

    return pack_blocks(shortened_blocks, TELEGRAM_HARD_LIMIT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="YYYY-MM-DD，預設為 Asia/Taipei 今天日期")
    parser.add_argument(
        "--base-url",
        required=True,
        help='GitHub Pages 網域，例如 "https://YOUR_GITHUB_USERNAME.github.io/daily-dispatch"（不要有結尾斜線）',
    )
    parser.add_argument(
        "--output-dir",
        help="輸出訊息檔案的暫存目錄，預設為系統暫存目錄下的隨機資料夾",
    )
    args = parser.parse_args()

    date_str = c.parse_date_arg(args.date)
    base_url = args.base_url.rstrip("/")

    summary_file = c.summary_path(date_str)
    if not summary_file.exists():
        c.die(f"找不到 site/_summaries/{date_str}.md，無法產生 Telegram 摘要")

    content = c.read_text(summary_file)
    body = strip_front_matter(content)

    sections = {
        "highlights": extract_section(body, SECTION_HEADINGS["highlights"]),
        "trends": extract_section(body, SECTION_HEADINGS["trends"]),
        "tomorrow": extract_section(body, SECTION_HEADINGS["tomorrow"]),
    }

    if not any(sections.values()):
        c.die(f"site/_summaries/{date_str}.md 內容為空或格式不符，找不到任何區塊")

    page_url = f"{base_url}/daily/{date_str}/"
    messages = build_messages(date_str, page_url, sections)

    output_dir = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp(prefix="daily-dispatch-telegram-"))
    output_dir.mkdir(parents=True, exist_ok=True)

    message_files = []
    for index, message in enumerate(messages, start=1):
        file_name = f"telegram-message-{index}.txt"
        file_path = output_dir / file_name
        file_path.write_text(message, encoding="utf-8")
        message_files.append(file_name)

    manifest = {
        "date": date_str,
        "url": page_url,
        "count": len(message_files),
        "messages": message_files,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[daily-dispatch] 已產生 {len(message_files)} 則 Telegram 訊息於 {output_dir}")
    print(str(manifest_path))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        c.die(f"未預期的錯誤：{exc}")
