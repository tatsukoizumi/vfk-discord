"""Google Calendar 読み取り用のリフレッシュトークンをローカルで一回だけ取得するスクリプト。

使い方:
    GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
        uv run python scripts/obtain_google_token.py

GCP コンソールで「デスクトップ アプリ」型の OAuth クライアントを作成しておくこと。
ブラウザが開くので、カレンダーを購読している Google アカウントで承認する。
表示されたリフレッシュトークンを Secret Manager の GOOGLE_OAUTH_REFRESH_TOKEN に登録する。
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events.readonly"]


def main() -> None:
    client_config = {
        "installed": {
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # prompt="consent" + offline でリフレッシュトークンを必ず発行させる
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    print("refresh_token:")
    print(credentials.refresh_token)


if __name__ == "__main__":
    main()
