from datetime import date, datetime, time

from vfk_discord.ics import JST, events_on

ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1
DTSTART:20261018T040000Z
SUMMARY:J2 いわき-甲府
DESCRIPTION:J2 第11節
LOCATION:ハワイアンズスタジアムいわき
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART:20261017T153000Z
SUMMARY:J2 甲府-横浜FC
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;VALUE=DATE:20270220
SUMMARY:J2 磐田-甲府
END:VEVENT
END:VCALENDAR
"""


def test_event_fields_and_jst_start() -> None:
    [event] = [e for e in events_on(ICS, date(2026, 10, 18)) if e.summary == "J2 いわき-甲府"]
    assert event.description == "J2 第11節"
    assert event.location == "ハワイアンズスタジアムいわき"
    assert isinstance(event.start, datetime)
    assert event.start.tzinfo == JST
    assert event.start.time() == time(13, 0)


def test_date_is_judged_in_jst() -> None:
    # 2026-10-17T15:30Z は JST では 10/18 00:30
    summaries = [e.summary for e in events_on(ICS, date(2026, 10, 18))]
    assert summaries == ["J2 いわき-甲府", "J2 甲府-横浜FC"]
    assert events_on(ICS, date(2026, 10, 17)) == []


def test_all_day_event_start_is_date() -> None:
    [event] = events_on(ICS, date(2027, 2, 20))
    assert event.start == date(2027, 2, 20)
    assert not isinstance(event.start, datetime)
