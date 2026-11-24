import json
from pathlib import Path

import pytest
import requests

from vfk_discord import x

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> object:
    body: object = json.loads((FIXTURES / name).read_text())
    return body


class FakeResponse:
    def __init__(self, body: object) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._body


class FakeGet:
    """requests.get の代わり。呼ばれた順にページを返し、受け取った params を記録する。"""

    def __init__(self, *pages: str) -> None:
        self._pages = [_load(name) for name in pages]
        self.params: list[dict[str, str]] = []

    def __call__(self, url: str, *, params: dict[str, str], **_: object) -> FakeResponse:
        self.params.append(params)
        return FakeResponse(self._pages.pop(0))


def test_parse_page() -> None:
    posts, next_token = x.parse_page(_load("x_posts_page1.json"))
    assert posts == [
        x.Post(
            id="1993000000000000004",
            text="【試合情報】11/29（日）ホームゲーム開催！チケット&イベント情報はこちら "
            "https://www.ventforet.jp/news/match/20261124_01",
            created_at="2026-11-24T03:00:00.000Z",
            media=(
                x.Media(
                    type="photo",
                    url="https://pbs.twimg.com/media/photo1.jpg",
                    preview_image_url=None,
                ),
                x.Media(
                    type="photo",
                    url="https://pbs.twimg.com/media/photo2.jpg",
                    preview_image_url=None,
                ),
            ),
        ),
        x.Post(
            id="1993000000000000003",
            text="本日の練習の様子です",
            created_at="2026-11-24T01:00:00.000Z",
            media=(
                x.Media(
                    type="video",
                    url=None,
                    preview_image_url="https://pbs.twimg.com/amplify_video_thumb/2001/img/preview.jpg",
                ),
            ),
        ),
    ]
    assert next_token == "7140dibdnow9c7btw4b0z0mf6bd2cyd8nv3ga3rqq1cqm"


def test_parse_page_without_entities_or_media() -> None:
    posts, next_token = x.parse_page(_load("x_posts_page2.json"))
    assert posts == [
        x.Post(
            id="1993000000000000002",
            text="チケット販売中です",
            created_at="2026-11-23T12:00:00.000Z",
            media=(),
        )
    ]
    assert next_token is None


def test_parse_page_without_data() -> None:
    assert x.parse_page(_load("x_posts_empty.json")) == ([], None)


def test_parse_page_rejects_unexpected_body() -> None:
    with pytest.raises(TypeError):
        x.parse_page([])


def test_fetch_posts_since_follows_pages_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeGet("x_posts_page1.json", "x_posts_page2.json")
    monkeypatch.setattr(requests, "get", fake_get)

    posts = x.fetch_posts_since("token", "123", "1993000000000000001")

    assert [p.id for p in posts] == [
        "1993000000000000002",
        "1993000000000000003",
        "1993000000000000004",
    ]
    assert [p.get("pagination_token") for p in fake_get.params] == [
        None,
        "7140dibdnow9c7btw4b0z0mf6bd2cyd8nv3ga3rqq1cqm",
    ]
    for params in fake_get.params:
        assert params["since_id"] == "1993000000000000001"
        assert params["exclude"] == "replies,retweets"
        assert params["expansions"] == "attachments.media_keys"


def test_fetch_latest_post_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeGet("x_posts_page1.json")
    monkeypatch.setattr(requests, "get", fake_get)
    assert x.fetch_latest_post_id("token", "123") == "1993000000000000004"
    # 基準点の ID だけ要るので、メディアの展開は要求しない
    assert "expansions" not in fake_get.params[0]


def test_fetch_latest_post_id_without_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", FakeGet("x_posts_empty.json"))
    assert x.fetch_latest_post_id("token", "123") is None
