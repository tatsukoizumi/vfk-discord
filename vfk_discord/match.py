import re
from dataclasses import dataclass
from datetime import date, datetime, time

from vfk_discord.ics import CalendarEvent

_LEAGUE_PREFIXES = frozenset({"J1", "J2", "J3"})
_UNOFFICIAL_PREFIXES = frozenset({"TM", "PSM"})

# 全角・各種ハイフン類（長音「ー」はチーム名に現れうるので含めない）
_HYPHENS = re.compile("[-‐‑‒–—―−－]")


@dataclass(frozen=True)
class Match:
    date: date
    kickoff: time | None  # 終日イベント（キックオフ未定）は None
    prefix: str
    home: str
    away: str
    opponent: str
    round_label: str
    venue: str


def _parse_teams(rest: str) -> tuple[str, str] | None:
    """`山形-甲府` / `鳥栖 2-0 甲府` を (home, away) にする。"""
    tokens = rest.split()
    if len(tokens) == 3:
        # 試合後形式: `鳥栖 2-0 甲府`
        return tokens[0], tokens[2]
    teams = _HYPHENS.sub("-", rest).split("-", 1)
    if len(teams) != 2:
        return None
    home, away = teams[0].strip(), teams[1].strip()
    if not home or not away:
        return None
    return home, away


def parse_event(event: CalendarEvent) -> Match | None:
    """カレンダーイベントを Match にする。非公式戦（TM/PSM）や解釈できないものは None。"""
    summary = event.summary.strip()
    parts = summary.split(None, 1)
    if len(parts) != 2:
        return None
    prefix, rest = parts
    if prefix in _UNOFFICIAL_PREFIXES:
        return None

    if isinstance(event.start, datetime):
        match_date, kickoff = event.start.date(), event.start.time()
    else:
        match_date, kickoff = event.start, None

    teams = _parse_teams(rest)
    if teams is None:
        return None
    home, away = teams
    opponent = away if home == "甲府" else home

    return Match(
        date=match_date,
        kickoff=kickoff,
        prefix=prefix,
        home=home,
        away=away,
        opponent=opponent,
        round_label=event.description.strip(),
        venue=event.location.strip(),
    )


def thread_title(match: Match) -> str:
    date_label = f"{match.date.month}/{match.date.day}"
    if match.prefix in _LEAGUE_PREFIXES:
        return f"{date_label} {match.opponent}"
    if match.prefix == "JC":
        return f"{date_label} {match.opponent}（ルヴァン）"
    return f"{date_label} {match.opponent}（{match.prefix}）"


def opening_message(match: Match) -> str:
    kickoff = match.kickoff.strftime("%H:%M") if match.kickoff is not None else "未定"
    lines = []
    if match.round_label:
        lines.append(match.round_label)
    lines.append(f"{match.home} vs {match.away}")
    lines.append(f"キックオフ: {kickoff}")
    if match.venue:
        lines.append(f"会場: {match.venue}")
    return "\n".join(lines)
