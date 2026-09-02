import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """環境変数から読む設定。未設定の値は空文字列（ジョブごとに必要な変数のみ設定すればよい）。"""

    discord_webhook_url_match: str
    discord_webhook_url_team: str
    discord_webhook_url_other: str
    discord_bot_token: str
    discord_match_channel_id: str
    google_calendar_id: str
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_refresh_token: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            discord_webhook_url_match=os.environ.get("DISCORD_WEBHOOK_URL_MATCH", ""),
            discord_webhook_url_team=os.environ.get("DISCORD_WEBHOOK_URL_TEAM", ""),
            discord_webhook_url_other=os.environ.get("DISCORD_WEBHOOK_URL_OTHER", ""),
            discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
            discord_match_channel_id=os.environ.get("DISCORD_MATCH_CHANNEL_ID", ""),
            google_calendar_id=os.environ.get("GOOGLE_CALENDAR_ID", ""),
            google_oauth_client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            google_oauth_client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            google_oauth_refresh_token=os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", ""),
        )
