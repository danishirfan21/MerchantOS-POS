> M8 readiness is pending final-head verification. The M7 evidence below is a historical baseline, not approval of the changed MFA/restore implementation. Public deployment remains blocked. See [MFA recovery controls](mfa-recovery.md).

# Milestone 7 readiness evidence

**GO for isolated, single-instance localhost staging using disposable demo data. Public production: BLOCKED.** No public deployment or merge was performed.

Verified runtime commits: POS `1238815f38e848716491dce0d9a3c6ae72e536bd`, Admin `ee653aa1faf81ba9d9621be67ca76733e609a9fa`. Admin CI pins that exact POS feature commit. Later documentation-only updates retain this runtime pin.

- [POS regression CI](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41243400068)
- [Admin regression CI](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41243440542)
- [Real HTTPS Compose recovery drill](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41243440548), [audited results/logs](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41243440548/artifacts/13058004439)
- [POS package/image scan](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41243400011), [Admin package/image scan](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41243440648)

| Capability | Status | Executed evidence / boundary |
|---|---|---|
| Authentication and authorization | Verified | Native real-user suites retained; staging administrator/cashier boundaries, disabled users, expiry, password/session revocation and logout exercised. POS remains authoritative. |
| HTTPS and proxy security | Verified | Real local-CA validation on edge and backend hops; secure cookie attributes, external-host redirects, direct untrusted forwarding rejection and spoofed-XFF throttling checked. |
| Durable Admin sessions | Verified | PostgreSQL protected tickets survive Admin/API/proxy/DB/full-stack restarts and actual restored-database cutover. Per-reference cryptographic purpose rejects copied ticket ciphertext. Absolute expiry is unchanged. |
| Key protection and recovery | Verified | Native certificate encryption, private mounts, encrypted XML assertions, rotation with old cookies, fail-closed missing configuration and protected-ring restore with explicit permissions. Wrapping certificate remains a separate offline recovery dependency. |
| Secrets | Verified | Random file-mounted credentials; separate runtime DB roles; fail-closed artifact audits including outage logs. No dumps, cookies, private certificates or keys uploaded. Docker host remains trusted. |
| Migration safety | Verified | Fresh installation, populated replay, concurrent advisory locking/checksums and failed-file atomic rollback; no reseeding/data loss. |
| Backup/restore | Verified | Real encrypted custom dump restored into a new isolated DB; all fields compared across 11 business/auth/audit/idempotency tables. Apps then use restored DB/rings and existing unexpired cookies. Off-host disaster recovery remains operator work. |
| Liveness/readiness | Verified | Separate process/dependency status; real DB outage gives live 200/ready 503; readiness and valid-session access recover. |
| Logging/correlation | Verified | Safe structured app logs, normalized/forwarded correlation ID observed in both services, filtered proxy failure metadata and error-parameter suppression; upload audit passes. |
| Operational metrics/monitoring | Partially verified | Administrator-protected process counters/duration and native Meter; safe per-route logs. No persistent collector, alert delivery or on-call ownership. |
| Restart/failure recovery | Verified | All service and full-stack restarts, forced API kill during checkout, DB outage, bounded same-key retries and exact-once stock/order behavior. Expired-record cleanup also exercised. |
| Dependencies/supply chain | Partially verified | Maintained action SHAs, digest-pinned bases, npm lockfile and complete npm/NuGet/Trivy reports. npm advisories fixed; remaining image findings documented in dependency-review.md. Green scan execution does not clear vulnerabilities. |
| Functional/responsive regressions | Verified | 31 POS .NET, 21 Angular, 21 POS browser; 61 Admin .NET, 3 templates, 94 Admin browser; 383 reporting checks on 10,000 historical orders, 99 management, 40 security checks (all prior 39 retained). |
| MFA/self-service recovery | Not implemented | Public blocker. Gated operator password/role/disable/revoke commands exist; no insecure public recovery endpoint introduced. |
| Public production | Blocked | No public exposure authorized; remaining security/operations controls below are required. |

The full staging drill passed **176 assertions** with real Docker/PostgreSQL/HTTPS on an isolated GitHub Actions Ubuntu runner. Docker was unavailable in the editing environment, so no local container execution is claimed. Four additional artifact-auditor tests exercise secret/key/dump rejection and embedded-report decoding. No existing meaningful assertion or authentication boundary was removed.

## Small-fixture timing observations

The recovery artifact records three samples per read/edit operation and one checkout, under the Compose 512 MiB/one-CPU app limits. Median milliseconds: authentication 78.05, catalog 7.86, product edit 17.28, inventory adjustment 18.09, reporting 17.29, historical page 7.00, CSV 6.78; one checkout 31.62. This is a smoke timing observation, not sustained load capacity or a production SLA. The independent reporting regression uses 10,000 historical orders.

## Corrected failures found during verification

The unchanged management suite caught malformed requests becoming 500 instead of 400. Container runs caught malformed tmpfs syntax, Caddy executable capabilities conflicting with cap-drop, missing ingress reachability and an external-host redirect issue. Outage testing exposed stale pooled database connections; these now report safe 503 and bounded same-key replay succeeds. Proxy failure metadata was removed after the credential audit blocked it from upload. Restore testing retained the startup permission check and fixed archive-restored directory modes rather than bypassing it. A clock-dependent test fixture was aligned with the Saudi store date without changing financial/date formulas. Harness-only cookie attribute casing and cookie snapshot issues were fixed; the final complete run passed.

## Public deployment blockers and limitations

- MFA, verified password recovery/enrollment and operator access ownership/approvals are absent.
- Single instance only. Fixed container names enforce the supported topology. Rate limits/metrics reset on app restart; no distributed rate state or distributed coordination is claimed.
- TLS certificates are local, short-lived and manually renewed. No public domain, certificate automation or exposure approved.
- Off-host backups, offline recovery-key custody, scheduled backup failure alerts and restore cadence require an assigned operator. No external monitoring destination or on-call ownership configured.
- Dependency/image findings must be reviewed at the exact build and advisory date. No blanket vulnerability-free claim. Mutable APK repositories prevent byte-identical source rebuilds; retain reviewed built image digests.
- Recovery point is last validated backup; no continuous WAL archival/HA/PITR. RTO is measured only by the disposable drill, not a production commitment.
- Payments remain the existing simulated cash/card flow. Real payment processing/financial compliance is outside this milestone.
- Security/account operator actions print completion but do not create an immutable external security audit trail; business audit history remains database-backed and unchanged.
- Health endpoints check required objects/connectivity, not every schema permission or semantic invariant. Run the serialized deployment migrator before startup.

- PostgreSQL transport relies on the isolated host/internal bridge; remote database/TLS deployment is not implemented.
