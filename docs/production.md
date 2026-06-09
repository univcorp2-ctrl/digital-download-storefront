# Production Runbook

このrepoはRenderへそのままデプロイできる構成にしています。

## 何が本番向けになっているか

- `Dockerfile` でコンテナ化
- `render.yaml` でRender Blueprint化
- `/api/health` をヘルスチェックに設定
- `STORE_DB_PATH=/data/store.db` でSQLiteを永続ディスクへ保存
- `APP_ENV=production` と `ALLOW_DEMO_CHECKOUT=false` でデモ決済を本番停止
- `STRIPE_SECRET_KEY` と `STRIPE_WEBHOOK_SECRET` はRender作成時に入力するSecret扱い
- `ADMIN_API_KEY` はRender側で自動生成

## Renderで公開する

1. RenderでNew Blueprintを選ぶ
2. GitHub repo `univcorp2-ctrl/digital-download-storefront` を選ぶ
3. Blueprint fileは `render.yaml`
4. Environment Variablesで以下を入力する
   - `PUBLIC_BASE_URL`: 最初はRenderが発行するURL。独自ドメイン設定後は本番ドメイン
   - `STRIPE_SECRET_KEY`: Stripeの秘密鍵
   - `STRIPE_WEBHOOK_SECRET`: Stripe Webhook署名Secret
5. 作成後、Deployが完了したら公開URLを開く

## Stripe側の設定

Stripe Webhookの送信先を以下にします。

```text
https://YOUR_PUBLIC_DOMAIN/api/stripe/webhook
```

イベントはまず `checkout.session.completed` を選びます。

## 公開後の確認

```bash
curl https://YOUR_PUBLIC_DOMAIN/api/health
```

レスポンスに `status: ok` が含まれていればアプリは起動しています。

## 注文CSV

```bash
curl -H "x-admin-api-key: YOUR_ADMIN_API_KEY" \
  https://YOUR_PUBLIC_DOMAIN/api/admin/orders.csv
```

## 注意

- SQLite永続ディスクは単一インスタンス運用向けです。売上が増えたらPostgreSQLへ移行してください。
- デジタル商品の中身は `downloads/` のファイルを差し替えてください。
- 商品マスタは `data/products.sample.json` を編集し、新しいDBでは初回起動時に投入されます。
- 本番では特定商取引法、プライバシーポリシー、利用規約、返金ポリシー、税務対応が必要です。
