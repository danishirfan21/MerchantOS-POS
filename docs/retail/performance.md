# Reproducible performance evidence

Measurements are CI observations, not production performance guarantees or a load/SLA certification. Each `performance.json` records exact source revision, viewport, Node version, runner OS/CPU/memory, fixture size, concurrency, method and raw samples. Main browser tests use a warm running API/database/dev server and fresh browser contexts; product filtering is client-side over 30 fictional products. Build/startup time is excluded. Shared runner scheduling and network overhead can affect results.

POS baseline `b0fe1865`, run 41374373280, before UI fixes:

| Viewport | Catalog + session load (one observation, ms) | Search p50 / p95 (10 samples, ms) |
|---|---:|---:|
| Desktop 1440×900 | 243.0 | 6.3 / 15.3 |
| Tablet 768×1024 | 336.0 | 9.6 / 25.5 |
| Mobile 390×844 | 237.2 | 5.7 / 15.4 |

Based on these observations, generous **test-environment smoke budgets** are initial catalog under 3,000ms and warm search p95 under 250ms. They detect gross regressions, not optimization wins. Final runs assert these limits and retain all raw samples. No performance improvement is claimed: UI corrections were for correctness/accessibility.

The POS lost-response test separately records one actual committed checkout response time. Receipt rendering has a wait-for-visible completion assertion, not a fabricated latency percentile. Cart update completion is asserted through rendered quantities/totals. Admin records browser navigation to Overview/products/inventory/page-16 Orders, ten authenticated historical sales-report requests (p50/p95), and one filtered CSV response. Its deterministic separate historical fixture contains 10,000 completed multi-item orders plus store-date/status/currency boundaries; the ordinary demo stays 30 products with organically created demo sales. Existing reporting CI retains actual PostgreSQL query-plan evidence (`report-query-plan.json`).

Admin pre-presentation-change observations (`ee66f6a4`, run 41375205198): desktop navigation Overview/products/inventory/orders 122.7/74.8/85.2/69.1ms, report p50/p95 17.0/19.7ms, CSV 12.3ms; tablet 114.8/73.2/72.8/61.9ms, report 16.8/17.2ms, CSV 11.2ms. Mobile measurement was not produced because the initial test selected a hidden desktop row; the test now selects the visible responsive card and reruns. Derived generous smoke budgets: each navigation <2,000ms, report p95 <500ms, one CSV <2,000ms. These budgets investigate gross regressions, not real-world capacity.

Final observed values are attached in the final CI artifacts and evidence manifest; an absent measurement is unverified. A single navigation/checkout/export observation is not a percentile. No new cache, stale inventory shortcut or financial/query-model rewrite was justified. Production-scale concurrency, constrained mobile hardware, cold CDN/TLS navigation, sustained resource/CPU/memory profiling, real WAN/mobile networks and multi-instance operation remain untested. Run representative load and independent usability sessions before setting operational budgets.
