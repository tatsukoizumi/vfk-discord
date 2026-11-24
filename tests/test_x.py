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
    ids, next_token = x.parse_page(_load("x_posts_page1.json"))
    assert ids == ["1993000000000000004", "1993000000000000003"]
    assert next_token == "7140dibdnow9c7btw4b0z0mf6bd2cyd8nv3ga3rqq1cqm"


def test_parse_page_without_data() -> None:
    assert x.parse_page(_load("x_posts_empty.json")) == ([], None)


def test_parse_page_rejects_unexpected_body() -> None:
    with pytest.raises(TypeError):
        x.parse_page([])


def test_fetch_post_ids_since_follows_pages_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeGet("x_posts_page1.json", "x_posts_page2.json")
    monkeypatch.setattr(requests, "get", fake_get)

    ids = x.fetch_post_ids_since("token", "123", "1993000000000000001")

    assert ids == ["1993000000000000002", "1993000000000000003", "1993000000000000004"]
    assert [p.get("pagination_token") for p in fake_get.params] == [
        None,
        "7140dibdnow9c7btw4b0z0mf6bd2cyd8nv3ga3rqq1cqm",
    ]
    assert all(p["since_id"] == "1993000000000000001" for p in fake_get.params)
    assert all(p["exclude"] == "replies,retweets" for p in fake_get.params)


def test_fetch_latest_post_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", FakeGet("x_posts_page1.json"))
    assert x.fetch_latest_post_id("token", "123") == "1993000000000000004"


def test_fetch_latest_post_id_without_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", FakeGet("x_posts_empty.json"))
    assert x.fetch_latest_post_id("token", "123") is None
