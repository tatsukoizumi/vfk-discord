import logging

from vfk_discord import discord, x
from vfk_discord.config import Settings
from vfk_discord.news import LOGO_URL
from vfk_discord.store import Store

logger = logging.getLogger(__name__)

USERNAME = "vfk_official"
AUTHOR_NAME = f"ヴァンフォーレ甲府 (@{USERNAME})"
# Discord は url が同じ embed の画像を 1 つのギャラリーにまとめる（最大 4 枚）
_GALLERY_MAX = 4
_DESCRIPTION_MAX = 4096
_VIDEO_TYPES = ("video", "animated_gif")


def build_embeds(post: x.Post) -> list[dict[str, object]]:
    url = x.post_url(USERNAME, post.id)
    photos = [m.url for m in post.media if m.type == "photo" and m.url][:_GALLERY_MAX]
    previews = [
        m.preview_image_url for m in post.media if m.type in _VIDEO_TYPES and m.preview_image_url
    ]

    description = post.text
    if previews:
        description = f"{description}\n\n▶ [動画・GIF を X で見る]({url})".strip()

    embed: dict[str, object] = {
        "author": {"name": AUTHOR_NAME, "url": url, "icon_url": LOGO_URL},
        "url": url,
    }
    if description:
        embed["description"] = description[:_DESCRIPTION_MAX]
    if post.created_at:
        embed["timestamp"] = post.created_at
    if photos:
        embed["image"] = {"url": photos[0]}
    if previews:
        embed["thumbnail"] = {"url": previews[0]}
    gallery: list[dict[str, object]] = [{"url": url, "image": {"url": p}} for p in photos[1:]]
    return [embed, *gallery]


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

    posts = x.fetch_posts_since(settings.x_bearer_token, user_id, saved_id)
    if not posts:
        logger.info("no new posts")
        return

    # 1 件ごとに保存し、送信に失敗したら次回はその投稿から再開する
    for post in posts:
        logger.info("sending post %s", post.id)
        discord.send_webhook_embeds(settings.discord_webhook_url_x, build_embeds(post))
        store.set_latest_x_post_id(user_id, post.id)
