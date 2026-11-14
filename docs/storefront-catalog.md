# Storefront catalog API (read-only)

A narrow, customer-safe, **read-only** catalog for the MerchantOS Storefront's server-side (BFF) requests. It is separate from the staff catalog: `/api/products`, `/api/inventory/{id}`, `/api/categories`, checkout, orders, management and reporting keep their existing policies and are unchanged.

**Scope and status.** Disabled by default. Intended only for an approved isolated integration environment. Public production remains NO-GO under [operational readiness](operations/readiness.md). Not a payment, checkout or order surface.

## Enabling

| Setting | Default | Meaning |
|---|---|---|
| `Storefront:Catalog:Enabled` | `false` | When false the routes are not mapped. |
| `Storefront:Catalog:RateLimitPerMinute` | `300` | Fixed-window limit per remote address (1-6000). All Storefront traffic comes from one server, so keep it generous. |

The existing transport rules still apply: HTTPS everywhere, except development loopback HTTP when `Security:AllowLoopbackHttp=true`. No CORS is configured; the Storefront calls this API server-side only.

## Routes

`GET /api/storefront/products?search=&category=&page=&pageSize=` and `GET /api/storefront/products/{slug}`. Anonymous (explicit `AllowAnonymous`), GET only, rate limited. Anything else is refused by the deny-by-default fallback policy or antiforgery.

Validation: `search` at most 64 characters with no control characters; `category` a lowercase slug; `page` 1-1000 (default 1); `pageSize` 1-50 (default 12); `slug` lowercase letters, digits and single hyphens, at most 64. Invalid input returns `400 {"code":"invalid_request","message":...}`; unknown or unpublished product `404 {"code":"not_found"}`; database failure `503 {"code":"catalog_unavailable"}` with no details; rate limit `429`.

## Public contract (the complete allow-list)

```json
{ "slug": "iphone-15-pro", "name": "iPhone 15 Pro",
  "category": { "slug": "smartphones", "label": "Smartphones" },
  "priceHalalas": 429900, "currency": "SAR", "vatTreatment": "excluded",
  "availability": "in-stock | low-stock | out-of-stock" }
```

The list wraps items as `{ items, page, pageSize, total }`. `priceHalalas` is an integer (SAR x 100) and **excludes VAT**: POS unit prices are ex-VAT and checkout adds 15%. Availability is derived from `inventory_levels.quantity_on_hand` (0 or less: out of stock, 1-5: low stock, otherwise in stock). Never exposed: SKU, internal product id, quantities, versions, Arabic name, badge, colour, icon, cost or audit data.

Success responses carry `Cache-Control: public, max-age=30`; errors are `no-store`. Reads run in a `READ ONLY` transaction and never write.

## Publication mapping (temporary)

`Storefront/StorefrontCatalog.cs` holds an explicit server-side map of five POS products (private POS id, public slug, public category). Price and stock are never copied into it. Slugs are chosen explicitly, never by matching Storefront fixture ids. A later change is expected to replace this with an additive public-catalog table. A published product missing from the POS tables is omitted, never invented.

## Tests

`services/merchant-api.Tests/StorefrontCatalogTests.cs`: disabled-by-default, field allow-list, slug and query validation, pagination and search bounds, availability and price mapping, 503 sanitisation, cache headers, rate limiting, GET-only, HTTP refusal, staff endpoints still 401, exactly two new anonymous routes, unchanged staff policies, and (when `STOREFRONT_TEST_DB` names an isolated, disposable database) price/stock parity with PostgreSQL, an unchanged-data fingerprint, and a sanitised 503 for an unreachable database.
