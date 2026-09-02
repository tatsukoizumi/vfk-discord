from datetime import date

from vfk_discord.gcal import day_range_jst


def test_day_range_jst() -> None:
    assert day_range_jst(date(2026, 9, 5)) == (
        "2026-09-05T00:00:00+09:00",
        "2026-09-06T00:00:00+09:00",
    )


def test_day_range_jst_crosses_month_end() -> None:
    assert day_range_jst(date(2026, 9, 30)) == (
        "2026-09-30T00:00:00+09:00",
        "2026-10-01T00:00:00+09:00",
    )
