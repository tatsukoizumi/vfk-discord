from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

from vfk_discord.discord import USER_AGENT

JST = ZoneInfo("Asia/Tokyo")
_TIMEOUT = 30


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    description: str
    location: str
    start: datetime | date  # datetime は JST、date は終日イベント（キックオフ未定）


def fetch(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT)
    response.raise_for_status()
    # Content-Type に charset が無い配信元でも文字化けしないよう UTF-8 で決め打ちする
    return response.content.decode("utf-8")


def _local_start(value: datetime | date) -> datetime | date:
    if isinstance(value, datetime):
        return value.astimezone(JST)
    return value


def _start_date(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def events_on(ics_text: str, target_date: date) -> list[CalendarEvent]:
    """JST で target_date に始まるイベントを返す。"""
    events = [
        CalendarEvent(
            summary=str(component.get("SUMMARY", "")),
            description=str(component.get("DESCRIPTION", "")),
            location=str(component.get("LOCATION", "")),
            start=_local_start(component.start),
        )
        for component in Calendar.from_ical(ics_text).events
    ]
    return [e for e in events if _start_date(e.start) == target_date]
