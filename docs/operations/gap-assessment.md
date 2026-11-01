# M9 baseline gap assessment

Verified baseline: POS main 239bd2be64b86226756b391e685b191337aec661 and Admin main 7804d7975d8783cc2346b570e95bb69a07adc5e5. All five post-merge workflows passed; no pre-existing M9 branches/PRs were found.

| Control | Baseline classification | M9 priority |
|---|---|---|
| Transactional checkout, inventory, reports, MFA/revocation | Implemented and independently exercised in real CI | Preserve all suites and financial modules |
| CMS encrypted DB backup, protected key rings, isolated restore | Implemented/verified, single-host custody/storage | S3 interface, scheduling, separate recovery mount and fresh-host drill |
| Security events | Transactional, append-only to runtime; owner can rewrite | Transactional outbox, independent retained batches and separately signed checkpoints |
| Health, correlation and metrics | Implemented, no actionable external delivery | Minimal collector, durable alert state and configurable receiver |
| Ownership/custody/escalation | Not staffed or externally verified | Role matrix, incident drills and explicit organizational gates |
| Release scans | Actual images scanned; one high staging exception | Fresh upstream/advisory check, exact-image scans; no automatic extension |
| Production infrastructure/durability | Disposable single-instance staging only | Continue NO-GO pending genuine external evidence and human approval |

No paid infrastructure, real merchant data, public deployment, invented operators or additional identity authority is authorized. Local S3/receiver fixtures demonstrate protocol behavior, not independent durability or live on-call routing.
