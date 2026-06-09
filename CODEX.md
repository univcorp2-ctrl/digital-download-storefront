# CODEX

## Project intent

Create a small, monetizable digital download storefront. Keep the first version simple, testable, and deployable.

## Development rules

- Keep API behavior covered by tests.
- Do not commit real Stripe keys or customer data.
- Keep demo checkout available for CI and local development.
- Prefer simple SQLite storage until the product needs PostgreSQL.
- Document required production Secrets in README and docs/setup.md.

## Useful commands

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q
uvicorn app.main:app --reload
```
