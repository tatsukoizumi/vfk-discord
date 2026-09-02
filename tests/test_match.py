from datetime import date, time

from vfk_discord.gcal import CalendarEvent
from vfk_discord.match import Match, opening_message, parse_event, thread_title


def _event(
    summary: str,
    description: str = "",
    location: str = "",
    date_time: str | None = "2026-09-05T14:00:00+09:00",
    all_day_date: str | None = None,
) -> CalendarEvent:
    start: dict[str, str] = {}
    if date_time is not None:
        start["dateTime"] = date_time
    if all_day_date is not None:
        start = {"date": all_day_date}
    return CalendarEvent(
        summary=summary,
        description=description,
        location=location,
        start=start,  # type: ignore[typeddict-item]
    )


def _parse(summary: str, **kwargs: str | None) -> Match:
    match = parse_event(_event(summary, **kwargs))  # type: ignore[arg-type]
    assert match is not None
    return match


class TestParseEvent:
    def test_league_away(self) -> None:
        match = _parse("J2 山形-甲府", description="J2 第28節", location="NDソフトスタジアム山形")
        assert match.home == "山形"
        assert match.away == "甲府"
        assert match.opponent == "山形"
        assert match.date == date(2026, 9, 5)
        assert match.kickoff == time(14, 0)
        assert match.round_label == "J2 第28節"
        assert match.venue == "NDソフトスタジアム山形"

    def test_league_home(self) -> None:
        match = _parse("J2 甲府-仙台")
        assert match.home == "甲府"
        assert match.away == "仙台"
        assert match.opponent == "仙台"

    def test_post_match_score_format(self) -> None:
        match = _parse("J2 鳥栖 2-0 甲府")
        assert match.home == "鳥栖"
        assert match.away == "甲府"
        assert match.opponent == "鳥栖"

    def test_fullwidth_hyphen(self) -> None:
        match = _parse("J2 山形－甲府")
        assert match.opponent == "山形"

    def test_all_day_event_has_no_kickoff(self) -> None:
        match = _parse("J2 山形-甲府", date_time=None, all_day_date="2026-09-05")
        assert match.date == date(2026, 9, 5)
        assert match.kickoff is None

    def test_description_is_stripped(self) -> None:
        match = _parse("天皇杯 鹿島-甲府", description="天皇杯 3回戦 ")
        assert match.round_label == "天皇杯 3回戦"

    def test_tm_is_skipped(self) -> None:
        assert parse_event(_event("TM 浦和-甲府")) is None

    def test_psm_is_skipped(self) -> None:
        assert parse_event(_event("PSM 松本-甲府")) is None

    def test_summary_without_space_is_skipped(self) -> None:
        assert parse_event(_event("休養日")) is None

    def test_rest_without_hyphen_is_skipped(self) -> None:
        assert parse_event(_event("J2 ミーティング")) is None

    def test_event_without_start_is_skipped(self) -> None:
        event = CalendarEvent(summary="J2 山形-甲府")
        assert parse_event(event) is None


class TestThreadTitle:
    def test_league(self) -> None:
        assert thread_title(_parse("J2 山形-甲府")) == "9/5 山形"

    def test_league_no_zero_padding(self) -> None:
        match = _parse("J2 甲府-福島", date_time="2027-02-07T13:00:00+09:00")
        assert thread_title(match) == "2/7 福島"

    def test_levain_cup(self) -> None:
        match = _parse("JC FC大阪-甲府", date_time="2026-09-02T19:00:00+09:00")
        assert thread_title(match) == "9/2 FC大阪（ルヴァン）"

    def test_emperors_cup(self) -> None:
        match = _parse("天皇杯 鹿島-甲府", date_time="2026-09-23T18:00:00+09:00")
        assert thread_title(match) == "9/23 鹿島（天皇杯）"

    def test_unknown_prefix_is_treated_as_cup(self) -> None:
        match = _parse("J2・J3百年構想 甲府-福島", date_time="2027-02-07T13:00:00+09:00")
        assert thread_title(match) == "2/7 福島（J2・J3百年構想）"


class TestOpeningMessage:
    def test_full(self) -> None:
        match = _parse("J2 山形-甲府", description="J2 第28節", location="NDソフトスタジアム山形")
        assert opening_message(match) == (
            "J2 第28節\n山形 vs 甲府\nキックオフ: 14:00\n会場: NDソフトスタジアム山形"
        )

    def test_all_day_kickoff_is_unknown(self) -> None:
        match = _parse("J2 山形-甲府", date_time=None, all_day_date="2026-09-05")
        assert "キックオフ: 未定" in opening_message(match)

    def test_missing_venue_line_is_omitted(self) -> None:
        match = _parse("J2 山形-甲府", description="J2 第28節")
        assert "会場" not in opening_message(match)
