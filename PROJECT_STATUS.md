# MerchantOS POS — Project status

## Milestone 3.1: Checkout reliability

**Status: verified on `feat/milestone-3-checkout`; PR #1 is open and unmerged.**

[GitHub Actions run #40928422996](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40928422996) passed on commit `49a8e98` (29 October 2026):

- PostgreSQL 17 seed and versioned checkout migration passed; .NET 10 API built and live catalog/transaction assertions passed.
- Live checkout checks cover cash and simulated card success, declined payment, insufficient cash and stock, invalid requests, rollback, server-side totals, receipt/history, duplicate same-key requests, conflicting keys and competing purchases. No stock is deducted for failed payments.
- Angular production build passed; **20/20 unit tests** passed across three files, including eight request identity and payment recovery tests.
- Playwright Chromium desktop/mobile checkout and recovery passed **6/6 tests without retries**. Screenshots, HTML report and API log are uploaded as CI artifacts.

The frontend now clears the key and fingerprint together for definitive failures and successful checkout, preserves the same key after uncertain network/server failures, and creates a new key when the request changes. Cart removal and clearing also invalidate the pending request. Submissions are blocked while payment is in progress; cash accepts only integer halalas.

## Milestone 3: Transactional checkout

Versioned SQL migration adds orders, order items, payments and checkout idempotency. The API calculates prices, discounts and VAT from PostgreSQL and updates inventory atomically with row locks. Angular provides cash and deterministic simulated card checkout, order history and printable receipts. Milestone 3 was previously verified by [run #40809931154](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40809931154), which passed the earlier 12/12 unit and 4/4 browser suites.

## Milestone 2 baseline

Milestone 2 catalog integration passed [Actions run #6](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40807068324): PostgreSQL initialized with 30 products and inventory rows; .NET API/live catalog checks, Angular build, 12/12 unit tests and 2/2 desktop/mobile browser smoke tests passed. Earlier local-environment gaps were superseded by this CI result.

## Known limitations

The checkout API is **demo-only without authentication** and must not be publicly exposed. Card outcomes are deterministic simulations without card details or a gateway. Refunds, split payments, receipt printer integration, advanced reporting and multi-store stock remain outside scope. Tablet visual comparison against Stitch remains open.

## Local operation

Run `docker compose up -d --build` to start PostgreSQL, apply the checkout migration through the one-shot `migrate` service and start the API. Run `npm ci && npm start` for Angular. The migration preserves the existing catalog. See README for details.
