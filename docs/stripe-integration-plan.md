# Stripe integration plan — univ合同会社
Date: 2026-10-29 JST

This is a preliminary implementation plan based on https://univ-corp.com/ and repository code review, not an output of the Stripe implementation planner (OAuth pending).

## Business use cases
- AI/mobile consulting: hosted Stripe Checkout for fixed-price deliverables, Invoicing for B2B projects.
- AI support plans: Billing subscriptions and customer self-service portal after contracts and prices are confirmed.
- Wholesale: Invoicing with agreed payment terms and shipping rules.
- Digital downloads: existing FastAPI Checkout integration in this repository.
- Third-party marketplace: use Connect only if payments are genuinely split among providers. Do not assume Connect is needed merely because univ operates multiple business lines.

## Phases
1. Enable Stripe sandbox and OAuth for the official MCP plugin. Confirm the account region and access, invoke stripe_implementation_planner, and reconcile the output against this plan.
2. Define approved products and prices. Use hosted Checkout and server-side price allowlists. Verify webhook signatures, paid state, currency, amount, session association and event deduplication before fulfillment.
3. Add recurring Billing only for contracted subscriptions, with subscription and invoice webhooks and Customer Portal.
4. Configure Invoicing for project work and wholesale, including payment terms and business invoice identifiers; avoid duplicate Checkout and invoice charges.
5. Configure Stripe Tax only after confirming seller registration, product tax categories, Japan consumption-tax treatment and cross-border obligations. Test on sandbox.
6. Add Connect only if actual platform payouts are confirmed; design connected-account onboarding, KYC, fees, refunds, disputes, tax and settlement responsibility first.

## Current implementation audit
- Existing app/main.py uses Stripe Checkout and a signature-verified webhook.
- Previously, checkout.session.completed used only an order ID to mark paid. The feature branch adds paid-state, amount, currency and product validation, and handles delayed payment success.
- JPY zero-decimal price display previously divided by 100; corrected on the feature branch.
- Product strings were interpolated into HTML; HTML escaping added.
- No verified end-to-end Stripe account connection or live checkout yet. Billing, Invoicing, Connect and Tax flows are planned, not deployed.

## Required tests and controls
- Sandbox-only development; secrets in deployment secret store, never in source.
- Webhook signature, repeated-event handling, failed/delayed payments, amount and currency mismatch, refund, chargeback, retries.
- Endpoint access control for downloads, event ledger and stable Checkout Session to order association.
- Independent CI, operational monitoring, customer support and rollback before production.
- Final release only after verified tax, legal, contractual and account eligibility.

## Official docs
- https://docs.stripe.com/mcp
- https://docs.stripe.com/payments/checkout
- https://docs.stripe.com/billing
- https://docs.stripe.com/invoicing/integration
- https://docs.stripe.com/tax
- https://docs.stripe.com/connect
