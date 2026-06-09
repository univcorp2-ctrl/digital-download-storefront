#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q
mkdir -p artifacts
python -c "from pathlib import Path; from app.main import seed_if_empty, export_orders_csv; seed_if_empty(); export_orders_csv(Path('artifacts/orders.csv'))"
