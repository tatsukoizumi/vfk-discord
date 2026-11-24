import pytest

from vfk_discord import discord, x, x_posts
from vfk_discord.config import Settings
from vfk_discord.store import Store

USER_ID = "123"
WEBHOOK_URL = "https://discord.com/api/webhooks/1/abc"

SETTINGS = Settings(
    discord_webhook_url_match="",
    discord_webhook_url_team="",
    discord_webhook_url_other="",
    discord_bot_token="",
    discord_match_channel_id="",
    match_calendar_ics_url="",
    x_bearer_token="token",
    x_user_id=USER_ID,
    discord_webhook_url_x=WEBHOOK_URL,
)


class FakeStore(Store):
    def __init__(self, latest_x_post_id: str = "") -> None:
        self.latest_x_post_id = latest_x_post_id

    def get_latest_x_post_id(self, user_id: str) -> str:
        assert user_id == USER_ID
        return self.latest_x_post_id

    def set_latest_x_post_id(self, user_id: str, post_id: str) -> None:
        assert user_id == USER_ID
        self.latest_x_post_id = post_id


class FakeWebhook:
    def __init__(self, fail_on: str | None = None) -> None:
        self.sent: list[str] = []
        self._fail_on = fail_on

    def __call__(self, webhook_url: str, content: str) -> None:
        assert webhook_url == WEBHOOK_URL
        if self._fail_on is not None and content.endswith(self._fail_on):
            raise RuntimeError("webhook failed")
        self.sent.append(content)


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    latest: str | None = None,
    since: list[str] | None = None,
    webhook: FakeWebhook | None = None,
) -> FakeWebhook:
    webhook = webhook or FakeWebhook()
    monkeypatch.setattr(x, "fetch_latest_post_id", lambda token, user_id: latest)
    monkeypatch.setattr(x, "fetch_post_ids_since", lambda token, user_id, since_id: since or [])
    monkeypatch.setattr(discord, "send_webhook_message", webhook)
    return webhook


def test_first_run_records_latest_without_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    webhook = _patch(monkeypatch, latest="100")
    store = FakeStore()

    x_posts.run(SETTINGS, store)

    assert store.latest_x_post_id == "100"
    assert webhook.sent == []


def test_first_run_without_posts_keeps_store_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, latest=None)
    store = FakeStore()

    x_posts.run(SETTINGS, store)

    assert store.latest_x_post_id == ""


def test_sends_new_posts_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    webhook = _patch(monkeypatch, since=["101", "102"])
    store = FakeStore("100")

    x_posts.run(SETTINGS, store)

    assert webhook.sent == [
        "https://x.com/vfk_official/status/101",
        "https://x.com/vfk_official/status/102",
    ]
    assert store.latest_x_post_id == "102"


def test_failed_send_keeps_last_sent_id(monkeypatch: pytest.MonkeyPatch) -> None:
    webhook = _patch(monkeypatch, since=["101", "102", "103"], webhook=FakeWebhook(fail_on="102"))
    store = FakeStore("100")

    with pytest.raises(RuntimeError):
        x_posts.run(SETTINGS, store)

    assert webhook.sent == ["https://x.com/vfk_official/status/101"]
    assert store.latest_x_post_id == "101"
