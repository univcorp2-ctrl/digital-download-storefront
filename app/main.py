from __future__ import annotations

import csv
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "store.db"
SAMPLE_PRODUCTS_PATH = BASE_DIR / "data" / "products.sample.json"
DOWNLOAD_DIR = BASE_DIR / "downloads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'jpy',
    file_url TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_provider TEXT NOT NULL,
    checkout_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    FOREIGN KEY(product_id) REFERENCES products(id)
);
"""

app = FastAPI(
    title="Digital Download Storefront",
    description="Sell digital downloads with a Stripe-ready FastAPI storefront.",
    version="1.1.0",
)


class ProductOut(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str


class CheckoutRequest(BaseModel):
    product_id: str = Field(min_length=1)
    customer_email: str = Field(min_length=3)


class CheckoutResponse(BaseModel):
    order_id: str
    payment_provider: str
    checkout_url: str


class OrderOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    customer_email: str
    amount_cents: int
    currency: str
    status: str
    payment_provider: str
    download_url: str | None = None


def get_db_path() -> Path:
    return Path(os.getenv("STORE_DB_PATH", str(DEFAULT_DB_PATH)))


def get_public_base_url(default: str) -> str:
    return os.getenv("PUBLIC_BASE_URL", default).rstrip("/")


def get_admin_api_key() -> str:
    return os.getenv("ADMIN_API_KEY", "change-me-local-admin-key")


def is_production() -> bool:
    return os.getenv("APP_ENV", "development").lower() == "production"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def allow_demo_checkout() -> bool:
    return env_bool("ALLOW_DEMO_CHECKOUT", not is_production())


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)


def upsert_product(product: dict[str, Any]) -> None:
    required = {"id", "name", "description", "price_cents", "currency", "file_url"}
    missing = required - set(product)
    if missing:
        raise ValueError(f"Product is missing required fields: {sorted(missing)}")

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO products (
                id, name, description, price_cents, currency, file_url, active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                price_cents = excluded.price_cents,
                currency = excluded.currency,
                file_url = excluded.file_url,
                active = excluded.active
            """,
            (
                product["id"],
                product["name"],
                product["description"],
                int(product["price_cents"]),
                product.get("currency", "jpy").lower(),
                product["file_url"],
                1 if product.get("active", True) else 0,
                now_iso(),
            ),
        )


def seed_products_from_file(path: Path = SAMPLE_PRODUCTS_PATH) -> int:
    if not path.exists():
        return 0
    products = json.loads(path.read_text(encoding="utf-8"))
    for product in products:
        upsert_product(product)
    return len(products)


def count_products() -> int:
    with connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM products").fetchone()
    return int(row["total"])


def seed_if_empty() -> int:
    init_db()
    if count_products() == 0:
        return seed_products_from_file()
    return 0


def list_products() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, price_cents, currency, file_url, active, created_at
            FROM products
            WHERE active = 1
            ORDER BY price_cents ASC, name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_product(product_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, name, description, price_cents, currency, file_url, active, created_at
            FROM products
            WHERE id = ? AND active = 1
            """,
            (product_id,),
        ).fetchone()
    return dict(row) if row else None


def create_order(product: dict[str, Any], customer_email: str) -> dict[str, Any]:
    order = {
        "id": f"ord_{uuid.uuid4().hex}",
        "product_id": product["id"],
        "customer_email": customer_email,
        "amount_cents": product["price_cents"],
        "currency": product["currency"],
        "status": "pending",
        "payment_provider": "pending",
        "checkout_url": "",
        "created_at": now_iso(),
        "paid_at": None,
    }
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO orders (
                id, product_id, customer_email, amount_cents, currency, status,
                payment_provider, checkout_url, created_at, paid_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(order.values()),
        )
    return order


def update_order_checkout(order_id: str, payment_provider: str, checkout_url: str) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE orders SET payment_provider = ?, checkout_url = ? WHERE id = ?",
            (payment_provider, checkout_url, order_id),
        )


def get_order(order_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                orders.id,
                orders.product_id,
                orders.customer_email,
                orders.amount_cents,
                orders.currency,
                orders.status,
                orders.payment_provider,
                orders.checkout_url,
                orders.created_at,
                orders.paid_at,
                products.name AS product_name,
                products.file_url AS file_url
            FROM orders
            JOIN products ON products.id = orders.product_id
            WHERE orders.id = ?
            """,
            (order_id,),
        ).fetchone()
    return dict(row) if row else None


def mark_order_paid(order_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE orders
            SET status = 'paid', paid_at = COALESCE(paid_at, ?)
            WHERE id = ?
            """,
            (now_iso(), order_id),
        )
    return get_order(order_id)


def list_orders() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                orders.id,
                orders.product_id,
                products.name AS product_name,
                orders.customer_email,
                orders.amount_cents,
                orders.currency,
                orders.status,
                orders.payment_provider,
                orders.created_at,
                orders.paid_at
            FROM orders
            JOIN products ON products.id = orders.product_id
            ORDER BY orders.created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def export_orders_csv(output_path: Path | None = None) -> str:
    fieldnames = [
        "id",
        "product_id",
        "product_name",
        "customer_email",
        "amount_cents",
        "currency",
        "status",
        "payment_provider",
        "created_at",
        "paid_at",
    ]
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(list_orders())
    csv_text = output.getvalue()
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(csv_text, encoding="utf-8")
    return csv_text


def create_checkout_url(order: dict[str, Any], product: dict[str, Any], base_url: str) -> tuple[str, str]:
    success_url = f"{base_url}/success.html?order_id={order['id']}"
    stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret_key:
        return "demo", success_url

    import stripe

    stripe.api_key = stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=order["customer_email"],
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": product["currency"],
                    "unit_amount": product["price_cents"],
                    "product_data": {
                        "name": product["name"],
                        "description": product["description"],
                    },
                },
            }
        ],
        success_url=success_url,
        cancel_url=f"{base_url}/?cancelled=1",
        metadata={"order_id": order["id"], "product_id": product["id"]},
    )
    if not session.url:
        raise RuntimeError("Stripe did not return a checkout URL")
    return "stripe", session.url


def order_response(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": order["id"],
        "product_id": order["product_id"],
        "product_name": order["product_name"],
        "customer_email": order["customer_email"],
        "amount_cents": order["amount_cents"],
        "currency": order["currency"],
        "status": order["status"],
        "payment_provider": order["payment_provider"],
        "download_url": f"/api/orders/{order['id']}/download" if order["status"] == "paid" else None,
    }


def local_download_path(file_url: str) -> Path | None:
    if file_url.startswith(("http://", "https://")):
        return None
    file_path = (BASE_DIR / file_url.lstrip("/")).resolve()
    downloads_root = DOWNLOAD_DIR.resolve()
    if file_path != downloads_root and downloads_root not in file_path.parents:
        raise HTTPException(status_code=400, detail="Invalid local download path")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Download file not found")
    return file_path


@app.on_event("startup")
def startup() -> None:
    seed_if_empty()


@app.get("/", include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(STOREFRONT_HTML)


@app.get("/success.html", include_in_schema=False)
def success_page() -> HTMLResponse:
    return HTMLResponse(SUCCESS_HTML)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app_env": os.getenv("APP_ENV", "development")}


@app.get("/api/products", response_model=list[ProductOut])
def products() -> list[dict[str, Any]]:
    return [
        {
            "id": product["id"],
            "name": product["name"],
            "description": product["description"],
            "price_cents": product["price_cents"],
            "currency": product["currency"],
        }
        for product in list_products()
    ]


@app.post("/api/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest, request: Request) -> dict[str, str]:
    if not os.getenv("STRIPE_SECRET_KEY") and not allow_demo_checkout():
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY or enable demo checkout.",
        )

    product = get_product(payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    order = create_order(product, payload.customer_email)
    base_url = get_public_base_url(str(request.base_url).rstrip("/"))
    provider, checkout_url = create_checkout_url(order, product, base_url)
    update_order_checkout(order["id"], provider, checkout_url)

    return {
        "order_id": order["id"],
        "payment_provider": provider,
        "checkout_url": checkout_url,
    }


@app.post("/api/orders/{order_id}/confirm-demo", response_model=OrderOut)
def confirm_demo_order(order_id: str) -> dict[str, Any]:
    if not allow_demo_checkout():
        raise HTTPException(status_code=403, detail="Demo checkout is disabled")
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["payment_provider"] != "demo":
        raise HTTPException(status_code=400, detail="Only demo orders can be confirmed here")
    paid_order = mark_order_paid(order_id)
    if not paid_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_response(paid_order)


@app.get("/api/orders/{order_id}", response_model=OrderOut)
def order_status(order_id: str) -> dict[str, Any]:
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_response(order)


@app.get("/api/orders/{order_id}/download")
def download_order(order_id: str) -> Response:
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] != "paid":
        raise HTTPException(status_code=403, detail="Order is not paid")

    file_url = order["file_url"]
    local_path = local_download_path(file_url)
    if local_path is None:
        return RedirectResponse(file_url, status_code=302)
    return FileResponse(local_path, filename=local_path.name)


@app.get("/api/admin/orders.csv")
def admin_orders_csv(
    x_admin_api_key: Annotated[str | None, Header(alias="x-admin-api-key")] = None,
) -> Response:
    if x_admin_api_key != get_admin_api_key():
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return PlainTextResponse(
        export_orders_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=400, detail="STRIPE_WEBHOOK_SECRET is not configured")

    import stripe

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        if order_id:
            mark_order_paid(order_id)
    return {"status": "received"}


STOREFRONT_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Digital Download Storefront</title>
  <style>
    :root { font-family: Inter, system-ui, sans-serif; background: #f7f7fb; color: #18181b; }
    body { margin: 0; }
    .hero { background: linear-gradient(135deg, #111827, #4f46e5); color: white; padding: 72px 24px; text-align: center; }
    .hero h1 { font-size: clamp(2.2rem, 7vw, 4.7rem); line-height: 1; margin: 8px auto 18px; max-width: 900px; }
    .hero p { max-width: 680px; margin: 0 auto; color: #e5e7eb; font-size: 1.1rem; }
    .eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: .78rem; font-weight: 800; color: #a5b4fc; }
    main { width: min(1100px, calc(100% - 32px)); margin: 32px auto; }
    .notice, .card, .success-card { background: white; border: 1px solid #e5e7eb; border-radius: 24px; padding: 24px; box-shadow: 0 16px 40px rgb(15 23 42 / 8%); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; margin-top: 24px; }
    .price { font-size: 2rem; font-weight: 900; color: #4f46e5; }
    label { display: grid; gap: 8px; color: #52525b; font-weight: 700; }
    input, button, .button { border-radius: 999px; border: 1px solid #d4d4d8; padding: 12px 16px; font: inherit; }
    button, .button { display: inline-block; margin-top: 14px; width: 100%; border: 0; background: #4f46e5; color: white; font-weight: 900; cursor: pointer; text-decoration: none; }
    button:disabled { opacity: .6; cursor: wait; }
    .message { min-height: 1.4rem; color: #52525b; }
    footer { text-align: center; padding: 40px 16px; color: #71717a; }
  </style>
</head>
<body>
  <header class="hero">
    <p class="eyebrow">Stripe-ready micro storefront</p>
    <h1>今日から売れるデジタル商品ストア</h1>
    <p>PDF、テンプレート、ノウハウ資料を登録して、購入ボタンと注文管理をすぐに開始できます。</p>
  </header>
  <main>
    <section class="notice"><strong>使い方:</strong> 商品カードのメール欄に入力して購入ボタンを押すと、Stripeまたはデモ決済へ進みます。</section>
    <section id="products" class="grid" aria-live="polite"></section>
  </main>
  <footer>Built with FastAPI, SQLite, and Stripe Checkout.</footer>
  <script>
    const productsEl = document.querySelector('#products');
    function formatPrice(priceCents, currency) {
      return new Intl.NumberFormat('ja-JP', { style: 'currency', currency: currency.toUpperCase() }).format(priceCents / 100);
    }
    async function loadProducts() {
      productsEl.innerHTML = '<p>商品を読み込んでいます...</p>';
      const response = await fetch('/api/products');
      const products = await response.json();
      productsEl.innerHTML = '';
      products.forEach((product) => {
        const card = document.createElement('article');
        card.className = 'card';
        card.innerHTML = `<h2>${product.name}</h2><p>${product.description}</p><p class="price">${formatPrice(product.price_cents, product.currency)}</p><form data-product-id="${product.id}"><label>メールアドレス<input name="email" type="email" placeholder="you@example.com" required /></label><button type="submit">購入する</button></form><p class="message" role="status"></p>`;
        productsEl.appendChild(card);
      });
    }
    productsEl.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.target;
      const message = form.parentElement.querySelector('.message');
      const button = form.querySelector('button');
      button.disabled = true;
      message.textContent = '決済URLを作成しています...';
      try {
        const response = await fetch('/api/checkout', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_id: form.dataset.productId, customer_email: form.email.value })
        });
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Checkout failed');
        }
        const checkout = await response.json();
        window.location.href = checkout.checkout_url;
      } catch (error) {
        message.textContent = error.message || '決済URLを作成できませんでした。';
        button.disabled = false;
      }
    });
    loadProducts();
  </script>
</body>
</html>
"""

SUCCESS_HTML = """<!doctype html>
<html lang="ja">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>Purchase complete</title></head>
<body style="font-family: system-ui, sans-serif; background:#f7f7fb; color:#18181b;">
  <main style="max-width:720px; margin:48px auto; background:white; border:1px solid #e5e7eb; border-radius:24px; padding:32px; text-align:center; box-shadow:0 16px 40px rgb(15 23 42 / 8%);">
    <p style="color:#4f46e5; font-weight:800; letter-spacing:.12em; text-transform:uppercase;">Payment complete</p>
    <h1>購入ありがとうございます</h1>
    <p id="status">注文を確認しています...</p>
    <p><a id="download" href="#" style="display:none; background:#4f46e5; color:white; padding:12px 18px; border-radius:999px; text-decoration:none; font-weight:900;">ダウンロードする</a></p>
    <p><a href="/">ストアへ戻る</a></p>
  </main>
  <script>
    async function confirmOrder() {
      const params = new URLSearchParams(window.location.search);
      const orderId = params.get('order_id');
      const status = document.querySelector('#status');
      const download = document.querySelector('#download');
      if (!orderId) { status.textContent = '注文IDが見つかりません。'; return; }
      try { await fetch(`/api/orders/${orderId}/confirm-demo`, { method: 'POST' }); } catch (error) {}
      const response = await fetch(`/api/orders/${orderId}`);
      const order = await response.json();
      if (order.status === 'paid' && order.download_url) {
        status.textContent = `${order.product_name} の購入が完了しました。`;
        download.href = order.download_url;
        download.style.display = 'inline-block';
      } else {
        status.textContent = '決済確認中です。Webhook反映後に再度確認してください。';
      }
    }
    confirmOrder();
  </script>
</body>
</html>
"""
