# Milestone 10 isolated demo release candidate

M9 is merged: POS `f2298f72c9fa980593271e7ab1c07ac674f3fac5`, Admin `df58922b2ff69d94cf2848bee9c195d13cfec019`. All six M9 post-merge workflows passed, including 369 HTTPS and 51 operational assertions. M10 is a new review candidate; its PRs remain unmerged until explicit approval.

An exact M10 revision is an **isolated demo GO** only after all integration/security/operations/HTTPS/credential-audit checks pass, the documented launcher is exercised, screenshots are reviewed and no critical/high core-demo blocker remains. Pending or failed checks mean candidate NO-GO. Generated operational readiness remains authoritative within its scope; product validation adds evidence, not a bypass.

**Public production: NO-GO.** Real off-host durability/immutable retention, independent custody/witnesses, live alert routing/on-call staffing, organizational approvals and the remaining staging-only go-jose/v3 exception are not resolved by UX tests. Existing exception expiry is 2026-12-01, unchanged. Preserve [the operational release policy](../operations/readiness.md).

This candidate contains source commits, lockfiles/prerequisites, `deploy/demo.py`, the unchanged fictional catalog plus separate deterministic reporting fixtures, generated native accounts with mandatory MFA, a practical walkthrough, actual screenshots and auditable test results. No public deployment, tag, GitHub Release or automatic merge is created.

Acceptance limitations: independent cashier/manager/evaluator participation pending; screen reader and hardware printer untested; same-tab pending-sale storage is not cross-device/offline reconciliation; real payments/refunds and large-scale/performance SLA unimplemented. The CI browser uses isolated loopback HTTP for the full UI suites; the separate real HTTPS recovery and demo-launcher checks exercise TLS/configuration. Do not describe every screenshot as an HTTPS browser capture.
