# Architecture

## 全体像

このアプリは、デジタル商品を販売するための最小構成ストアです。静的HTMLのフロントエンド、FastAPIのバックエンド、SQLiteの永続化、Stripe Checkoutの決済導線で構成しています。

```mermaid
flowchart TD
  Buyer[購入者] -->|商品を見る| Static[静的HTML/CSS/JS]
  Static -->|GET /api/products| API[FastAPI API]
  Static -->|POST /api/checkout| API
  API -->|商品・注文| DB[(SQLite)]
  API -->|Checkout Session| Stripe[Stripe Checkout]
  Stripe -->|checkout.session.completed| Webhook[/api/stripe/webhook]
  Webhook --> DB
  Admin[運営者] -->|CSV取得| Export[/api/admin/orders.csv]
  Export --> DB
  GitHubActions[GitHub Actions] -->|pytest / ruff / CSV artifact| Repo[Repository]
```

## ユーザー入力

- 購入者メールアドレス
- 商品ID
- Stripe Webhookイベント
- 管理CSV取得時の `x-admin-api-key`

## フロントエンド

`app/static` 配下の静的ファイルで構成しています。`/api/products` から商品一覧を取得し、購入フォームから `/api/checkout` にPOSTします。

## バックエンド

FastAPIがAPIと静的ファイル配信を担当します。Stripeが未設定の場合はデモ決済URLを返すため、初期状態でもE2Eの購入体験を確認できます。

## DB

SQLiteを使用します。テーブルは `products` と `orders` の2つです。本番では `STORE_DB_PATH` を永続ディスクへ向けてください。

## CI/CD

GitHub Actionsで以下を実行します。

1. Pythonセットアップ
2. 依存関係インストール
3. `ruff check .`
4. `pytest -q`
5. 注文CSV artifact生成
6. `sales-export` artifactアップロード

## Secrets

実値はGitHubにコミットしません。必要なSecret名は以下です。

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `PUBLIC_BASE_URL`
- `STORE_DB_PATH`
- `ADMIN_API_KEY`

## 今後の拡張案

- 管理画面からの商品追加
- 署名付きダウンロードURL
- メール送信連携
- クーポンコード
- Google Analytics / Search Console連携
- Stripe Customer Portal
- PostgreSQLへの移行
