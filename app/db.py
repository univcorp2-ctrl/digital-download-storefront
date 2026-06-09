from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import SAMPLE_PRODUCTS_PATH, get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'usd',
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


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def upsert_product(product: dict[str, Any], db_path: Path | None = None) -> None:
    required = {"id", "name", "description", "price_cents", "currency", "file_url"}
    missing = required - set(product)
    if missing:
        raise ValueError(f"Product is missing required fields: {sorted(missing)}")

    with connect(db_path) as connection:
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
                product.get("currency", "usd").lower(),
                product["file_url"],
                1 if product.get("active", True) else 0,
                now_iso(),
            ),
        )


def seed_products_from_file(path: Path = SAMPLE_PRODUCTS_PATH, db_path: Path | None = None) -> int:
    if not path.exists():
        return 0
    products = json.loads(path.read_text(encoding="utf-8"))
    for product in products:
        upsert_product(product, db_path)
    return len(products)


def count_products(db_path: Path | None = None) -> int:
    with connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM products").fetchone()
    return int(row["total"])


def seed_if_empty(db_path: Path | None = None) -> int:
    init_db(db_path)
    if count_products(db_path) == 0:
        return seed_products_from_file(db_path=db_path)
    return 0


def list_products(db_path: Path | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, price_cents, currency, file_url, active, created_at
            FROM products
            WHERE active = 1
            ORDER BY price_cents ASC, name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_product(product_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, name, description, price_cents, currency, file_url, active, created_at
            FROM products
            WHERE id = ? AND active = 1
            """,
            (product_id,),
        ).fetchone()
    return row_to_dict(row)


def create_order(
    *,
    product: dict[str, Any],
    customer_email: str,
    payment_provider: str = "pending",
    checkout_url: str = "",
    db_path: Path | None = None,
) -> dict[str, Any]:
    order_id = f"ord_{uuid.uuid4().hex}"
    order = {
        "id": order_id,
        "product_id": product["id"],
        "customer_email": customer_email,
        "amount_cents": product["price_cents"],
        "currency": product["currency"],
        "status": "pending",
        "payment_provider": payment_provider,
        "checkout_url": checkout_url,
        "created_at": now_iso(),
        "paid_at": None,
    }
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO orders (
                id, product_id, customer_email, amount_cents, currency, status,
                payment_provider, checkout_url, created_at, paid_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["id"],
                order["product_id"],
                order["customer_email"],
                order["amount_cents"],
                order["currency"],
                order["status"],
                order["payment_provider"],
                order["checkout_url"],
                order["created_at"],
                order["paid_at"],
            ),
        )
    return order


def update_order_checkout(
    order_id: str, payment_provider: str, checkout_url: str, db_path: Path | None = None
) -> None:
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE orders
            SET payment_provider = ?, checkout_url = ?
            WHERE id = ?
            """,
            (payment_provider, checkout_url, order_id),
        )


def mark_order_paid(order_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    paid_at = now_iso()
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE orders
            SET status = 'paid', paid_at = COALESCE(paid_at, ?)
            WHERE id = ?
            """,
            (paid_at, order_id),
        )
    return get_order(order_id, db_path)


def get_order(order_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as connection:
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
    return row_to_dict(row)


def list_orders(db_path: Path | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
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


def export_orders_csv(output_path: Path, db_path: Path | None = None) -> Path:
    orders = list_orders(db_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)
    return output_path
