import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

from vfk_discord.discord import USER_AGENT

JST = ZoneInfo("Asia/Tokyo")
_TIMEOUT = 30
_FOLDED_LINE = re.compile(rb"\r?\n[ \t]")


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    location: str
    start: datetime | date  # datetime は JST、date は終日イベント（キックオフ未定）


def fetch(url: str) -> bytes:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.content


def _unfold(data: bytes) -> str:
    """RFC 5545 の行折り返しをバイト列のまま戻してから UTF-8 として読む。

    J リーグのカレンダーはマルチバイト文字の途中で折り返すため、icalendar に任せると
    折り返しを戻す前に行ごとにデコードされて文字化けする。
    """
    return _FOLDED_LINE.sub(b"", data).decode("utf-8")


def _local_start(value: datetime | date) -> datetime | date:
    if isinstance(value, datetime):
        return value.astimezone(JST)
    return value


def _start_date(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def events_on(data: bytes, target_date: date) -> list[CalendarEvent]:
    """JST で target_date に始まるイベントを返す。"""
    events = [
        CalendarEvent(
            summary=str(component.get("SUMMARY", "")),
            location=str(component.get("LOCATION", "")),
            start=_local_start(component.start),
        )
        for component in Calendar.from_ical(_unfold(data)).events
    ]
    return [e for e in events if _start_date(e.start) == target_date]
