# MerchantOS POS

Angular 22 cashier application + read-only ASP.NET Core 10 / PostgreSQL product and inventory API. The UI remains based on the approved Google Stitch design. Milestone 2 replaces its hardcoded catalog with live database results; checkout and payment processing are **not implemented**.

## Requirements

- Docker Desktop (for ASP.NET Core API and PostgreSQL)
- Node.js 24.15+ and npm 11+ (for Angular)

## Quick start (Windows PowerShell)

```powershell
docker compose up -d --build
curl.exe http://localhost:5080/api/health
curl.exe http://localhost:5080/api/products
npm ci
npm start
```

Open `http://localhost:4200`. Angular proxies `/api` to `http://127.0.0.1:5080` in local development, so the frontend uses relative API URLs. If the API is offline, the product area displays an explicit error and Retry button instead of showing fabricated inventory data.

## Build and tests

```powershell
npm run build
npm test
python scripts/verify_catalog_seed.py
```

The Angular cart test suite from Milestone 1.5 is preserved and extended with catalog reconciliation coverage. **Milestone 2 runtime/build verification is still pending** because the implementation environment lacked a .NET SDK, Docker and working network access. Do not treat these commands as already passed.

## Backend endpoints

- `GET /api/health`
- `GET /api/products` (optional `category`, `search` query)
- `GET /api/products/{id}`
- `GET /api/categories`
- `GET /api/inventory/{productId}`

Product prices are integer halalas; the database holds products and separate per-product stock levels. Local PostgreSQL database initializes 30 products from `db/init/*.sql`. Stock is **read-only** in this milestone.

## Layout

- `src/app/core/services/product.repository.ts` – typed Angular API repository
- `src/app/features/checkout` – responsive Stitch-inspired POS, cart and totals
- `services/merchant-api` – .NET 10 minimal API + EF Core/Npgsql
- `db/init` – initial local schema and repeatable seed
- `docker-compose.yml` – local database and API containers
- `docs/MILESTONE_2.md` – endpoints, verification checklist, constraints and outstanding work
- `PROJECT_STATUS.md` – progress and test claims

The credentials in Docker Compose and API configuration are strictly for local development. Supply secure secrets and reviewed migrations before deployment. There is no authentication, payment, or inventory write endpoint yet.

## Local completion check

Run `powershell -ExecutionPolicy Bypass -File scripts/qa-windows.ps1` from the repository root on Windows with Docker Desktop and Node 24.15+. This builds and starts the API/database, checks live endpoints, installs Angular dependencies, builds the UI, and runs unit tests. Then open `http://localhost:4200` for browser verification. The script does not perform browser visual QA.

## GitHub Actions integration verification

Push this repository (including `.github/workflows/milestone-2.yml`) to a GitHub repository with Actions enabled. The workflow runs on push, pull request or manual `workflow_dispatch`; no database secrets or external paid services are needed for this local-demo CI. Open the **MerchantOS Milestone 2** run, confirm all steps pass, and download `merchantos-browser-artifacts` for desktop/mobile screenshots, browser report and API log. The workflow uses a PostgreSQL 17 service and executes the seed scripts explicitly; it does not use Docker Compose.

## Milestone 3 demo checkout

Apply `db/migrations/003_checkout.sql` once to existing PostgreSQL volumes; it uses `CREATE TABLE IF NOT EXISTS` and retains the product catalog. The CI workflow applies it after the initial seed. The checkout endpoint accepts cash or deterministic simulated card outcomes; no real card details are used. Prices, discounts (0, 5 or 10%) and VAT are computed on the server in integer halalas, rounding each discount/VAT to the nearest halala (half up). Inventory rows are locked in product ID order inside a transaction; idempotency keys serialize retries. This demo API has no authentication and must not be publicly exposed.

Docker Compose now runs the versioned checkout migration in a one-shot `migrate` service before starting the API. It is safe to rerun against the existing named volume; it does not delete products or inventory. Run `docker compose up -d --build` after pulling this branch.
