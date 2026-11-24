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
    match_calendar_ics_url: str
    x_bearer_token: str
    x_user_id: str
    discord_webhook_url_x: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            discord_webhook_url_match=os.environ.get("DISCORD_WEBHOOK_URL_MATCH", ""),
            discord_webhook_url_team=os.environ.get("DISCORD_WEBHOOK_URL_TEAM", ""),
            discord_webhook_url_other=os.environ.get("DISCORD_WEBHOOK_URL_OTHER", ""),
            discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
            discord_match_channel_id=os.environ.get("DISCORD_MATCH_CHANNEL_ID", ""),
            match_calendar_ics_url=os.environ.get("MATCH_CALENDAR_ICS_URL", ""),
            x_bearer_token=os.environ.get("X_BEARER_TOKEN", ""),
            x_user_id=os.environ.get("X_USER_ID", ""),
            discord_webhook_url_x=os.environ.get("DISCORD_WEBHOOK_URL_X", ""),
        )
