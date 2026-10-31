# Milestone 7 readiness evidence

Decision pending final container/recovery and supply-chain evidence. Public deployment is blocked.

| Capability | Status | Evidence / boundary |
|---|---|---|
| Native authentication and roles | Verified | Existing security regression CI retained; POS remains identity authority. |
| HTTPS and proxy trust | Partially verified | Real container drill implemented; final run required. Local CA only. |
| Durable Admin sessions | Partially verified | Encrypted PostgreSQL native ticket store implemented; final restart/restore drill required. |
| Key protection | Partially verified | Native certificate-encrypted persistent rings; startup fail-closed tests pass. Container rotation/recovery pending. |
| Secret isolation | Partially verified | Random file-mounted credentials; masked CI values; credential audit gates operational log uploads. Docker host remains trusted. |
| Migration safety | Partially verified | Ordered/checksummed ledger, session advisory lock, per-file transaction; concurrent/replay/rollback drill pending. |
| Backup and restore | Partially verified | Encrypted dump, checksum manifest and isolated-target restore; executed final drill pending. |
| Health and readiness | Verified locally | New .NET tests distinguish live/ready, enforce mandatory staging configuration; real outage recovery pending. |
| Logging and metrics | Partially verified | Safe structured route/method/status/duration/category and correlation implemented; process-local Meter/counters. No historical collector/alerts. |
| Restart/failure recovery | Partially verified | CI drill implemented; no final pass claimed until executed. |
| Dependency security | Partially verified | Digest/action SHA pins and lockfile npm install; unsuppressed npm/NuGet/Trivy scan results pending review. Scan execution success is not vulnerability clearance. |
| Functional regressions | Verified | POS run 41240185882 and Admin run 41240244620 passed full existing suites plus new operational tests. Final-head rerun required. |
| MFA | Not implemented | Public deployment blocker; requires reviewed enrollment and recovery design. |
| Account recovery | Partially verified | Gated operator password/session/role/disable commands; no self-service recovery or verified emergency operator ownership. |
| Public production | Blocked | Local staging evidence does not establish public readiness. |

Local tests: POS 31/31 (28 existing + 3 operational); Admin 61/61 (58 existing + 3 operational). Existing CI behavior is not reduced: 21 Angular unit/21 POS browser, 3 template/94 Admin browser, 383 reporting assertions on 10,000 historical orders, 99 management and 39 security checks.

Initial POS CI identified a malformed-request 400 converted to 500 by the new operational boundary; fixed and unchanged management assertions then passed. Initial staging CI identified unquoted tmpfs mount commas; fixed. A later ephemeral database fixture raced PostgreSQL's temporary initialization server; readiness now probes the authenticated host TCP connection rather than the temporary Unix socket. Failed runs are not counted as passes.

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
