# Milestone 2: API-backed product catalog and inventory

**Scope:** Read-only ASP.NET Core + EF Core + PostgreSQL product/inventory service, with an Angular `HttpClient` catalog repository. Checkout payments, authentication, orders and inventory mutations are **not** in scope.

## Run locally (Docker Desktop + Node 24.15+)

From the repository root:

```powershell
docker compose up -d --build
docker compose ps
curl.exe http://localhost:5080/api/health
curl.exe http://localhost:5080/api/products
curl.exe http://localhost:5080/api/categories
curl.exe http://localhost:5080/api/products/p01
curl.exe http://localhost:5080/api/inventory/p01
npm ci
npm start
```

Angular serves on `http://localhost:4200` and proxies `/api/*` to the API on port 5080. The API uses a PostgreSQL database on localhost port 5433. Demo database credentials and ports are intentionally **local development only**; don't reuse them for any deployed environment.

The PostgreSQL Docker entrypoint executes `db/init/001_schema.sql` followed by `db/init/002_seed.sql` **only on a fresh named volume**. If the database volume already exists, changing these scripts will not update the existing database. Do not delete an existing volume to apply schema changes: introduce reviewed EF migrations instead. This initial schema bootstrap is for Milestone 2 local development, not production migration management.

## API contract

| Endpoint | Response |
|---|---|
| `GET /api/health` | 200 when the database is reachable; 503 otherwise |
| `GET /api/products` | Array of products, with stock from `inventory_levels` |
| `GET /api/products?category=Audio&search=Sony` | Filtered product array |
| `GET /api/products/p01` | Product or 404 |
| `GET /api/categories` | Names and product counts |
| `GET /api/inventory/p01` | `{ "productId": "p01", "stock": 8 }` or 404 |

Product contract is camelCase and matches `src/app/core/models/product.ts`. Money is sent in **integer halalas**, never floating-point SAR. Product `stock` is derived from the related inventory row; no stock updates are exposed yet.

The Angular catalog calls `/api/products` once on checkout initialization. Category filtering/search remain local reactive operations over the fetched 30 products; the API also supports server-side filters for later scale. If the API is unavailable, the UI shows an explicit failure with Retry. There is **no silent fallback to demo inventory**. Cart quantities are clamped if refreshed stock decreases or a product disappears.

## Verification still required

The packaging environment lacks the .NET SDK, Docker, a functional npm dependency install and outbound DNS access. Therefore **no successful API build, PostgreSQL integration run, Angular build or browser test is claimed** for Milestone 2. We ran only the dependency-free seed contract test.

On a machine with Docker and Node 24.15+, verify:

1. `docker compose up -d --build` successfully builds and starts both services.
2. `/api/health` returns 200 and `/api/products` returns 30 records.
3. `/api/products?category=Audio` and `?search=Sony` filter correctly; nonexistent IDs return 404.
4. `npm ci`, `npm run build`, and `npm test` pass; the cart suite should now include two catalog-reconciliation tests.
5. Browser: search, filters, RTL toggle, stock caps and cart calculations still work with API data.
6. Stop the API, refresh Angular, confirm the visible error/retry state; start the API and Retry.
7. Compare desktop/tablet/mobile screenshots with the approved Stitch designs. The browser-visual QA limitation from Milestone 1.5 remains open.

## Next milestone

Milestone 3 adds server-authoritative checkout, transactions, order line price snapshots, stock validation and reductions inside a database transaction, idempotency keys, receipt records and payment simulation. Do not treat current frontend total previews as a real payment result.
