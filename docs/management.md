# Administrative write contracts (Milestone 5)

All `/api/admin` routes require the explicit ProductManagement, InventoryManagement or AuditRead Administrator policy. Cookie/CSRF and revocation checks remain enabled. Actor IDs come only from backend claims.

GET `/api/admin/products/{id}` returns editable names (English/Arabic), category, integer priceHalalas, product version, stock and stockVersion. No description/active fields exist in the schema; these are intentionally excluded. SKU/ID never change. Categories are the six existing catalog categories.

POST `/api/admin/products/{id}` accepts {name,nameAr,category,priceHalalas,version}; unknown JSON fields are rejected. Names 1–240 chars; positive price up to 100000000 halalas; optimistic version conflicts return 409. Catalog/new checkout reflect changes; receipt snapshots remain untouched.

POST `/api/admin/inventory/{id}/adjustments` accepts {operation,quantity,reason,stockVersion,idempotencyKey}. Operations restock/damage use positive deltas; correction quantity is an absolute nonnegative count. Reason 1–500 chars, key 1–128 chars. All operations require a matching stockVersion. A database trigger advances that version on every stock update, including checkout, preventing ABA/stale corrections. Identical actor-scoped retries replay the original result; changed payload/key reuse returns 409. The backend computes balances under the same inventory row locks as checkout.

GET `/api/admin/audit?entityId=...&action=...&from=...&to=...&page=1&pageSize=10` returns bounded items and hasMore; max pageSize50/page10000. Action product.updated/inventory.restock/inventory.damage/inventory.correction; UTC dates. Audit JSON contains only editable fields or stock values/reason, never credentials.

Migration005 preserves populated data, adds product/stock versions, immutable audit and adjustment records with indexes. Business changes and audit insertion share a transaction; audit failure rolls back the change. Triggers prohibit ordinary UPDATE/DELETE/TRUNCATE of audit/adjustments; database owners can still alter schema and must be controlled operationally.
