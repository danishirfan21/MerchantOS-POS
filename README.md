# Authentication milestone

See [authentication architecture and setup](docs/authentication.md). Protected API routes now require genuine sessions and CSRF on unsafe methods. Development identities must be explicitly provisioned from environment credentials; there are no default accounts. Angular uses the same-origin API proxy and HttpOnly session cookies.

# MerchantOS POS

A bilingual English/Arabic retail checkout demo for a Saudi electronics store. The cashier UI uses Angular 22 and connects to an ASP.NET Core 10 API backed by PostgreSQL 17. Prices and transaction totals use integer halalas (SAR); the API reads current prices, locks inventory rows, records orders and simulated payments, and deducts stock in one database transaction.

> **Demo only:** The API requires authenticated sessions and explicit role policies. Do not expose it to the public internet. Card approval/decline is deterministic simulation; no card details are collected or processed.

## Features

- Responsive catalog of 30 products, local original SVG illustrations, search, category filters and live stock.
- Signals cart with stock limits, 0/5/10% discounts and 15% VAT; English/Arabic and RTL across catalog, payment, order history and receipts.
- Cash tender/change and simulated card checkout, safe idempotent retries, inventory refresh, printable receipt and recent orders.
- PostgreSQL row locks serialize competing stock purchases; duplicate checkout keys cannot create duplicate completed sales.

## Screenshots

Actual live API/PostgreSQL browser captures at the requested viewports. CI also uploads the Playwright report and cart/receipt captures.

| Desktop 1440×900 | Tablet 768×1024 | Mobile 390×844 |
| --- | --- | --- |
| [View desktop](docs/screenshots/desktop.png) | [View tablet](docs/screenshots/tablet.png) | [View mobile](docs/screenshots/mobile.png) |

## Run locally

Install Docker (with Compose), Node.js 24 and npm. From the repository root:

```sh
docker compose up -d db
# Apply all migrations and provision accounts as documented in docs/authentication.md.
# Run the API as a host process over HTTPS (or explicit loopback-only Development HTTP).
npm ci
npm start
```

Open `http://localhost:4200`. The Angular dev server proxies `/api` to `http://127.0.0.1:5080`. Check API health at `http://localhost:5080/api/health`. Use Compose for PostgreSQL; the legacy container API HTTP path is not compatible with the strict loopback transport exception. Apply all db/migrations/*.sql in numeric order. The migration preserves an existing database volume; the initial catalog seed contains 30 products and inventory rows. Compose credentials are for local demo use only.

## Verify

```sh
npm run build
npm test
npm run test:e2e
```

The Playwright suite requires the API/database running and a Chromium browser (`npx playwright install chromium` if needed). CI in `.github/workflows/milestone-2.yml` starts a fresh PostgreSQL 17 service, applies schema/seed/migration, builds and exercises the live .NET API, builds/tests Angular, then runs desktop, tablet and mobile Playwright flows with zero retries. `scripts/verify_live_api.py` checks catalog endpoints; `scripts/verify_checkout.py` checks transactions and concurrency against real PostgreSQL. CI uploads screenshots, Playwright HTML report and API log.

## Architecture and API

- `src/app/features/checkout`: standalone Angular checkout screen, Signals cart, typed bilingual copy and focused unit tests.
- `src/app/core/services`: typed HTTP repositories for catalog and checkout.
- `services/merchant-api`: ASP.NET Core minimal API and Npgsql transaction code.
- `db/init` and `db/migrations`: catalog seed and versioned checkout schema.
- `public/products`: original local SVG product-category illustrations.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Database health |
| `GET /api/products?search=&category=` | Catalog search/filter |
| `GET /api/products/{id}` | Product detail |
| `GET /api/categories` | Categories |
| `GET /api/inventory/{productId}` | Current stock |
| `POST /api/checkout` | Atomic demo sale |
| `GET /api/orders` | Recent orders |
| `GET /api/orders/{id}` | Receipt |

Checkout accepts product IDs/quantities, an allowed discount (0, 5 or 10), cash tender or a deterministic simulated card scenario, and an idempotency key. The server ignores any frontend price assumptions. Discount and VAT are rounded separately to the nearest halala, half up. Failed payments leave inventory unchanged. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for verified checks and limitations.

## Milestone5 administration API

[Management contracts](docs/management.md): Administrator-only product editing, transactional inventory adjustments and immutable audit history. Angular remains cashier-only and contains no editing controls. Names/category/price can change; existing IDs/SKUs and receipt snapshots remain unchanged. Apply additive migration005 after identity004; never reset populated data. CI verifies real authorization, concurrency, idempotency and audit rollback. Security PR#3 is merged. Management [PR#4](https://github.com/danishirfan21/MerchantOS-POS/pull/4) stays unmerged pending review; Admin PR#6 pins its tested backend.
