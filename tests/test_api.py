from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_products_are_seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_DB_PATH", str(tmp_path / "store.db"))
    with TestClient(app) as client:
        response = client.get("/api/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 3
    assert {product["id"] for product in products} >= {
        "starter-kit",
        "revenue-dashboard-template",
    }


def test_demo_checkout_and_download_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_DB_PATH", str(tmp_path / "store.db"))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEMO_CHECKOUT", "true")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with TestClient(app) as client:
        checkout_response = client.post(
            "/api/checkout",
            json={"product_id": "starter-kit", "customer_email": "buyer@example.com"},
        )
        assert checkout_response.status_code == 200
        checkout = checkout_response.json()
        assert checkout["payment_provider"] == "demo"
        assert "/success.html" in checkout["checkout_url"]

        order_id = checkout["order_id"]
        unpaid_response = client.get(f"/api/orders/{order_id}")
        assert unpaid_response.status_code == 200
        assert unpaid_response.json()["download_url"] is None

        blocked_download = client.get(f"/api/orders/{order_id}/download")
        assert blocked_download.status_code == 403

        confirm_response = client.post(f"/api/orders/{order_id}/confirm-demo")
        assert confirm_response.status_code == 200
        paid_order = confirm_response.json()
        assert paid_order["status"] == "paid"
        assert paid_order["download_url"] == f"/api/orders/{order_id}/download"

        download_response = client.get(paid_order["download_url"])
        assert download_response.status_code == 200
        assert "副業スターターキット" in download_response.text


def test_production_requires_stripe_when_demo_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_DB_PATH", str(tmp_path / "store.db"))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_DEMO_CHECKOUT", "false")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/checkout",
            json={"product_id": "starter-kit", "customer_email": "buyer@example.com"},
        )
    assert response.status_code == 503


def test_admin_csv_requires_key(tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_DB_PATH", str(tmp_path / "store.db"))
    monkeypatch.setenv("ADMIN_API_KEY", "secret-test-key")
    with TestClient(app) as client:
        unauthorized = client.get("/api/admin/orders.csv")
        assert unauthorized.status_code == 401

        authorized = client.get(
            "/api/admin/orders.csv", headers={"x-admin-api-key": "secret-test-key"}
        )
        assert authorized.status_code == 200
        assert "text/csv" in authorized.headers["content-type"]
        assert "product_name" in authorized.text
