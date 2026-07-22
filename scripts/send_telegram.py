#!/usr/bin/env python3
"""將 extract_summary.py 產生的訊息，依序透過 Telegram Bot API 傳送。

用法：
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
        python scripts/send_telegram.py --manifest /tmp/xxx/manifest.json

規則：
    * Token 與 Chat ID 只能從環境變數讀取，不接受命令列參數。
    * 不輸出完整 Telegram API URL、不輸出 Token 或 Chat ID。
    * 不使用 curl -v、不使用 set -x（由呼叫端的 workflow 負責遵守）。
    * 任一則訊息傳送失敗，就以非零 Exit Code 結束，不繼續傳送剩餘訊息。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

import _common as c

TELEGRAM_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT_SECONDS = 15
RETRY_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 3

# 保險：萬一任何來源的文字裡混入類似 Bot Token 的字串，一律遮蔽再輸出。
_TOKEN_PATTERN = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")


def redact(text: str) -> str:
    return _TOKEN_PATTERN.sub("[REDACTED]", text)


def load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        c.die("找不到 manifest 檔案，請先執行 extract_summary.py")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        c.die(f"manifest 檔案格式錯誤：{exc}")
        raise  # pragma: no cover


def send_one_message(token: str, chat_id: str, text: str) -> None:
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    last_error: str | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 2):
        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last_error = f"連線錯誤（{type(exc).__name__}）"
        else:
            try:
                data = response.json()
            except ValueError:
                data = {}

            if response.status_code == 200 and data.get("ok") is True:
                return

            description = redact(str(data.get("description", "")))
            last_error = f"HTTP {response.status_code}，Telegram 回應：{description or '(無說明)'}"

        if attempt <= RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)

    c.die(f"Telegram 訊息傳送失敗：{last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="extract_summary.py 產生的 manifest.json 路徑")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        c.die("缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 環境變數（必須由 GitHub Actions Secrets 提供）")

    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    message_files = manifest.get("messages", [])
    if not message_files:
        c.die("manifest 內沒有任何訊息可傳送")

    base_dir = manifest_path.parent
    total = len(message_files)
    for index, file_name in enumerate(message_files, start=1):
        message_path = base_dir / file_name
        if not message_path.exists():
            c.die(f"找不到訊息檔案：第 {index}/{total} 則")
        text = message_path.read_text(encoding="utf-8")
        send_one_message(token, chat_id, text)
        print(f"[daily-dispatch] 已傳送第 {index}/{total} 則 Telegram 訊息")

    print(f"[daily-dispatch] 全部 {total} 則 Telegram 訊息傳送完成")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        c.die(f"未預期的錯誤：{redact(str(type(exc).__name__))}")
        sys.exit(1)
