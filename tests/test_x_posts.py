import pytest

from vfk_discord import discord, x, x_posts
from vfk_discord.config import Settings
from vfk_discord.news import LOGO_URL
from vfk_discord.store import Store

USER_ID = "123"
WEBHOOK_URL = "https://discord.com/api/webhooks/1/abc"
POST_URL = "https://x.com/vfk_official/status/101"

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


def _photo(name: str) -> x.Media:
    return x.Media(
        type="photo", url=f"https://pbs.twimg.com/media/{name}.jpg", preview_image_url=None
    )


def _post(post_id: str = "101", text: str = "本文", media: tuple[x.Media, ...] = ()) -> x.Post:
    return x.Post(id=post_id, text=text, created_at="2026-11-24T03:00:00.000Z", media=media)


class TestBuildEmbeds:
    def test_text_only(self) -> None:
        assert x_posts.build_embeds(_post()) == [
            {
                "author": {
                    "name": "ヴァンフォーレ甲府 (@vfk_official)",
                    "url": POST_URL,
                    "icon_url": LOGO_URL,
                },
                "url": POST_URL,
                "description": "本文",
                "timestamp": "2026-11-24T03:00:00.000Z",
            }
        ]

    def test_photos_become_gallery_up_to_four(self) -> None:
        photos = tuple(_photo(f"p{i}") for i in range(5))
        embeds = x_posts.build_embeds(_post(media=photos))

        assert len(embeds) == 4
        assert {e["url"] for e in embeds} == {POST_URL}
        assert [e["image"] for e in embeds] == [
            {"url": f"https://pbs.twimg.com/media/p{i}.jpg"} for i in range(4)
        ]
        assert embeds[0]["description"] == "本文"
        assert all("description" not in e for e in embeds[1:])

    @pytest.mark.parametrize("media_type", ["video", "animated_gif"])
    def test_video_uses_preview_as_thumbnail(self, media_type: str) -> None:
        video = x.Media(type=media_type, url=None, preview_image_url="https://pbs.twimg.com/v.jpg")
        [embed] = x_posts.build_embeds(_post(media=(video,)))

        assert embed["thumbnail"] == {"url": "https://pbs.twimg.com/v.jpg"}
        assert "image" not in embed
        assert embed["description"] == f"本文\n\n▶ [動画・GIF を X で見る]({POST_URL})"

    def test_media_only_post_has_no_description(self) -> None:
        [embed] = x_posts.build_embeds(_post(text="", media=(_photo("p0"),)))
        assert "description" not in embed

    def test_long_text_is_truncated(self) -> None:
        [embed] = x_posts.build_embeds(_post(text="あ" * 5000))
        assert embed["description"] == "あ" * 4096


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

    def __call__(self, webhook_url: str, embeds: list[dict[str, object]]) -> None:
        assert webhook_url == WEBHOOK_URL
        url = str(embeds[0]["url"])
        if self._fail_on is not None and url.endswith(self._fail_on):
            raise RuntimeError("webhook failed")
        self.sent.append(url.rsplit("/", 1)[-1])


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    latest: str | None = None,
    since: list[str] | None = None,
    webhook: FakeWebhook | None = None,
) -> FakeWebhook:
    webhook = webhook or FakeWebhook()
    posts = [_post(post_id) for post_id in since or []]
    monkeypatch.setattr(x, "fetch_latest_post_id", lambda token, user_id: latest)
    monkeypatch.setattr(x, "fetch_posts_since", lambda token, user_id, since_id: posts)
    monkeypatch.setattr(discord, "send_webhook_embeds", webhook)
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

    assert webhook.sent == ["101", "102"]
    assert store.latest_x_post_id == "102"


def test_failed_send_keeps_last_sent_id(monkeypatch: pytest.MonkeyPatch) -> None:
    webhook = _patch(monkeypatch, since=["101", "102", "103"], webhook=FakeWebhook(fail_on="102"))
    store = FakeStore("100")

    with pytest.raises(RuntimeError):
        x_posts.run(SETTINGS, store)

    assert webhook.sent == ["101"]
    assert store.latest_x_post_id == "101"
