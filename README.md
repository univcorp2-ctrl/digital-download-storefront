# Digital Download Storefront

デジタル商品をすぐ販売できる、Stripe連携対応の軽量ストアです。PDF、テンプレート、画像素材、ノウハウ資料、Notionテンプレートなどを商品として登録し、購入導線と注文記録をまとめて扱えます。

> 収益を保証するものではありません。実際の売上には商品品質、集客、価格設定、法務・税務対応、決済審査などが必要です。

## できること

- 商品一覧ページを自動表示
- SQLiteで商品と注文を管理
- Stripe Checkoutへ接続可能
- Stripe未設定でもローカルのデモ決済で動作確認可能
- 注文CSVをGitHub Actions artifactとして出力
- Codespaces / devcontainer 対応
- pytest と ruff のCI付き

## すぐ動かす

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

ブラウザで `http://127.0.0.1:8000` を開きます。

## 本番運用に必要なもの

最低限、以下を準備してください。

| 用途 | 環境変数 / Secret | 説明 |
| --- | --- | --- |
| 公開URL | `PUBLIC_BASE_URL` | 例: `https://your-domain.example` |
| Stripe秘密鍵 | `STRIPE_SECRET_KEY` | Stripe Checkout作成に使用 |
| Stripe Webhook署名 | `STRIPE_WEBHOOK_SECRET` | 決済完了通知の検証に使用 |
| DB保存先 | `STORE_DB_PATH` | 例: `/data/store.db` |
| 管理用キー | `ADMIN_API_KEY` | 注文CSVの管理APIを保護 |

Secretsの実値はGitHubやREADMEに書かず、ホスティングサービス側のSecret機能に登録してください。

## 商品を追加する

`data/products.sample.json` を参考に、SQLiteへ商品を登録します。初回起動時はサンプル商品が自動投入されます。

```bash
python scripts/seed_sample.py
```

各商品の `file_url` には、購入後に渡すダウンロードURLを入れます。本番では署名付きURLや会員認証を組み合わせるのがおすすめです。

## Stripe連携

`STRIPE_SECRET_KEY` と `PUBLIC_BASE_URL` を設定すると、購入ボタンはStripe Checkout URLを返します。決済完了後はStripe Webhookが `/api/stripe/webhook` を呼び、注文ステータスを `paid` に更新します。

ローカル・CIではStripe未設定のため、デモ決済URLに遷移します。

## 注文CSVを出力する

ローカルでは以下で出力できます。

```bash
python scripts/export_orders.py --output artifacts/orders.csv
```

GitHub Actionsの `workflow_dispatch` でもCSV artifactを取得できます。

## API

| Method | Path | 説明 |
| --- | --- | --- |
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/products` | 商品一覧 |
| POST | `/api/checkout` | 決済セッション作成 |
| POST | `/api/orders/{order_id}/confirm-demo` | デモ決済完了 |
| GET | `/api/orders/{order_id}` | 注文確認 |
| GET | `/api/admin/orders.csv` | 注文CSV出力。`x-admin-api-key` が必要 |
| POST | `/api/stripe/webhook` | Stripe決済完了Webhook |

## 開発

```bash
ruff check .
pytest -q
```

## アーキテクチャ

詳細は [docs/architecture.md](docs/architecture.md) を参照してください。

```mermaid
flowchart LR
  Buyer[購入者] --> Frontend[静的ストア画面]
  Frontend --> API[FastAPI]
  API --> DB[(SQLite)]
  API --> Stripe[Stripe Checkout]
  Stripe --> Webhook[/api/stripe/webhook]
  Webhook --> DB
  API --> CSV[注文CSV]
```
