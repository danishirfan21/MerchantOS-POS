# Milestone 6 — historical reporting under review

Branch feature/historical-reporting-api; [PR #5](https://github.com/danishirfan21/MerchantOS-POS/pull/5) remains unmerged. Based on current verified main ad73c8e406fc1b42c8fdf4fd88b721d08f2ce320. Admin PR #7 pins the tested reporting revision.

Three read-only API routes provide SQL-filtered historical pages, one consistent sales analytics snapshot and bounded formula-safe CSV. Asia/Riyadh periods, financial formulas, offset consistency limitations, query/index behavior and export caps are documented in docs/reporting.md. No changes to checkout arithmetic, management locks, audit, identities, receipt access or Angular UI.

[Initial verified CI](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41231296851), head42e5aa6655cf99fd4b05942a59049543fb9c9172:28 .NET tests (16 retained),21 Angular unit,21 browser,383 reporting assertions on 10,000historical multi-item orders,99 management and39 security checks. Actual UTC/store boundary, VAT/discount/AOV, historical-price, page-tie ordering, role/session, CSV escaping/bounds and additive migration replay checks pass. Chronological index confirmed by EXPLAIN ANALYZE/BUFFERS; single-day aggregate 0.058 seconds on that isolated fixture, not a production guarantee. Query plan included in audited artifacts. Final-head evidence is linked in PR #5.

Milestone 5 POS PR #4 merged asad73c8e406fc1b42c8fdf4fd88b721d08f2ce320 and Admin PR #6 as61489430eff4a3843579ee08dba121128b36e8c0. Neither remains pending. No public deployment.

## Previous milestones (historical evidence)

# Milestone 5 — administrative write foundation

Branch feature/admin-product-inventory-api, based on verified mainab2b6397d36f3cd2c1597ccc50fbeb0c5a5d8ba5. [PR #4](https://github.com/danishirfan21/MerchantOS-POS/pull/4) merged; Admin PR #6 depends on its exact pinned revision. Product updates, inventory adjustments and bounded audit retrieval use explicit Administrator policies, existing native sessions/CSRF, version tokens, row locks and actor-scoped idempotency. Migration005 is additive/replay-safe; business changes and append-only audit are atomic.

Initial implementation4542bab2ada061be5d4fef8cd981b0c735bfda29 [passed CI](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41206002144):9.NET security,21 Angular unit,21 browser,88real management checks,39 security checks, checkout/idempotency/concurrency and credential audit. Further boundary tests/documentation are tracked with final-head results in PR #4.

Security PR #3 and Admin PR #5 are already merged. [POS post-merge CI](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41204394695) passed. No public deployment; existing production-security limitations remain. See docs/management.md and docs/authentication.md.

## Earlier milestones (historical verification)

# Authentication and authorization milestone

Branch `feature/auth-role-security`, based on POS main `68cc809edb2146e13632ff9cd316504b2dc5d25d`. Native ASP.NET Core cookie/password security, PostgreSQL identities/revocable sessions, explicit deny-by-default policies, cashier-owned receipts, scoped idempotency, CSRF, lockout and throttle implemented. Angular login/logout added. Local API/Angular builds and 21 existing unit tests pass. [Verified implementation CI](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41138325213) at `a594c3bd8b310dcd45864272295baf8e19b05163` passed: 9 native .NET security HTTP tests, 21 Angular unit tests, 21 browser tests (15 existing + 6 authentication), real catalog/checkout/idempotency/concurrency and 38 direct security/log checks. [Screenshots and reports](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41138325213/artifacts/13017955386).

The final documentation/security-verification commit additionally replays the identity migration against populated checkout data and checks that product count, stock and order totals remain intact. CI includes a fail-closed password/session-token artifact audit. The authenticated username and Sign out action are integrated into the existing POS header, preserving its original height. Final-head results are linked in [POS PR #3](https://github.com/danishirfan21/MerchantOS-POS/pull/3), which merged as ab2b6397d36f3cd2c1597ccc50fbeb0c5a5d8ba5. Admin integration is tracked in [Admin PR #5](https://github.com/danishirfan21/MerchantOS-Admin/pull/5) and must pin this final POS revision. No public deployment or automatic merge. See docs/authentication.md.

# MerchantOS POS — Project status

## Milestone 4: Visual QA and portfolio polish

**Integrated into `main` through merged PR #1 and PR #2.**

Milestone 4 adds complete English/Arabic UI copy for supported screens, RTL alignment and consistent SAR formatting; six original local SVG category illustrations used across 30 catalog products; explicit demo labels instead of fabricated shift and cashier metrics; dialog/cart keyboard focus and Escape/backdrop handling; responsive tablet/mobile sizing; and current README documentation. Checkout and database transaction logic remain unchanged.

[GitHub Actions PR run #40934104138](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40934104138) passed on commit `00ceb81`: PostgreSQL 17 seed/migration, .NET 10 API build and live catalog/checkout/concurrency checks, Angular production build, **21/21 unit tests** across four files and **15/15 Playwright desktop/tablet/mobile tests** with retries disabled. CI uploaded 1440×900, 768×1024 and 390×844 captures, receipt/cart/Arabic captures, Playwright HTML report and API log. The three English catalog captures were visually reviewed and added under `docs/screenshots`; Arabic mobile capture was reviewed after adjusting currency presentation to prevent narrow-card crowding. No horizontal overflow was detected in tested viewports.

The approved Stitch screenshot file was not accessible in this workspace. Visual review uses actual browser screenshots and the supplied design token/specification text; exact pixel parity with Stitch is unverified.

## Milestone 3.1 baseline

[PR #1 run #40928743649](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40928743649) passed PostgreSQL migration, .NET API/live checkout checks, Angular build, 20/20 unit tests and 6/6 desktop/mobile Playwright tests without retries. PR #1 was merged into `main` as `610b12f664d8ff3b04a0274c0a564bd045ce0885`.

## Milestone 2 baseline

[Run #6](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40807068324) passed PostgreSQL initialization with 30 products/inventory rows, live catalog API, Angular build, 12/12 unit tests and 2/2 browser tests. Earlier local environment gaps were superseded by CI.

## Integration and limits

PR #1 was merged first using a regular merge commit. PR #2 was retargeted to `main`, then [retargeted PR run #40937260128](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/40937260128) passed PostgreSQL/API checks, Angular build, 21/21 unit tests and 15/15 browser tests without retries. PR #2 was merged as `f579e11e8360e37b03f4c6a550328d9b1dfdbc94`. The final `main` workflow runs against the integrated commit, with results in GitHub Actions.

The API is demo-only with required authentication and must not be exposed publicly. Simulated card processing stores no card details. No real gateway, refunds, multi-store management, hardware printing or advanced reporting. Product illustrations are stylized by category rather than exact manufacturer photography. Tablet and mobile screenshots are browser captures, not a claim of exact Stitch parity.
