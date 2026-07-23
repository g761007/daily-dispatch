"""daily-dispatch 共用工具函式。

所有腳本共用同一套日期／時區／檔案路徑邏輯，避免各腳本各自實作、
彼此不一致。此模組不得輸出任何 Secrets，也不應該依賴任何環境變數
中可能含有敏感資訊的值。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# scripts/_common.py -> repo root 是上一層
REPO_ROOT = Path(__file__).resolve().parent.parent

REPORTS_DIR = REPO_ROOT / "reports"
SUMMARIES_DIR = REPO_ROOT / "site" / "_summaries"
PUBLISHED_DIR = REPO_ROOT / ".state" / "published"

# 每日五個固定分析時段（Asia/Taipei）。
# 「24:00」是傳統節目表式的記法，代表「當天最後一次」，實際觸發時刻是隔天 00:00，
# 但邏輯上仍歸屬於前一個日曆日（見 docs/cowork-schedules.md 排程五的日期換算說明）。
SLOTS = ["05:00", "10:00", "15:00", "20:00", "24:00"]
FINAL_SLOT = "24:00"

DATE_FMT = "%Y-%m-%d"


def die(message: str, code: int = 1) -> None:
    """輸出錯誤訊息到 stderr 並結束程式。呼叫端須確保 message 不含 Secrets。"""
    print(f"[daily-dispatch] 錯誤：{message}", file=sys.stderr)
    sys.exit(code)


def taipei_now() -> datetime:
    return datetime.now(TAIPEI)


def taipei_today_str() -> str:
    return taipei_now().strftime(DATE_FMT)


def parse_date_arg(date_str: str | None) -> str:
    """驗證並回傳 YYYY-MM-DD 字串；未提供時使用 Asia/Taipei 今天日期。"""
    if not date_str:
        return taipei_today_str()
    try:
        parsed = datetime.strptime(date_str, DATE_FMT)
    except ValueError:
        die(f"日期格式錯誤：{date_str!r}，必須是 YYYY-MM-DD")
        raise  # pragma: no cover - die() 會結束程式
    return parsed.strftime(DATE_FMT)


def report_path(date_str: str) -> Path:
    return REPORTS_DIR / f"{date_str}.md"


def summary_path(date_str: str) -> Path:
    return SUMMARIES_DIR / f"{date_str}.md"


def published_marker_path(date_str: str) -> Path:
    return PUBLISHED_DIR / date_str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text_atomic(path: Path, content: str) -> None:
    """以「寫暫存檔後 rename」的方式寫入，避免寫到一半被中斷造成檔案損毀。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def get_status(content: str) -> str | None:
    """取出 <!-- status: xxx --> 標記內容。"""
    import re

    match = re.search(r"<!--\s*status:\s*(\w+)\s*-->", content)
    return match.group(1) if match else None


def slot_span(content: str, slot: str) -> tuple[int, int] | None:
    """回傳 (start_marker_index, end_marker_index) 或 None（找不到該時段）。

    要求 start 與 end 標記都存在，且 start 在 end 之前。
    """
    import re

    start_re = re.compile(rf"<!--\s*slot:\s*{re.escape(slot)}:start\s*-->")
    end_re = re.compile(rf"<!--\s*slot:\s*{re.escape(slot)}:end\s*-->")
    start_match = start_re.search(content)
    end_match = end_re.search(content)
    if not start_match or not end_match:
        return None
    if start_match.start() >= end_match.start():
        return None
    return start_match.start(), end_match.end()


def slot_body(content: str, slot: str) -> str | None:
    """取出某時段 start/end 標記「之間」的內容（不含標記本身）。"""
    import re

    start_re = re.compile(rf"<!--\s*slot:\s*{re.escape(slot)}:start\s*-->")
    end_re = re.compile(rf"<!--\s*slot:\s*{re.escape(slot)}:end\s*-->")
    start_match = start_re.search(content)
    end_match = end_re.search(content)
    if not start_match or not end_match or start_match.start() >= end_match.start():
        return None
    return content[start_match.end():end_match.start()].strip()


def missing_slots(content: str) -> list[str]:
    """回傳缺少（或不完整）的時段清單。

    「缺少」涵蓋兩種情況：start/end 標記本身不存在（或順序錯誤），以及
    標記存在但中間沒有實際內容（例如檔案剛建立時的空骨架，或某次排程
    失敗、只留下一對空標記）。兩種情況都視為「這個時段沒有可用內容」，
    這樣 validate_report.py 的「五個時段是否全部沒有內容」防呆判斷才會
    正確；至於「缺 1～4 個時段仍可發布」的行為，是刻意設計、不受這個
    函式影響（見 docs/cowork-schedules.md 排程五）。
    """
    return [slot for slot in SLOTS if not slot_body(content, slot)]
