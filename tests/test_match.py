from datetime import date, datetime, time

from vfk_discord.ics import JST, CalendarEvent
from vfk_discord.match import Match, opening_message, parse_event, thread_title


def _event(
    summary: str,
    location: str = "",
    start: datetime | date = datetime(2026, 10, 31, 14, 5, tzinfo=JST),
) -> CalendarEvent:
    return CalendarEvent(summary=summary, location=location, start=start)


def _parse(summary: str, location: str = "", start: datetime | date | None = None) -> Match:
    event = _event(summary, location) if start is None else _event(summary, location, start)
    match = parse_event(event)
    assert match is not None
    return match


class TestParseEvent:
    def test_away(self) -> None:
        match = _parse("[Ｊ２]:[A]VS今治 [キックオフ時間]14:05", location="アシさと")
        assert match.competition == "J2"
        assert match.home == "今治"
        assert match.away == "甲府"
        assert match.opponent == "今治"
        assert match.date == date(2026, 10, 31)
        assert match.kickoff == time(14, 5)
        assert match.venue == "アシさと"

    def test_home(self) -> None:
        match = _parse("[Ｊ２]:[H]VS新潟 [キックオフ時間]14:00")
        assert match.home == "甲府"
        assert match.away == "新潟"
        assert match.opponent == "新潟"

    def test_fullwidth_is_normalized(self) -> None:
        match = _parse("[Ｊ２]:[A]VS栃木Ｃ", location="ＪＩＴス")
        assert match.opponent == "栃木C"
        assert match.venue == "JITス"

    def test_kickoff_undecided(self) -> None:
        match = _parse("[Ｊ２]:[A]VS磐田", start=date(2027, 2, 20))
        assert match.date == date(2027, 2, 20)
        assert match.kickoff is None

    def test_garbled_kickoff_suffix_is_ignored(self) -> None:
        # 配信元が折り返し時に壊した文字（U+FFFD）がそのまま含まれることがある
        match = _parse("[Ｊ２・Ｊ３百年構想]:[H]VSいわき [キックオフ時\ufffd\ufffd\ufffd]14:00")
        assert match.opponent == "いわき"

    def test_unparseable_summary(self) -> None:
        assert parse_event(_event("J2 山形-甲府")) is None


class TestThreadTitle:
    def test_league(self) -> None:
        assert thread_title(_parse("[Ｊ２]:[A]VS今治")) == "10/31 今治"

    def test_no_zero_padding(self) -> None:
        match = _parse("[Ｊ２]:[A]VS磐田", start=date(2027, 2, 7))
        assert thread_title(match) == "2/7 磐田"

    def test_levain_cup(self) -> None:
        assert thread_title(_parse("[YLC]:[A]VSFC大阪")) == "10/31 FC大阪（ルヴァン）"

    def test_emperors_cup(self) -> None:
        assert thread_title(_parse("[天皇杯]:[A]VS鹿島")) == "10/31 鹿島（天皇杯）"

    def test_unknown_competition_is_used_as_is(self) -> None:
        match = _parse("[Ｊ２・Ｊ３百年構想]:[H]VS福島")
        assert thread_title(match) == "10/31 福島（J2・J3百年構想）"


class TestOpeningMessage:
    def test_full(self) -> None:
        match = _parse("[Ｊ２]:[A]VS今治 [キックオフ時間]14:05", location="アシさと")
        assert opening_message(match) == "J2\n今治 vs 甲府\nキックオフ: 14:05\n会場: アシさと"

    def test_levain_cup_name(self) -> None:
        assert opening_message(_parse("[YLC]:[A]VSFC大阪")).startswith("ルヴァンカップ\n")

    def test_kickoff_undecided(self) -> None:
        match = _parse("[Ｊ２]:[A]VS磐田", start=date(2027, 2, 20))
        assert "キックオフ: 未定" in opening_message(match)

    def test_missing_venue_line_is_omitted(self) -> None:
        assert "会場" not in opening_message(_parse("[Ｊ２]:[A]VS今治"))
