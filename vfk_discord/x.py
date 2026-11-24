import html
from dataclasses import dataclass

import requests

API_BASE = "https://api.x.com/2"
_TIMEOUT = 30
_MAX_RESULTS = 100
# 引用ポストは本人の投稿として返るので除外されない
_EXCLUDE = "replies,retweets"
_POST_FIELDS = {
    "tweet.fields": "created_at,entities,attachments",
    "expansions": "attachments.media_keys",
    "media.fields": "type,url,preview_image_url",
}


@dataclass(frozen=True)
class Media:
    type: str  # photo / video / animated_gif
    url: str | None  # photo のみ
    preview_image_url: str | None  # video / animated_gif のみ


@dataclass(frozen=True)
class Post:
    id: str
    text: str
    created_at: str
    media: tuple[Media, ...]


def post_url(username: str, post_id: str) -> str:
    return f"https://x.com/{username}/status/{post_id}"


def _dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"unexpected response: {value!r}")
    return {str(k): v for k, v in value.items()}


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"unexpected response: {value!r}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _display_text(post: dict[str, object]) -> str:
    """t.co を展開し、添付メディアを指す t.co は消す（画像は embed に出すため）。"""
    text = str(post.get("text", ""))
    entities = _dict(post.get("entities", {}))
    for raw_url in _list(entities.get("urls", [])):
        url = _dict(raw_url)
        short = str(url.get("url", ""))
        if not short:
            continue
        if url.get("media_key") or str(url.get("display_url", "")).startswith("pic."):
            text = text.replace(short, "")
        else:
            text = text.replace(short, str(url.get("expanded_url", short)))
    # X API の text は &amp; などが HTML エスケープされたまま返る
    return html.unescape(text).strip()


def parse_page(body: object) -> tuple[list[Post], str | None]:
    """User Posts timeline のレスポンスから（新しい順の投稿, next_token）を取り出す。"""
    root = _dict(body)
    includes = _dict(root.get("includes", {}))
    media_by_key: dict[str, Media] = {}
    for raw_media in _list(includes.get("media", [])):
        media = _dict(raw_media)
        media_by_key[str(media["media_key"])] = Media(
            type=str(media.get("type", "")),
            url=_optional_str(media.get("url")),
            preview_image_url=_optional_str(media.get("preview_image_url")),
        )

    posts: list[Post] = []
    for raw_post in _list(root.get("data", [])):
        post = _dict(raw_post)
        attachments = _dict(post.get("attachments", {}))
        keys = [str(k) for k in _list(attachments.get("media_keys", []))]
        posts.append(
            Post(
                id=str(post["id"]),
                text=_display_text(post),
                created_at=str(post.get("created_at", "")),
                media=tuple(media_by_key[k] for k in keys if k in media_by_key),
            )
        )

    next_token = _dict(root.get("meta", {})).get("next_token")
    return posts, next_token if isinstance(next_token, str) else None


def _get_page(bearer_token: str, user_id: str, params: dict[str, str]) -> object:
    response = requests.get(
        f"{API_BASE}/users/{user_id}/tweets",
        headers={"Authorization": f"Bearer {bearer_token}"},
        params={"exclude": _EXCLUDE, **params},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    body: object = response.json()
    return body


def fetch_latest_post_id(bearer_token: str, user_id: str) -> str | None:
    # 課金は返った投稿数に比例するので、API が許す最小の 5 件だけ取る
    posts, _ = parse_page(_get_page(bearer_token, user_id, {"max_results": "5"}))
    return posts[0].id if posts else None


def fetch_posts_since(bearer_token: str, user_id: str, since_id: str) -> list[Post]:
    """since_id より新しい投稿を古い順に返す。"""
    posts: list[Post] = []
    params = {"since_id": since_id, "max_results": str(_MAX_RESULTS), **_POST_FIELDS}
    while True:
        page, next_token = parse_page(_get_page(bearer_token, user_id, params))
        posts.extend(page)
        if next_token is None:
            break
        params = {**params, "pagination_token": next_token}
    posts.reverse()
    return posts
