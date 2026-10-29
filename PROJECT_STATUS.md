# MerchantOS POS — Project status

## Milestone 3: Transactional checkout

**Status: implemented and verified on the feature branch; PR #1 remains open and unmerged.**

GitHub Actions [run #40809686037](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40809686037) passed on commit `c164bf7` (29 October 2026):

- PostgreSQL 17 catalog seed and versioned checkout migration applied.
- ASP.NET Core 10 API built and started; live catalog endpoints passed.
- Live checkout assertions passed for cash and simulated card success, failed card, insufficient cash, invalid products/quantities, insufficient stock, server-side price and VAT, idempotent retry, conflicting key, order/receipt persistence, inventory deduction and concurrent competing purchases.
- Angular production build passed; 12/12 unit tests passed.
- Playwright Chromium desktop/mobile smoke passed 4/4 tests, including live checkout, receipts, history, catalog and cart. CI uploaded screenshots, report and API log.

The checkout API is a **demo** without authentication. Do not expose it publicly. Card outcomes are deterministic simulations; no real card data or gateway is used. No refunds, split payments, hardware printer, advanced reporting or multi-store inventory are included. Tablet visual review against Stitch remains a separate design check.

## Milestone 2 baseline

Milestone 2 catalog integration passed [Actions run #6](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40807068324): PostgreSQL initialized with 30 products and inventory rows; .NET API and live catalog checks passed; Angular build, 12/12 unit tests and 2/2 desktop/mobile browser smoke tests passed. Historical local-environment limitations were superseded by that CI verification.

## Local operation

Use `docker compose up -d --build` to start PostgreSQL, apply the checkout migration through the one-shot `migrate` service and start the API, then `npm ci && npm start` for Angular. The migration does not remove existing catalog data. See README for details.
