from __future__ import annotations

from app.db import init_db, seed_products_from_file


def main() -> None:
    init_db()
    count = seed_products_from_file()
    print(f"Seeded {count} products")


if __name__ == "__main__":
    main()
