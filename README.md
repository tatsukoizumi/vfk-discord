# vfk-discord

ヴァンフォーレ甲府関連の Discord 自動化ジョブ集（GCP Cloud Functions 2nd gen）。

| ジョブ | エントリポイント | 内容 |
|---|---|---|
| ニュース通知 | `notify_news` | 公式サイトのニュース（試合・チーム・その他）を Webhook で通知 |
| 試合日スレッド作成 | `create_match_threads` | 公式戦当日の朝にテキストチャンネルへ `9/5 山形` 形式のスレッドを作成し、初回メッセージ（大会/節・対戦カード・キックオフ・会場）を投稿 |

## 開発

[uv](https://docs.astral.sh/uv/) と Python 3.13（`mise.toml`）で管理する。

```sh
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

依存を変更したら `requirements.txt`（デプロイ用の生成物）を更新する:

```sh
uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
```

## 環境変数

| 変数 | 使うジョブ | 内容 |
|---|---|---|
| `DISCORD_WEBHOOK_URL_MATCH` | notify_news | 試合・イベントニュース用 Webhook URL |
| `DISCORD_WEBHOOK_URL_TEAM` | notify_news | チームニュース用 Webhook URL |
| `DISCORD_WEBHOOK_URL_OTHER` | notify_news | その他ニュース用 Webhook URL |
| `DISCORD_BOT_TOKEN` | create_match_threads | Bot トークン（Secret Manager 推奨） |
| `DISCORD_MATCH_CHANNEL_ID` | create_match_threads | スレッドを作るテキストチャンネル ID |
| `GOOGLE_CALENDAR_ID` | create_match_threads | `c203nq73hug1i4qvqlh52d0r32me32nv@import.calendar.google.com` |
| `GOOGLE_OAUTH_CLIENT_ID` | create_match_threads | OAuth クライアント ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | create_match_threads | OAuth クライアントシークレット（Secret Manager 推奨） |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | create_match_threads | リフレッシュトークン（Secret Manager 推奨） |

## Discord Bot の準備（試合日スレッド用）

Webhook ではテキストチャンネルにスレッドを作れないため Bot が必要。

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリと Bot を作成し、トークンを控える
2. サーバーに招待し、対象チャンネルで以下の権限を付与する:
   View Channel / Send Messages / Create Public Threads / Send Messages in Threads
3. 対象チャンネルの ID（開発者モードで右クリック → ID をコピー）を `DISCORD_MATCH_CHANNEL_ID` に設定する

## Google カレンダー認証（試合日スレッド用）

購読カレンダー（ICS インポート）はサービスアカウントと共有できないため、
ユーザー本人の OAuth リフレッシュトークンを使う。

1. GCP コンソールで OAuth クライアント（アプリケーションの種類: **デスクトップ アプリ**）を作成する
2. OAuth 同意画面を**本番環境に公開**する
   （External + Testing のままだとリフレッシュトークンが 7 日で失効する）
3. リフレッシュトークンを取得し、Secret Manager に登録する:

   ```sh
   GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
       uv run python scripts/obtain_google_token.py
   ```

注意: ICS 購読カレンダーは Google 側の更新が半日〜1 日遅れるため、
前夜のカレンダー変更は当日 08:00 の実行に反映されないことがある。

## デプロイ

プロジェクト `vfk-discord`、リージョン `asia-northeast1`。

### 自動デプロイ（GitHub Actions）

`main` への push で [.github/workflows/deploy.yml](.github/workflows/deploy.yml) が
2 つの関数を `gcloud functions deploy` で再デプロイする。
環境変数・シークレットの設定はフラグを指定しないため既存関数の値がそのまま引き継がれる
（変更したいときは下記の手動デプロイコマンドを使う）。

認証はキーレスの Workload Identity Federation を使う。初回のみ以下をセットアップする:

```sh
PROJECT_ID=vfk-discord
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
REPO=tatsukoizumi/vfk-discord

# デプロイ用サービスアカウント
gcloud iam service-accounts create github-deployer --project="$PROJECT_ID"
SA=github-deployer@$PROJECT_ID.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA" --role=roles/cloudfunctions.developer
# 関数の実行サービスアカウント（デフォルトの Compute SA）として動かす権限
gcloud iam service-accounts add-iam-policy-binding \
    "$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:$SA" --role=roles/iam.serviceAccountUser

# GitHub Actions からの OIDC 連携
gcloud iam workload-identity-pools create github \
    --project="$PROJECT_ID" --location=global
gcloud iam workload-identity-pools providers create-oidc github-actions \
    --project="$PROJECT_ID" --location=global --workload-identity-pool=github \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '$REPO'"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
    --project="$PROJECT_ID" \
    --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$REPO"
```

GitHub リポジトリの Secrets（Settings → Secrets and variables → Actions）に以下を登録する:

| Secret | 値 |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/{PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/providers/github-actions` |
| `GCP_SERVICE_ACCOUNT` | `github-deployer@vfk-discord.iam.gserviceaccount.com` |

### Secret Manager

```sh
printf '%s' "$DISCORD_BOT_TOKEN" | gcloud secrets create DISCORD_BOT_TOKEN --data-file=-
printf '%s' "$GOOGLE_OAUTH_CLIENT_SECRET" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET --data-file=-
printf '%s' "$GOOGLE_OAUTH_REFRESH_TOKEN" | gcloud secrets create GOOGLE_OAUTH_REFRESH_TOKEN --data-file=-
```

### ニュース通知（既存関数の再デプロイ）

```sh
gcloud functions deploy discord-vfk-pr \
    --gen2 \
    --region=asia-northeast1 \
    --runtime=python313 \
    --entry-point=notify_news \
    --trigger-topic=vfk-discord \
    --source=. \
    --set-env-vars="DISCORD_WEBHOOK_URL_MATCH=...,DISCORD_WEBHOOK_URL_TEAM=...,DISCORD_WEBHOOK_URL_OTHER=..."
```

既存 Scheduler `pr-notify-cloud-function-schedule`（`*/30 7-23 * * *` Asia/Tokyo）はそのまま。

### 試合日スレッド作成（新関数）

```sh
gcloud pubsub topics create vfk-match-thread

gcloud functions deploy create-match-threads \
    --gen2 \
    --region=asia-northeast1 \
    --runtime=python313 \
    --entry-point=create_match_threads \
    --trigger-topic=vfk-match-thread \
    --source=. \
    --set-env-vars="DISCORD_MATCH_CHANNEL_ID=...,GOOGLE_CALENDAR_ID=c203nq73hug1i4qvqlh52d0r32me32nv@import.calendar.google.com,GOOGLE_OAUTH_CLIENT_ID=..." \
    --set-secrets="DISCORD_BOT_TOKEN=DISCORD_BOT_TOKEN:latest,GOOGLE_OAUTH_CLIENT_SECRET=GOOGLE_OAUTH_CLIENT_SECRET:latest,GOOGLE_OAUTH_REFRESH_TOKEN=GOOGLE_OAUTH_REFRESH_TOKEN:latest"

gcloud scheduler jobs create pubsub match-thread-schedule \
    --location=asia-northeast1 \
    --schedule="0 8 * * *" \
    --time-zone="Asia/Tokyo" \
    --topic=vfk-match-thread \
    --message-body="{}"
```

### 動作確認

Pub/Sub メッセージに `{"date": "YYYY-MM-DD"}` を入れると、その日を対象に実行できる
（バックフィル・動作確認用）。無ければ JST の今日が対象になる。

```sh
gcloud pubsub topics publish vfk-match-thread --message='{"date": "2026-09-05"}'
# または
gcloud scheduler jobs run match-thread-schedule --location=asia-northeast1
```

ローカル実行:

```sh
uv run functions-framework --target create_match_threads --signature-type cloudevent
# 別ターミナルで Pub/Sub 形式の CloudEvent を送る（data は base64 の {"date": "2026-09-05"}）
curl localhost:8080 -X POST \
    -H "Content-Type: application/json" \
    -H "ce-id: test" -H "ce-source: test" -H "ce-type: google.cloud.pubsub.topic.v1.messagePublished" \
    -H "ce-specversion: 1.0" \
    -d '{"message": {"data": "eyJkYXRlIjogIjIwMjYtMDktMDUifQ=="}}'
```

## 冪等性

作成済みスレッドは Firestore コレクション `match_threads`
（ドキュメント ID = `{YYYY-MM-DD}_{対戦相手}`）に記録し、存在すればスキップする。
再実行・同日複数回の起動でもスレッドは重複しない。
ニュース通知は従来どおり `latest_news_id` コレクションで最新 ID を管理する。
