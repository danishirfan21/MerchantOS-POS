# Milestone 8 — review candidate, isolated staging evidence

Both Milestone 7 PRs are merged. Milestone 8 remains unmerged and has no public deployment. Read [MFA/recovery and restore reconciliation](mfa-recovery.md), [threat model](identity-threat-model.md), [dependency review](dependency-review.md) and the [operations runbook](staging-operations.md).

## Executed evidence

- POS `a99238d330a63f17a4b79eadaa461f75a9520b35`: [integration 41295184232](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41295184232), 47 .NET, 72 real PostgreSQL identity assertions, 21 Angular, 24 browser, 383 reporting, 99 management and 40 direct security checks.
- Admin `f108ebbae3d0acc341d2149bfa4cba61b67021cb`, pinned POS `a99238d330a63f17a4b79eadaa461f75a9520b35`: [integration 41295285449](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41295285449), 68 Admin .NET, all 109 browser cases (94 retained +15 MFA), checkout/catalog, 383 reporting, 99 management and 40 security checks; credential audit passed.
- Same Admin/POS pair: [real HTTPS recovery 41295285442](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41295285442), [audited results and five-image scans](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41295285442/artifacts/13077969702), **283 assertions passed**. Original M7 operational scenarios are retained; identity restore expectations are tightened to quarantine and explicit reconciliation. Copied pre-restore cookies also fail after reconciliation.
- [Responsive MFA screenshots and full 109-case browser evidence](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41295285449/artifacts/13079385271): desktop 1440×900, tablet 768×1024 and mobile 390×844. Enrollment QR/key region is masked. The empty-validation-summary refinement is included in these screenshots.

These links identify executed revisions, rather than implying every later commit has been tested. Before marking the PRs ready, all integration, security and staging checks must pass at their latest heads and Admin's exact POS pin must match the verified backend. Final-head links and commit SHAs belong in the PR descriptions.

| Area | Verified behavior / scope |
|---|---|
| Administrator authority | Password creates a restricted five-minute challenge; direct administrative APIs remain unauthorized until backend MFA succeeds. Legacy password-only Admin sessions fail closed. |
| TOTP/enrollment | Otp.NET, RFC vectors, six ASCII digits, ±one 30-second step, encrypted per-user pending/active secrets, confirmation before activation, local QR, one-time display. |
| Replay/concurrency | Actual PostgreSQL user/challenge locks, monotonically accepted TOTP step, concurrent factor/code redemption exactly once, challenge expiry/replay rejection. |
| Recovery/passwords | One-time high-entropy hashed recovery verifiers, rotation invalidates old codes/sessions, current-password checks, recent backend MFA, forced temporary-password replacement, separate operator authorizations and case UUID. |
| Atomic security events | Credential/factor changes and critical event writes share transactions; injected event failure rolls back factor consumption and session issuance. Safe fixed field contract; runtime roles cannot alter/delete events. |
| Durable sessions and keys | Full and pending Admin tickets remain server-held and encrypted, POS authority revalidated; permitted restarts preserve absolute expiry. Key rotation and protected-ring recovery retain decryption dependencies. |
| Restore | Current schema plus all restored identities quarantined. Original business/auth/audit snapshots compared before reconciliation; business hashes preserved afterwards. Old sessions/codes fail; disabled status stays disabled. Separate per-person owner reconciliation required. |
| Operational regression | Original service/full-stack restarts, kill during checkout, DB outage/liveness/readiness, same-key exact-once checkout/inventory retries, migration concurrency and rollback, encrypted dump/key recovery, ciphertext swap, expiry, logout/stolen cookies, role/disable/password revocation, forwarded-header trust and throttling retained. |
| Business/browser regression | Original Admin 94 cases retained; 15 real MFA scenarios added across three viewports. Reporting formulas, checkout arithmetic and inventory transaction modules unchanged. |
| Container gate | Exact staging-built image IDs/layers scanned before application startup. Unsuppressed reports retained; separate high/critical gate with narrow expiring unfixed go-jose v3 exception. Nine policy regression tests. |
| Artifact hygiene | No active QR screenshots, traces/storage state/recovery files/key archives/dumps uploaded. Known credentials/factors, cookie patterns, enrollment URIs and private material screened before upload. |

## Readiness decision and production blockers

**GO only for isolated, disposable, single-instance HTTPS staging with the passing revision's exact images/configuration. Public production is BLOCKED.** A green collection job alone does not pass the security gate or approve deployment.

- One unfixed `github.com/go-jose/go-jose/v3` high finding remains, individually reviewed only for the pinned private Caddy surface until 2026-12-01; medium/low/unknown findings remain in reports. Apply a fix when available and refresh scans before any release.
- Assign independent identity verification, operator authorization/approval ownership and recovery custody. Initial-enrollment credential theft remains a bootstrap risk. No anonymous/email password reset or phishing-resistant WebAuthn is implemented.
- Database owner/host compromise can alter audit or identity authority. Off-host immutable security-event collection, alerting and on-call ownership are not implemented. Owner-only bounded 90-day retention requires an assigned schedule.
- Assign offline key/certificate custody, off-host backups, backup-failure alerts and restore cadence. MFA decryption keys are long-lived dependencies; session expiry does not make old keys disposable.
- Supported topology is one instance on one trusted host. Rate limits are process-local; multi-instance/distributed throttling, HA, PITR/WAL recovery and sustained load/SLA validation are outside scope.
- PostgreSQL remains on the private host bridge; remote database transport/TLS and public ingress/certificate/operational threat review require separate work.
- Session cookie theft remains relevant despite MFA. No real payment processing, refunds or cloud deployment is added.
