from datetime import date, timedelta
from typing import TypedDict
from urllib.parse import quote

import requests

_TIMEOUT = 30
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"


class EventStart(TypedDict, total=False):
    dateTime: str
    date: str


class CalendarEvent(TypedDict, total=False):
    summary: str
    description: str
    location: str
    start: EventStart


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    response = requests.post(
        _TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def day_range_jst(target_date: date) -> tuple[str, str]:
    """JST の当日 00:00:00 から翌日 00:00:00 までの timeMin/timeMax。"""
    next_day = target_date + timedelta(days=1)
    return (
        f"{target_date.isoformat()}T00:00:00+09:00",
        f"{next_day.isoformat()}T00:00:00+09:00",
    )


def list_events(access_token: str, calendar_id: str, target_date: date) -> list[CalendarEvent]:
    time_min, time_max = day_range_jst(target_date)
    response = requests.get(
        _EVENTS_URL.format(calendar_id=quote(calendar_id, safe="")),
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            # 終日イベントを JST の日付で範囲判定させるために必要
            "timeZone": "Asia/Tokyo",
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    items: list[CalendarEvent] = response.json().get("items", [])
    return items
