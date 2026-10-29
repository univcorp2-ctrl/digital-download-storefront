"""Regression checks for safe Stripe Checkout order fulfillment.

Stripe SDK signature verification remains enabled in production. These unit tests
stub only the signature verification result so the handler's business checks are
exercised without sending a network request or using credentials.
"""
from __future__ import annotations

import pytest
import stripe
from fastapi.testclient import TestClient

from app.main import (
    app,
    create_order,
    get_order,
    init_db,
    update_order_checkout,
    upsert_product,
)


@pytest.fixture
def checkout_order(tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_DB_PATH", str(tmp_path / "stripe-guard-test.db"))
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_not_a_real_secret")
    init_db()
    product = {
        "id": "sample-checkout-product",
        "name": "Stripe test item",
        "description": "Sample",
        "price_cents": 980,
        "currency": "jpy",
        "file_url": "downloads/starter-kit.txt",
    }
    upsert_product(product)
    order = create_order(product, "testing@example.invalid")
    update_order_checkout(order["id"], "stripe", "https://checkout.stripe.com/test-session")
    return order


@pytest.mark.parametrize(
    ("event_type", "payment_status", "amount", "currency", "product_id", "expected"),
    [
        ("checkout.session.completed", "paid", 980, "jpy", "sample-checkout-product", "paid"),
        ("checkout.session.completed", "unpaid", 980, "jpy", "sample-checkout-product", "pending"),
        ("checkout.session.completed", "paid", 0, "jpy", "sample-checkout-product", "pending"),
        ("checkout.session.completed", "paid", 980, "usd", "sample-checkout-product", "pending"),
        ("checkout.session.completed", "paid", 980, "jpy", "wrong-product", "pending"),
        ("checkout.session.async_payment_succeeded", "paid", 980, "jpy", "sample-checkout-product", "paid"),
    ],
)
def test_fulfillment_requires_matching_paid_checkout(
    checkout_order, monkeypatch, event_type, payment_status, amount, currency, product_id, expected
):
    event = {
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_sample",
                "mode": "payment",
                "payment_status": payment_status,
                "amount_total": amount,
                "currency": currency,
                "metadata": {"order_id": checkout_order["id"], "product_id": product_id},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *args: event)
    with TestClient(app) as client:
        resp = client.post("/api/stripe/webhook", data=b"{}", headers={"stripe-signature": "test"})
    assert resp.status_code == 200
    assert get_order(checkout_order["id"])["status"] == expected


def test_unrelated_event_never_fulfills_order(checkout_order, monkeypatch):
    event = {"type": "customer.created", "data": {"object": {}}}
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *args: event)
    with TestClient(app) as client:
        resp = client.post("/api/stripe/webhook", data=b"{}", headers={"stripe-signature": "test"})
    assert resp.status_code == 200
    assert get_order(checkout_order["id"])["status"] == "pending"
