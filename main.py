import base64
import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import functions_framework
from cloudevents.http import CloudEvent

from vfk_discord import match_threads, news
from vfk_discord.config import Settings
from vfk_discord.store import Store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _target_date(event: CloudEvent) -> date:
    """Pub/Sub メッセージの `{"date": "YYYY-MM-DD"}` を優先し、無ければ JST の今日。"""
    try:
        raw = base64.b64decode(event.data["message"]["data"])
        date_str = json.loads(raw)["date"]
        return date.fromisoformat(date_str)
    except (KeyError, TypeError, ValueError):
        return datetime.now(ZoneInfo("Asia/Tokyo")).date()


@functions_framework.cloud_event
def notify_news(event: CloudEvent) -> None:
    logger.info("notify_news triggered: %s", event["id"])
    news.run(Settings.from_env(), Store())


@functions_framework.cloud_event
def create_match_threads(event: CloudEvent) -> None:
    logger.info("create_match_threads triggered: %s", event["id"])
    match_threads.run(Settings.from_env(), Store(), _target_date(event))
