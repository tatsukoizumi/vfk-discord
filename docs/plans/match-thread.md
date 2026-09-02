# 試合日スレッド自動作成 + 複数ジョブ前提のリファクタ

## Context

ヴァンフォーレ甲府の公式戦当日に、Discord の特定テキストチャンネルへ `9/5 山形` / `9/2 FC大阪（ルヴァン）` 形式のスレッドを自動作成したい。試合データは Google カレンダー「甲府 全試合」（ICS 購読、`c203nq73hug1i4qvqlh52d0r32me32nv@import.calendar.google.com`）を Calendar API で読む。

既存リポジトリは単一の Cloud Function（ニュース通知）で、テスト・lint なし、`requirements.txt` 直書き、`print` ログ、import 時に Firestore クライアント生成、`-> [dict]` 注釈がある。ユーザー決定: **複数処理がある前提で全体をリファクタ**し、uv / Ruff / mypy / pytest のグローバル規約に合わせる。

### 現在のデプロイ状況（gcloud で確認済み）

- GCP プロジェクト `vfk-discord`、リージョン `asia-northeast1`
- 関数 `discord-vfk-pr`: 2nd gen、runtime `python39`、entry point `main`、Pub/Sub トピック `vfk-discord`
- Cloud Scheduler `pr-notify-cloud-function-schedule`: `*/30 7-23 * * *` (Asia/Tokyo)
- 環境変数 `DISCORD_WEBHOOK_URL_{MATCH,TEAM,OTHER}` は平文 env var

### カレンダーのイベント形式（実データで確認済み）

| フィールド | 試合前 | 試合後 |
|---|---|---|
| summary | `J2 山形-甲府` / `JC FC大阪-甲府` / `天皇杯 鹿島-甲府` / `TM 浦和-甲府` / `PSM 松本-甲府` | `J2 鳥栖 2-0 甲府` |
| description | `J2 第5節` / `Jリーグカップ 1stラウンド 第1節` / `天皇杯 3回戦 ` / `練習試合` / `プレシーズンマッチ` | 同左 |
| location | スタジアム名（TM は欠けることあり） | |
| start | `dateTime` +09:00（一部 TM は終日 `date`） | |

ホームが先、アウェイが後。`J2・J3百年構想` のような空白を含まない長い接頭辞もある。

## ユーザー決定事項

- データ取得: Google Calendar API（ICS 直接取得ではない）
- 実行タイミング: 試合日の朝定時（Cloud Scheduler、08:00 JST）
- スレッド作成時に初回メッセージ（キックオフ時刻・会場・大会/節）を投稿する
- 同一リポジトリで複数ジョブを持つ構成に全体リファクタ

## 設計

### タイトル生成ルール（`vfk_discord/match.py`）

summary を最初の空白で `prefix, rest` に分割して分類する。

| 接頭辞 | 扱い | タイトル |
|---|---|---|
| `J1` `J2` `J3` | リーグ戦 | `M/D 対戦相手` |
| `JC` | カップ戦 | `M/D 対戦相手（ルヴァン）` |
| `天皇杯` | カップ戦 | `M/D 対戦相手（天皇杯）` |
| `TM` `PSM` | 非公式戦 | スキップ（None） |
| その他 | カップ戦扱い | `M/D 対戦相手（接頭辞そのまま）` 例 `（J2・J3百年構想）` |

- `rest` が 3 トークン（`鳥栖 2-0 甲府`）なら試合後形式、そうでなければ `-`（全角・ハイフン類を正規化）で分割。対戦相手は `甲府` でない側
- 日付はイベント開始の JST 日付、ゼロ埋めなし、全角カッコ
- 終日イベントはキックオフ「未定」
- Calendar API のレスポンスは `TypedDict` で受け、`match.py` で即座に `Match` dataclass（date, kickoff, prefix, home, away, opponent, round_label, venue）に変換する

### 認証（Google Calendar、`vfk_discord/gcal.py`）

購読カレンダーはサービスアカウントと共有できないため、ユーザー本人の OAuth リフレッシュトークンを使う。

- `scripts/obtain_google_token.py`（ローカル一回実行、dev 依存 `google-auth-oauthlib`、Desktop アプリ型クライアント、`prompt="consent"` + offline）で scope `https://www.googleapis.com/auth/calendar.events.readonly` のリフレッシュトークンを取得
- 関数側は `google-auth` を使わず、`requests.post("https://oauth2.googleapis.com/token", grant_type=refresh_token)` でアクセストークンを取り、`Authorization: Bearer` で `events.list` を GET する（mypy の google 系型問題を回避）
- `events.list` パラメータ: `timeMin`/`timeMax` = JST 当日 `00:00:00+09:00` 〜 翌日、`singleEvents=true`、`orderBy=startTime`、`timeZone=Asia/Tokyo`（終日イベントの範囲判定に必要）。calendarId は `urllib.parse.quote(..., safe="")`
- 注意（README に記載）: OAuth 同意画面が External + Testing のままだとリフレッシュトークンが 7 日で失効する。「本番環境」に公開する。ICS 購読カレンダーは Google 側の更新が半日〜1 日遅れるため、前夜の変更は 08:00 に反映されないことがある

### Discord（`vfk_discord/discord.py`）

Bot トークンで REST を直接叩く（`Authorization: Bot ...`、`User-Agent` 付与、gateway 不要）。Webhook ではテキストチャンネルにスレッドを作れないため Bot が必須。

1. `POST /channels/{channel_id}/threads` で `{"name": タイトル, "type": 11, "auto_archive_duration": 4320}`（type 明示必須、name ≤ 100 文字）
2. `POST /channels/{thread_id}/messages` で初回メッセージ（大会/節、対戦カード、キックオフ時刻、会場）を投稿

先にスレッドを作ることで、途中失敗→再実行時にチャンネルへ孤児メッセージが残らない。必要な Bot 権限: View Channel / Send Messages / Create Public Threads / Send Messages in Threads。

既存の Webhook 送信も同モジュールに `send_webhook_embed()` として `requests.post` 1 本で実装し、`dhooks` を外す。Embed の見た目（author=ヴァンフォーレ甲府公式、ロゴ、タイトルリンク、サムネイル）は維持。

### 冪等性（`vfk_discord/store.py`）

Firestore コレクション `match_threads`、ドキュメント ID = `{YYYY-MM-DD}_{対戦相手}`（ICS 由来のイベント ID は再生成されうるため使わない）。スレッド作成成功後に書き込む。存在すればスキップ。既存の `latest_news_id` コレクションは維持。Firestore クライアントは import 時ではなく `Store` 生成時に作る（テストで ADC 不要）。

### リポジトリ構成

```
pyproject.toml              uv 管理、requires-python >=3.13、[build-system] なし
                            ruff: line-length 100, extend-select ["I"]
                            mypy: strict 相当 + [[overrides]] module google.* ignore_missing_imports
                            pytest: pythonpath ["."]
uv.lock
mise.toml                   python 3.13
.gitignore / .gcloudignore  (.venv, tests, scripts, .git を除外)
requirements.txt            `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt` の生成物
main.py                     functions_framework エントリポイント 2 つ: notify_news / create_match_threads
vfk_discord/
  __init__.py
  config.py                 Settings.from_env()（frozen dataclass）
  discord.py                send_webhook_embed / create_thread / post_message
  store.py                  Store: latest_news_id get/set, match_thread exists/mark
  news.py                   parse_news_html()（純関数）+ run(settings, store)
  gcal.py                   get_access_token() / list_events(date) -> list[CalendarEvent]
  match.py                  Match dataclass, parse_event() / thread_title() / opening_message()
  match_threads.py          run(settings, store, date)
scripts/obtain_google_token.py
tests/
  test_match.py             全 summary 形状・スコア形式・終日・TM/PSM スキップ・未知接頭辞
  test_news.py              tests/fixtures/news_match.html のパース
  test_gcal.py              JST 日付範囲の計算
README.md                   環境変数、OAuth 手順、デプロイ・Scheduler コマンド
```

- `create_match_threads` は Pub/Sub メッセージに `{"date": "YYYY-MM-DD"}` があればその日を対象にする（バックフィル・動作確認用）。無ければ `datetime.now(ZoneInfo("Asia/Tokyo"))` の日付
- `print` → `logging`。`cloudevents.http.CloudEvent` はエントリポイントの型注釈に使うため依存に残す
- 依存: `requests` `beautifulsoup4>=4.13`（inline 型あり）`google-cloud-firestore` `functions-framework` `cloudevents`。dev: `ruff` `mypy` `pytest` `types-requests` `google-auth-oauthlib`
- コミットは英語、ブランチを切って作業（main 直コミット禁止）

### デプロイ（README に記載、実行はユーザー）

- 既存関数 `discord-vfk-pr` を `--gen2 --runtime=python313 --entry-point=notify_news --trigger-topic=vfk-discord --source=.` で再デプロイ
- 新関数 `create-match-threads`: `--entry-point=create_match_threads --trigger-topic=vfk-match-thread`、Scheduler `--schedule="0 8 * * *" --time-zone="Asia/Tokyo"`
- Secret Manager（`--set-secrets`）: `DISCORD_BOT_TOKEN` / `GOOGLE_OAUTH_CLIENT_SECRET` / `GOOGLE_OAUTH_REFRESH_TOKEN`。env: `DISCORD_MATCH_CHANNEL_ID` / `GOOGLE_CALENDAR_ID` / `GOOGLE_OAUTH_CLIENT_ID` / 既存 Webhook URL 3 つ

## 実装手順

1. ブランチ作成
2. `mise.toml` / `pyproject.toml` / `.gitignore` / `.gcloudignore` 作成、`uv lock`、`requirements.txt` を生成物に置換
3. `config.py` / `store.py`（Firestore 遅延生成）
4. `news.py` + `discord.py` の Webhook 関数に既存ロジックを移植、`tests/test_news.py`
5. `match.py` を `tests/test_match.py` 先行で実装
6. `gcal.py` + `tests/test_gcal.py`、`discord.py` の Bot 関数、`match_threads.py`
7. `main.py` 書き直し、`scripts/obtain_google_token.py`、README
8. `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` を通す

## 検証

- 単体テスト: `J2 山形-甲府`→`9/5 山形`、`JC FC大阪-甲府`→`9/2 FC大阪（ルヴァン）`、`天皇杯 鹿島-甲府`→`9/23 鹿島（天皇杯）`、`J2 鳥栖 2-0 甲府`→対戦相手 `鳥栖`、`J2・J3百年構想 甲府-福島`→`2/7 福島（J2・J3百年構想）`、`TM ...`→None、終日→キックオフ未定
- ローカル実行: `uv run functions-framework --target create_match_threads` に `{"date": "2026-09-05"}` を含む Pub/Sub 形式 CloudEvent を curl で送る。テスト用チャンネル ID を env に指定し、スレッドと初回メッセージ、Firestore `match_threads/2026-09-05_山形` の作成を確認。同じリクエストの 2 回目でスキップされること
- ニュース通知のリグレッション: `notify_news` をローカル起動し、Firestore の最新 ID と比較して送信内容・Embed の見た目が変わらないこと
- デプロイ後: `gcloud scheduler jobs run` で手動発火して同様に確認

## ユーザー作業（コード外）

- Discord Bot アプリの作成・サーバー招待とチャンネル ID の取得
- GCP で OAuth クライアント（Desktop）作成と同意画面の本番公開、`scripts/obtain_google_token.py` の実行
- Secret Manager への登録と 2 関数のデプロイ、Scheduler 作成
