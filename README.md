# vfk-discord

ヴァンフォーレ甲府関連の Discord 自動化ジョブ集（GCP Cloud Functions 2nd gen）。

| ジョブ | エントリポイント | 内容 |
|---|---|---|
| ニュース通知 | `notify_news` | 公式サイトのニュース（試合・チーム・その他）を Webhook で通知 |
| 試合日スレッド作成 | `create_match_threads` | 公式戦当日の朝にテキストチャンネルへ `9/5 山形` 形式のスレッドを作成し、初回メッセージ（大会/節・対戦カード・キックオフ・会場）を投稿 |
| X 投稿通知 | `notify_x_posts` | 公式 X アカウント（[@vfk_official](https://x.com/vfk_official)）の新しい投稿を本文・画像付きの embed にして Webhook で送る（返信・リポストは除外、引用は送る） |

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
| `MATCH_CALENDAR_ICS_URL` | create_match_threads | 試合日程の ICS（`https://www.jleague.jp/api/club-calendar/kofu/`） |
| `X_BEARER_TOKEN` | notify_x_posts | X API の Bearer Token（Secret Manager） |
| `X_USER_ID` | notify_x_posts | @vfk_official の user ID（数値） |
| `DISCORD_WEBHOOK_URL_X` | notify_x_posts | X 投稿用 Webhook URL（Secret Manager） |

## Discord Bot の準備（試合日スレッド用）

Webhook ではテキストチャンネルにスレッドを作れないため Bot が必要。

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリと Bot を作成し、トークンを控える
2. サーバーに招待し、対象チャンネルで以下の権限を付与する:
   View Channel / Send Messages / Create Public Threads / Send Messages in Threads
3. 対象チャンネルの ID（開発者モードで右クリック → ID をコピー）を `DISCORD_MATCH_CHANNEL_ID` に設定する

## 試合日程の取得元

J リーグ公式のクラブ別カレンダー（ICS）を取得する。
件名は `[Ｊ２]:[A]VS今治 [キックオフ時間]14:05` の形式で、節の情報は含まれない。
会場は `アシさと` のような略称、キックオフ未定の試合は終日イベントになる。

`year` クエリを省略すると現在のシーズンが返る（`?year=2025` などで過去シーズンも取得できる）。
2026-27 シーズンは 2027 年 5 月まで。次シーズンの日程公開後に、省略時の返却が切り替わっているか確認する。

## デプロイ

プロジェクト `vfk-discord`、リージョン `asia-northeast1`。

### 自動デプロイ（GitHub Actions）

`main` への push で [.github/workflows/deploy.yml](.github/workflows/deploy.yml) が
各関数を `gcloud functions deploy` で再デプロイする。
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
    --set-env-vars="DISCORD_MATCH_CHANNEL_ID=...,MATCH_CALENDAR_ICS_URL=https://www.jleague.jp/api/club-calendar/kofu/" \
    --set-secrets="DISCORD_BOT_TOKEN=DISCORD_BOT_TOKEN:latest"

gcloud scheduler jobs create pubsub match-thread-schedule \
    --location=asia-northeast1 \
    --schedule="0 8 * * *" \
    --time-zone="Asia/Tokyo" \
    --topic=vfk-match-thread \
    --message-body="{}"
```

### X 投稿通知（新関数）

X API は従量課金で、他アカウントの投稿は1件 $0.005。同じ投稿は UTC の同じ日のうちなら再課金されない。
課金は返った投稿数に比例するので、ポーリング間隔を縮めても費用はほぼ増えない。1日20投稿なら月 $3 前後になる。
画像を出すために `expansions=attachments.media_keys` でメディアも取得している。
[料金表](https://docs.x.com/x-api/getting-started/pricing)に Media の項目は無いが、「返ったリソースごとに課金」とも書かれていて、メディアが別に数えられるかは明記されていない。
仮にメディアも Post と同額だとすると、1投稿に画像2枚が平均なら月 $9 前後になる。運用開始後に Developer Console の利用量で確かめる。
投稿者のユーザー情報は展開しない（User read は $0.01/件 かかるため、名前とアイコンは固定値を使う）。

1. [X Developer Console](https://console.x.com) でアプリを作り、クレジットを購入する。
   請求設定で課金サイクルごとの支出上限（例: $10）を設定しておく（上限に達するとリクエストがブロックされる）
2. アプリの Bearer Token を発行する
3. user ID を調べる（1回だけ。User read として $0.01 かかる）:

   ```sh
   curl -s -H "Authorization: Bearer $X_BEARER_TOKEN" \
       https://api.x.com/2/users/by/username/vfk_official
   # {"data":{"id":"<この値を X_USER_ID に使う>", ...}}
   ```

4. 通知先チャンネルで Webhook を作る
5. Secret Manager に登録し、関数の実行サービスアカウントに読み取り権限を付ける:

   ```sh
   PROJECT_NUMBER=$(gcloud projects describe vfk-discord --format='value(projectNumber)')
   printf '%s' "$X_BEARER_TOKEN" | gcloud secrets create X_BEARER_TOKEN --data-file=-
   printf '%s' "$DISCORD_WEBHOOK_URL_X" | gcloud secrets create DISCORD_WEBHOOK_URL_X --data-file=-
   for name in X_BEARER_TOKEN DISCORD_WEBHOOK_URL_X; do
       gcloud secrets add-iam-policy-binding "$name" \
           --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
           --role=roles/secretmanager.secretAccessor
   done
   ```

6. トピック・関数・Scheduler を作る。GitHub Actions は既存関数の設定を引き継ぐだけなので、
   このデプロイは main へのマージより前に済ませる（先にマージすると secrets の無い関数が作られる）:

   ```sh
   gcloud pubsub topics create vfk-x-posts

   # 実行が重なると同じ投稿を二重に送るので 1 インスタンスに制限する
   gcloud functions deploy notify-x-posts \
       --gen2 \
       --region=asia-northeast1 \
       --runtime=python313 \
       --entry-point=notify_x_posts \
       --trigger-topic=vfk-x-posts \
       --source=. \
       --max-instances=1 \
       --set-env-vars="X_USER_ID=..." \
       --set-secrets="X_BEARER_TOKEN=X_BEARER_TOKEN:latest,DISCORD_WEBHOOK_URL_X=DISCORD_WEBHOOK_URL_X:latest"

   gcloud scheduler jobs create pubsub x-posts-schedule \
       --location=asia-northeast1 \
       --schedule="*/5 * * * *" \
       --time-zone="Asia/Tokyo" \
       --topic=vfk-x-posts \
       --message-body="{}"
   ```

初回の実行は最新の投稿 ID を記録するだけで、Discord には送らない（過去の投稿が流れ込まないように）。
2回目以降は、その ID より新しい投稿を古い順に送る。

Discord への表示:

- 1投稿は1メッセージになる。embed には本文、投稿日時、投稿へのリンク（投稿者名がリンクになる）を入れる。本文の t.co は展開先の URL に置き換え、添付メディアを指す t.co は消す
- 画像は最大4枚。同じ `url` を持つ embed を並べると、Discord が1つのギャラリーにまとめて表示する
- 動画と GIF は再生できないので、プレビュー画像をサムネイルにし、本文の末尾に投稿へのリンクを付ける
- 引用投稿は、引用した側の本文とリンクだけを出す。引用元の内容は展開しない（引用元を取得すると Post read が増えるため）。引用元が本文中の URL として含まれていれば、そのリンクとして残る
- 280字を超える長文投稿は、API の `text` に入っている範囲だけを出す。続きは投稿へのリンクから読む

ポーリング間隔は Scheduler の設定だけで変えられる:

```sh
gcloud scheduler jobs update pubsub x-posts-schedule \
    --location=asia-northeast1 --schedule="* * * * *"
```

通知先チャンネルを変えるときは、`DISCORD_WEBHOOK_URL_X` に新しいバージョンを追加する
（`gcloud secrets versions add DISCORD_WEBHOOK_URL_X --data-file=-`）。関数は `:latest` を参照しているので、次のコールドスタートから反映される。

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
X 投稿通知は `x_latest_post_id` コレクション（ドキュメント ID = user ID）に送信済みの最新投稿 ID を
1件送るたびに保存する。送信に失敗したら次回はその投稿から再開する。
