import logging

from vfk_discord import discord, x
from vfk_discord.config import Settings
from vfk_discord.store import Store

logger = logging.getLogger(__name__)

USERNAME = "vfk_official"


def run(settings: Settings, store: Store) -> None:
    user_id = settings.x_user_id
    saved_id = store.get_latest_x_post_id(user_id)

    if not saved_id:
        # 初回は基準点だけ記録する。送ると過去の投稿がまとめて流れてしまう
        latest_id = x.fetch_latest_post_id(settings.x_bearer_token, user_id)
        if latest_id is not None:
            store.set_latest_x_post_id(user_id, latest_id)
        logger.info("initialized latest post id: %s", latest_id)
        return

    post_ids = x.fetch_post_ids_since(settings.x_bearer_token, user_id, saved_id)
    if not post_ids:
        logger.info("no new posts")
        return

    # 1 件ごとに保存し、送信に失敗したら次回はその投稿から再開する
    for post_id in post_ids:
        logger.info("sending post %s", post_id)
        discord.send_webhook_message(settings.discord_webhook_url_x, x.post_url(USERNAME, post_id))
        store.set_latest_x_post_id(user_id, post_id)
