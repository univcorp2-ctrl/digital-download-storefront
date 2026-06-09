# Setup Guide

## 1. ローカル起動

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python scripts/seed_sample.py
uvicorn app.main:app --reload
```

`http://127.0.0.1:8000` を開きます。

## 2. 商品を自分の商品に差し替える

`data/products.sample.json` を編集します。

```json
{
  "id": "my-ebook",
  "name": "自分の電子書籍",
  "description": "購入したくなる説明文",
  "price_cents": 1980,
  "currency": "jpy",
  "file_url": "https://example.com/your-download.pdf",
  "active": true
}
```

編集後に以下を実行します。

```bash
python scripts/seed_sample.py
```

## 3. Stripeを使う

ホスティング先で以下の環境変数を設定します。

```bash
PUBLIC_BASE_URL=https://your-domain.example
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
ADMIN_API_KEY=long-random-admin-key
STORE_DB_PATH=/data/store.db
```

`STRIPE_SECRET_KEY` と `STRIPE_WEBHOOK_SECRET` の実値はコードやREADMEへ書かないでください。

Stripe側のWebhook URLは次にします。

```text
https://your-domain.example/api/stripe/webhook
```

購読イベントではなく、まずは `checkout.session.completed` を送れば注文を `paid` に更新できます。

## 4. デプロイ候補

FastAPIが動作し、SQLite用の永続ディスクを設定できる環境を使います。

- Render
- Fly.io
- Railway
- VPS
- Docker対応PaaS

## 5. 本番前チェック

- 商品の `file_url` が正しい
- `PUBLIC_BASE_URL` が本番URL
- Stripeが本番キー
- Webhookが本番ドメインを指している
- `ADMIN_API_KEY` が十分長いランダム値
- SQLite DBが永続化される
- 特定商取引法、利用規約、プライバシーポリシー、税務対応を確認済み
