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

## Executed M10 retail observations

POS `cc8a11fe2d39e3aa02bfb860ae5a36c839fef3b4`, [run 41380882492](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41380882492), four-vCPU Ubuntu runner, about 15.6GiB RAM, concurrency one:

| Viewport | Initial catalog ms (one) | Search p50 / p95 ms | Cart increase+decrease p50 / p95 ms (10 round trips) |
|---|---:|---:|---:|
| Desktop | 365.14 | 9.02 / 12.48 | 99.74 / 125.90 |
| Tablet | 361.16 | 7.35 / 12.81 | 99.78 / 126.07 |
| Mobile | 338.28 | 7.76 / 12.30 | 99.93 / 142.15 |

Observed checkout request timings were 12.4–18.6ms (one per viewport, not a percentile). Final timing JSON additionally records retry-to-visible-receipt duration (includes HTTP retry and Playwright visibility polling), browser-reported approximate JS heap/DOM size and sampled/peak disposable API process RSS. These are scoped process observations, not sustained production resource profiling. A controlled request barrier verifies processing/disabled feedback while the browser request is stalled; it uses no arbitrary sleep to pass a test.

Admin `debf6292147518fa8c18322ad1a38aa5661804b3`, [run 41379963932](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41379963932):

| Viewport | Overview/products/inventory/page-16 orders ms (one each) | Historical report p50 / p95 ms (10 requests) | CSV ms (one) |
|---|---|---:|---:|
| Desktop | 156.92 / 91.89 / 91.84 / 86.39 | 21.24 / 22.41 | 14.76 |
| Tablet | 145.98 / 88.79 / 89.75 / 83.34 | 20.45 / 23.25 | 13.96 |
| Mobile | 147.33 / 99.38 / 94.60 / 85.59 | 20.86 / 22.91 | 13.50 |

All scoped budgets passed in these runs. Initial-load observations vary from the earlier baseline; one navigation sample and differing test scheduling do not establish an optimization or a sustained regression. No performance improvement claim is made. Use final PR-head artifacts for the latest samples and investigate repeated threshold breaches before acceptance.
