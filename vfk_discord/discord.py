import requests

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "vfk-discord (https://github.com/tatsukoizumi/vfk-discord, 1.0)"
_TIMEOUT = 30

# テキストチャンネル内の公開スレッド
_CHANNEL_TYPE_PUBLIC_THREAD = 11
# 3 日間投稿がなければ自動アーカイブ
_AUTO_ARCHIVE_MINUTES = 4320


def _bot_headers(bot_token: str) -> dict[str, str]:
    return {"Authorization": f"Bot {bot_token}", "User-Agent": USER_AGENT}


def send_webhook_embed(
    webhook_url: str,
    *,
    author_name: str,
    author_url: str,
    author_icon_url: str,
    title: str,
    title_url: str,
    thumbnail_url: str,
) -> None:
    payload = {
        "embeds": [
            {
                "author": {"name": author_name, "url": author_url, "icon_url": author_icon_url},
                "title": title,
                "url": title_url,
                "thumbnail": {"url": thumbnail_url},
            }
        ]
    }
    response = requests.post(webhook_url, json=payload, timeout=_TIMEOUT)
    response.raise_for_status()


def create_thread(bot_token: str, channel_id: str, name: str) -> str:
    """テキストチャンネルに公開スレッドを作り、スレッド ID を返す。"""
    response = requests.post(
        f"{API_BASE}/channels/{channel_id}/threads",
        headers=_bot_headers(bot_token),
        json={
            "name": name[:100],
            "type": _CHANNEL_TYPE_PUBLIC_THREAD,
            "auto_archive_duration": _AUTO_ARCHIVE_MINUTES,
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def post_message(bot_token: str, channel_id: str, content: str) -> None:
    response = requests.post(
        f"{API_BASE}/channels/{channel_id}/messages",
        headers=_bot_headers(bot_token),
        json={"content": content},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
