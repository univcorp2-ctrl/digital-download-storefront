from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from app.config import BASE_DIR, get_admin_api_key, get_public_base_url, get_stripe_webhook_secret
from app.db import (
    export_orders_csv,
    get_order,
    get_product,
    list_products,
    mark_order_paid,
    seed_if_empty,
    update_order_checkout,
    create_order,
)
from app.payments import create_checkout_url

app = FastAPI(
    title="Digital Download Storefront",
    description="Sell digital downloads with a Stripe-ready FastAPI storefront.",
    version="1.0.0",
)

STATIC_DIR = BASE_DIR / "app" / "static"
ARTIFACTS_DIR = BASE_DIR / "artifacts"


class ProductOut(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str


class CheckoutRequest(BaseModel):
    product_id: str = Field(min_length=1)
    customer_email: EmailStr


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


@app.on_event("startup")
def startup() -> None:
    seed_if_empty()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/success.html", include_in_schema=False)
def success_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "success.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    product = get_product(payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    order = create_order(product=product, customer_email=payload.customer_email)
    request_base_url = str(request.base_url).rstrip("/")
    base_url = get_public_base_url(request_base_url)
    provider, checkout_url = create_checkout_url(order=order, product=product, base_url=base_url)
    update_order_checkout(order["id"], provider, checkout_url)

    return {
        "order_id": order["id"],
        "payment_provider": provider,
        "checkout_url": checkout_url,
    }


@app.post("/api/orders/{order_id}/confirm-demo", response_model=OrderOut)
def confirm_demo_order(order_id: str) -> dict[str, Any]:
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


def order_response(order: dict[str, Any]) -> dict[str, Any]:
    download_url = order["file_url"] if order["status"] == "paid" else None
    return {
        "id": order["id"],
        "product_id": order["product_id"],
        "product_name": order["product_name"],
        "customer_email": order["customer_email"],
        "amount_cents": order["amount_cents"],
        "currency": order["currency"],
        "status": order["status"],
        "payment_provider": order["payment_provider"],
        "download_url": download_url,
    }


@app.get("/api/admin/orders.csv")
def admin_orders_csv(
    x_admin_api_key: Annotated[str | None, Header(alias="x-admin-api-key")] = None,
) -> Response:
    if x_admin_api_key != get_admin_api_key():
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    output_path = export_orders_csv(ARTIFACTS_DIR / "orders.csv")
    return PlainTextResponse(
        output_path.read_text(encoding="utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    webhook_secret = get_stripe_webhook_secret()
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
