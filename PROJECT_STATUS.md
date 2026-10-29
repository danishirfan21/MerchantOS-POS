# MerchantOS POS – Project status (29 October 2026)

## Milestone 2: PostgreSQL catalog and typed REST API integration

**Status: Implementation prepared; integration verification blocked by environment. NOT yet verified complete.**

### Code delivered

- .NET 10 ASP.NET Core minimal API and EF Core/Npgsql PostgreSQL context.
- Two relational tables: products and inventory_levels, constraints against negative prices/stock, unique SKUs, one-to-one FK.
- Initial local SQL schema and 30 seeded electronics catalog products with stock values.
- Docker Compose local PostgreSQL and ASP.NET Core service, health check and API ports.
- Read-only `/api/health`, `/api/products` (optional search/category), `/api/products/{id}`, `/api/categories`, and `/api/inventory/{productId}` endpoints.
- Angular ProductRepository using typed `HttpClient` and local `/api` development proxy.
- Checkout catalog now loads from API with loading, error and Retry states; no silent hardcoded fallback.
- Cart reconciliation when API refreshes product prices/stock or removes products.
- Two additional cart tests for stock/price refresh and unavailable products.
- `docs/MILESTONE_2.md` with Windows runbook, API contract and QA checklist.

### Verified in this execution environment

- Python/SQLite **seed contract check passed**: 30 unique products, 30 inventory rows, foreign-key joins, nonnegative price/stock constraints, and repeatable upsert.
- All 10 frontend TypeScript files parsed with **zero syntax errors** using TypeScript parser (syntax only, not a full Angular compilation).

### Not verified (must not claim passed)

- Actual ASP.NET Core `dotnet build` (no .NET SDK available here).
- Actual PostgreSQL data initialization or live API HTTP responses (Docker not installed here).
- Angular `npm ci`, production build or Vitest (dependencies unavailable and network DNS fails).
- New 12-test cart suite (tests written but not executed in this environment).
- Browser/Playwright flows and Stitch comparison (existing Milestone 1.5 visual QA gap remains).

### Critical local QA steps

See `docs/MILESTONE_2.md`: `docker compose up -d --build`, check endpoint results, `npm ci`, `npm run build`, `npm test`, and browser verification. Correct any compilation or behavioral issues before designating Milestone 2 complete.

### Scope kept out of Milestone 2

- Authentication, permissions, payments, refunds, checkout transaction processing, orders, receipts, stock decrements, multi-location inventory, admin editing.
- Production migrations/secrets: initial SQL bootstrap is for fresh local Docker volumes only; use formal migrations before schema updates or deployment.

## Milestone 1 / 1.5 baseline (previous Work report)

- Angular standalone frontend with responsive catalog/cart, RTL toggle, cart pricing in integer halalas and 15% VAT.
- At the end of Milestone 1.5, Work reported production build passed and **10/10 unit tests passed**.
- Browser QA was blocked because Chromium download returned an invalid ZIP; it was not visually verified.
- Earlier demo buttons that had no behavior were disabled/labeled.

## Work verification update — 29 October 2026

Status remains **incomplete pending live API/database and browser verification**.

Executed in this workspace:
- `npm ci`: passed (255 packages installed).
- `npm run build`: passed, Angular production output generated.
- `npm test`: 12/12 tests passed across 2 files.
- `python3 scripts/verify_catalog_seed.py`: passed, 30 products and 30 inventory rows in the SQLite seed contract check.

Changes:
- API health endpoint now returns HTTP 503 for database connection exceptions instead of an unhandled server error.
- Windows QA script now asserts category filtering, Sony search, product detail price/stock, and 404 for unknown product IDs.

Blocked here:
- `dotnet`, Docker, PostgreSQL, and Chrome/Chromium/Edge binaries are absent. Therefore the ASP.NET Core project was not compiled, PostgreSQL was not started, HTTP endpoints were not exercised, Angular-to-API communication was not confirmed, and browser screenshots/tests were not run. This is not a fully verified Milestone 2.
- On a Windows machine with Docker Desktop and Node installed, run `powershell -ExecutionPolicy Bypass -File scripts/qa-windows.ps1`, then perform browser flows and viewport captures listed in `docs/MILESTONE_2.md`.

## CI verification prepared — 29 October 2026

- Added `.github/workflows/milestone-2.yml`: Ubuntu, .NET 10, Node 24, PostgreSQL 17 service, schema/seed load, API build/start, live endpoint assertions, Angular build, 12 unit tests, Playwright Chromium install and desktop/mobile browser smoke. CI uploads Playwright screenshots, report and API log even on failure.
- Added `scripts/verify_live_api.py` and `e2e/catalog.spec.ts`; these execute against live services in CI.
- Locally reran Angular build and unit suite: passed, 12/12 tests. The CI workflow, .NET build, PostgreSQL integration and browser tests have **not run** here.
- The GitHub repository is connected at danishirfan21/MerchantOS-POS. Milestone 2 remains pending a successful GitHub Actions run and review of its artifacts.
