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

The API is demo-only without authentication and must not be exposed publicly. Simulated card processing stores no card details. No real gateway, refunds, multi-store management, hardware printing or advanced reporting. Product illustrations are stylized by category rather than exact manufacturer photography. Tablet and mobile screenshots are browser captures, not a claim of exact Stitch parity.
