from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "store.db"
SAMPLE_PRODUCTS_PATH = BASE_DIR / "data" / "products.sample.json"


def get_db_path() -> Path:
    return Path(os.getenv("STORE_DB_PATH", str(DEFAULT_DB_PATH)))


def get_public_base_url(default: str) -> str:
    return os.getenv("PUBLIC_BASE_URL", default).rstrip("/")


def get_admin_api_key() -> str:
    return os.getenv("ADMIN_API_KEY", "change-me-local-admin-key")


def get_stripe_secret_key() -> str | None:
    value = os.getenv("STRIPE_SECRET_KEY")
    return value if value else None


def get_stripe_webhook_secret() -> str | None:
    value = os.getenv("STRIPE_WEBHOOK_SECRET")
    return value if value else None
