from __future__ import annotations

from typing import Any

from app.config import get_stripe_secret_key


def create_checkout_url(
    *,
    order: dict[str, Any],
    product: dict[str, Any],
    base_url: str,
) -> tuple[str, str]:
    """Return (provider, checkout_url).

    When STRIPE_SECRET_KEY is present, this creates a Stripe Checkout session.
    Otherwise it returns a local demo payment URL so the application remains usable in CI
    and during first-run development.
    """
    stripe_secret_key = get_stripe_secret_key()
    success_url = f"{base_url}/success.html?order_id={order['id']}"
    cancel_url = f"{base_url}/?cancelled=1"

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
        cancel_url=cancel_url,
        metadata={"order_id": order["id"], "product_id": product["id"]},
    )
    if not session.url:
        raise RuntimeError("Stripe did not return a checkout URL")
    return "stripe", session.url
