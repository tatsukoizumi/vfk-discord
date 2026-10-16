import json
import logging
import sys

from vfk_discord.log import CloudLoggingFormatter


def _record(level: int, msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("vfk_discord.news", level, __file__, 1, msg, args, None)


def test_formats_single_line_json_with_severity() -> None:
    line = CloudLoggingFormatter().format(_record(logging.WARNING, "no new items for %s", "TEAM"))
    assert "\n" not in line
    assert json.loads(line) == {
        "severity": "WARNING",
        "message": "no new items for TEAM",
        "logger": "vfk_discord.news",
    }


def test_includes_traceback_for_exceptions() -> None:
    record = _record(logging.ERROR, "failed")
    try:
        raise ValueError("boom")
    except ValueError:
        record.exc_info = sys.exc_info()
    payload = json.loads(CloudLoggingFormatter().format(record))
    assert payload["severity"] == "ERROR"
    assert payload["message"].startswith("failed\nTraceback")
    assert "ValueError: boom" in payload["message"]
