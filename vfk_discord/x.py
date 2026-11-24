import requests

API_BASE = "https://api.x.com/2"
_TIMEOUT = 30
_MAX_RESULTS = 100
# 引用ポストは本人の投稿として返るので除外されない
_EXCLUDE = "replies,retweets"


def post_url(username: str, post_id: str) -> str:
    return f"https://x.com/{username}/status/{post_id}"


def parse_page(body: object) -> tuple[list[str], str | None]:
    """User Posts timeline のレスポンスから（新しい順の投稿 ID, next_token）を取り出す。"""
    if not isinstance(body, dict):
        raise TypeError(f"unexpected response: {body!r}")
    data = body.get("data", [])
    meta = body.get("meta", {})
    if not isinstance(data, list) or not isinstance(meta, dict):
        raise TypeError(f"unexpected response: {body!r}")
    ids = [str(post["id"]) for post in data if isinstance(post, dict)]
    next_token = meta.get("next_token")
    return ids, next_token if isinstance(next_token, str) else None


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
    ids, _ = parse_page(_get_page(bearer_token, user_id, {"max_results": "5"}))
    return ids[0] if ids else None


def fetch_post_ids_since(bearer_token: str, user_id: str, since_id: str) -> list[str]:
    """since_id より新しい投稿 ID を古い順に返す。"""
    ids: list[str] = []
    params = {"since_id": since_id, "max_results": str(_MAX_RESULTS)}
    while True:
        page_ids, next_token = parse_page(_get_page(bearer_token, user_id, params))
        ids.extend(page_ids)
        if next_token is None:
            break
        params = {**params, "pagination_token": next_token}
    ids.reverse()
    return ids
