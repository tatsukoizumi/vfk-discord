from datetime import date, datetime, time

from vfk_discord.ics import JST, events_on

_SUMMARY = "[Ｊ２]:[A]VS今治 [キックオフ時間]14:05".encode()
# J リーグのカレンダーと同じく、マルチバイト文字（「時」）の途中で折り返す
_FOLD_AT = _SUMMARY.index("時".encode()) + 1

ICS = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
    b"BEGIN:VEVENT\r\nUID:1\r\nDTSTART;TZID=Asia/Tokyo:20261031T140500\r\n"
    b"SUMMARY:" + _SUMMARY[:_FOLD_AT] + b"\r\n " + _SUMMARY[_FOLD_AT:] + b"\r\n"
    b"LOCATION:" + "アシさと".encode() + b"\r\nEND:VEVENT\r\n"
    b"BEGIN:VEVENT\r\nUID:2\r\nDTSTART:20261030T153000Z\r\n"
    b"SUMMARY:" + "[Ｊ２]:[H]VS新潟".encode() + b"\r\nEND:VEVENT\r\n"
    b"BEGIN:VEVENT\r\nUID:3\r\nDTSTART;VALUE=DATE:20270220\r\n"
    b"SUMMARY:" + "[Ｊ２]:[A]VS磐田".encode() + b"\r\nEND:VEVENT\r\n"
    b"END:VCALENDAR\r\n"
)


def test_unfolds_line_split_inside_multibyte_char() -> None:
    [event, _] = events_on(ICS, date(2026, 10, 31))
    assert event.summary == "[Ｊ２]:[A]VS今治 [キックオフ時間]14:05"
    assert event.location == "アシさと"


def test_start_is_jst_datetime() -> None:
    [event, _] = events_on(ICS, date(2026, 10, 31))
    assert isinstance(event.start, datetime)
    assert event.start.tzinfo == JST
    assert event.start.time() == time(14, 5)


def test_date_is_judged_in_jst() -> None:
    # 2026-10-30T15:30Z は JST では 10/31 00:30
    summaries = [e.summary for e in events_on(ICS, date(2026, 10, 31))]
    assert summaries == ["[Ｊ２]:[A]VS今治 [キックオフ時間]14:05", "[Ｊ２]:[H]VS新潟"]
    assert events_on(ICS, date(2026, 10, 30)) == []


def test_all_day_event_start_is_date() -> None:
    [event] = events_on(ICS, date(2027, 2, 20))
    assert event.start == date(2027, 2, 20)
    assert not isinstance(event.start, datetime)
