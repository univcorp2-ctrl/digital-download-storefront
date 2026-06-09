# Digital Download Storefront

デジタル商品を販売するための、Stripe連携対応ミニストアです。PDF、テンプレート、素材集、ノウハウ資料などを商品として登録し、購入導線、注文記録、CSV出力まで扱えます。

> 収益を保証するものではありません。実際の売上には商品品質、集客、価格設定、決済審査、法務・税務対応が必要です。

## できること

- 商品一覧ページを自動表示
- SQLiteで商品と注文を管理
- Stripe Checkoutへ接続可能
- Stripe未設定でも開発環境ではデモ決済で動作確認可能
- 本番環境ではデモ決済を無効化し、Stripe設定を必須化
- 購入済み注文だけダウンロードURLを発行
- Render BlueprintとDockerで本番デプロイ可能
- Codespaces / devcontainer 対応
- pytest と ruff のテスト構成付き

## すぐ動かす

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

ブラウザで `http://127.0.0.1:8000` を開きます。

Dockerでも起動できます。

```bash
docker compose up --build
```

## 本番稼働

Render向けの `render.yaml` と `Dockerfile` を同梱済みです。詳細は [docs/production.md](docs/production.md) を確認してください。

本番で必要な環境変数 / Secret は以下です。

| 用途 | 環境変数 / Secret | 説明 |
| --- | --- | --- |
| 本番モード | `APP_ENV=production` | 本番向け動作に切り替え |
| デモ決済停止 | `ALLOW_DEMO_CHECKOUT=false` | 本番では必ずfalse |
| 公開URL | `PUBLIC_BASE_URL` | 例: `https://your-domain.example` |
| Stripe秘密鍵 | `STRIPE_SECRET_KEY` | Stripe Checkout作成に使用 |
| Stripe Webhook署名 | `STRIPE_WEBHOOK_SECRET` | 決済完了通知の検証に使用 |
| DB保存先 | `STORE_DB_PATH` | Renderでは `/data/store.db` |
| 管理用キー | `ADMIN_API_KEY` | 注文CSVの管理APIを保護 |

Secretsの実値はGitHubやREADMEに書かず、ホスティングサービス側のSecret機能に登録してください。

## 商品を追加する

`data/products.sample.json` を編集します。初回起動時にSQLiteへ投入されます。各商品の `file_url` には `downloads/your-file.txt` のようなローカルファイル、または外部URLを指定できます。

## 注文CSV

```bash
curl -H "x-admin-api-key: YOUR_ADMIN_API_KEY" \
  https://YOUR_PUBLIC_DOMAIN/api/admin/orders.csv
```

## API

| Method | Path | 説明 |
| --- | --- | --- |
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/products` | 商品一覧 |
| POST | `/api/checkout` | 決済セッション作成 |
| POST | `/api/orders/{order_id}/confirm-demo` | 開発用デモ決済完了。本番では無効 |
| GET | `/api/orders/{order_id}` | 注文確認 |
| GET | `/api/orders/{order_id}/download` | 支払い済み商品のダウンロード |
| GET | `/api/admin/orders.csv` | 注文CSV出力。`x-admin-api-key` が必要 |
| POST | `/api/stripe/webhook` | Stripe決済完了Webhook |

## 開発

```bash
ruff check .
pytest -q
```

## アーキテクチャ

詳細は [docs/architecture.md](docs/architecture.md) を参照してください。
