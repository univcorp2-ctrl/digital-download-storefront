from __future__ import annotations

import argparse
from pathlib import Path

from app.db import export_orders_csv, seed_if_empty


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export orders to CSV")
    parser.add_argument("--output", default="artifacts/orders.csv", help="CSV output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_if_empty()
    output_path = export_orders_csv(Path(args.output))
    print(f"Exported orders to {output_path}")


if __name__ == "__main__":
    main()
