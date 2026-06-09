# Digital Download Storefront

デジタル商品を販売するための、Stripe連携対応ミニストアです。PDF、テンプレート、素材集、ノウハウ資料などを商品として登録し、購入導線、注文記録、CSV出力まで扱えます。

> 収益を保証するものではありません。実際の売上には商品品質、集客、価格設定、決済審査、法務・税務対応が必要です。

## できること

- 商品一覧ページを自動表示
- SQLiteで商品と注文を管理
- Stripe Checkoutへ接続可能
- Stripe未設定でもデモ決済で動作確認可能
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

| 用途 | 環境変数 / Secret | 説明 |
| --- | --- | --- |
| 公開URL | `PUBLIC_BASE_URL` | 例: `https://your-domain.example` |
| Stripe秘密鍵 | `STRIPE_SECRET_KEY` | Stripe Checkout作成に使用 |
| Stripe Webhook署名 | `STRIPE_WEBHOOK_SECRET` | 決済完了通知の検証に使用 |
| DB保存先 | `STORE_DB_PATH` | 例: `/data/store.db` |
| 管理用キー | `ADMIN_API_KEY` | 注文CSVの管理APIを保護 |

Secretsの実値はGitHubやREADMEに書かず、ホスティングサービス側のSecret機能に登録してください。

## 商品を追加する

`data/products.sample.json` を編集し、初回起動または再起動でSQLiteに投入します。各商品の `file_url` は購入後に渡すダウンロードURLです。本番では署名付きURLや会員認証の併用を推奨します。

## 注文CSV

ローカルまたはCIで以下を実行できます。

```bash
mkdir -p artifacts
python -c "from pathlib import Path; from app.main import seed_if_empty, export_orders_csv; seed_if_empty(); export_orders_csv(Path('artifacts/orders.csv'))"
```

GitHub Actionsの `workflow_dispatch` でも `sales-export` artifact を取得できます。

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
