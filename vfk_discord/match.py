import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time

from vfk_discord.ics import CalendarEvent

HOME_TEAM = "甲府"

_LEAGUES = frozenset({"J1", "J2", "J3"})
# スレッド名の括弧書き。未登録の大会は大会名をそのまま使う
_CUP_SUFFIXES = {"YLC": "ルヴァン"}
_COMPETITION_NAMES = {"YLC": "ルヴァンカップ"}

# J リーグ公式カレンダーの件名: `[J2]:[A]VS今治 [キックオフ時間]14:05`（キックオフ未定なら後半なし）
_SUMMARY = re.compile(r"^\[(?P<competition>[^\]]+)\]:\[(?P<side>[HA])\]VS(?P<opponent>\S+)")


@dataclass(frozen=True)
class Match:
    date: date
    kickoff: time | None  # 終日イベント（キックオフ未定）は None
    competition: str
    home: str
    away: str
    opponent: str
    venue: str


def _normalize(text: str) -> str:
    """全角英数字（`Ｊ２`・`栃木Ｃ`）を半角にそろえる。"""
    return unicodedata.normalize("NFKC", text).strip()


def parse_event(event: CalendarEvent) -> Match | None:
    """カレンダーイベントを Match にする。件名を解釈できなければ None。"""
    m = _SUMMARY.match(_normalize(event.summary))
    if m is None:
        return None
    competition, opponent = m["competition"], m["opponent"]
    home, away = (HOME_TEAM, opponent) if m["side"] == "H" else (opponent, HOME_TEAM)

    if isinstance(event.start, datetime):
        match_date, kickoff = event.start.date(), event.start.time()
    else:
        match_date, kickoff = event.start, None

    return Match(
        date=match_date,
        kickoff=kickoff,
        competition=competition,
        home=home,
        away=away,
        opponent=opponent,
        venue=_normalize(event.location),
    )


def thread_title(match: Match) -> str:
    date_label = f"{match.date.month}/{match.date.day}"
    if match.competition in _LEAGUES:
        return f"{date_label} {match.opponent}"
    suffix = _CUP_SUFFIXES.get(match.competition, match.competition)
    return f"{date_label} {match.opponent}（{suffix}）"


def opening_message(match: Match) -> str:
    kickoff = match.kickoff.strftime("%H:%M") if match.kickoff is not None else "未定"
    lines = [
        _COMPETITION_NAMES.get(match.competition, match.competition),
        f"{match.home} vs {match.away}",
        f"キックオフ: {kickoff}",
    ]
    if match.venue:
        lines.append(f"会場: {match.venue}")
    return "\n".join(lines)
