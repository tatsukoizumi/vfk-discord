import logging
from datetime import date

from vfk_discord import discord, ics
from vfk_discord.config import Settings
from vfk_discord.match import is_unofficial, opening_message, parse_event, thread_title
from vfk_discord.store import Store

logger = logging.getLogger(__name__)


def run(settings: Settings, store: Store, target_date: date) -> None:
    events = ics.events_on(ics.fetch(settings.match_calendar_ics_url), target_date)
    if not events:
        logger.info("no events on %s", target_date.isoformat())
        return
    logger.info("%d event(s) on %s", len(events), target_date.isoformat())

    for event in events:
        if is_unofficial(event):
            logger.info("skipping unofficial match: %s", event.summary)
            continue
        match = parse_event(event)
        if match is None:
            # ICS の件名形式が変わった可能性があるので気づけるように WARNING にする
            logger.warning("could not parse event: %s", event.summary)
            continue

        key = f"{match.date.isoformat()}_{match.opponent}"
        if store.match_thread_exists(key):
            logger.info("thread already created for %s", key)
            continue

        title = thread_title(match)
        # 先にスレッドを作ることで、途中失敗→再実行時にチャンネルへ孤児メッセージが残らない
        thread_id = discord.create_thread(
            settings.discord_bot_token, settings.discord_match_channel_id, title
        )
        discord.post_message(settings.discord_bot_token, thread_id, opening_message(match))
        store.mark_match_thread(key, thread_id)
        logger.info("created thread %s for %s", thread_id, key)
