# Ownership and incident response

Every real owner/escalation path below is **unassigned/unverified**. Defining a role or running a fixture does not staff operations.

| Responsibility | Required role | Technical mechanism | Real owner / escalation |
|---|---|---|---|
| POS/Admin availability | Service operator | readiness, aggregate metrics, TLS alerts | Must be assigned and tested |
| Database health/backups | Database/backup operator | read-only backup role, locked job, receipts, age/failure alerts | Must be assigned and tested |
| Recovery private keys and protected dependencies | Independent recovery custodian | recovery-only mount, encrypted dependency bundle, public inventory | Must be assigned; independent custody/approvals pending |
| Independent audit verification | Witness custodian / audit reader | signed checkpoints, pinned certificate, reader credentials | Must be assigned outside app/exporter administration |
| Security incidents/MFA recovery | Incident commander + identity operator | revocation, case UUID, separately gated CLI and DB role | Identity verification and approval path pending |
| Vulnerability exceptions | Vulnerability reviewer | exact-image reports/SBOM, release gate, expiry alert | Accountable review/decision cadence must be staffed |
| Certificate renewal | Certificate custodian | inventory, expiry alerts, controlled rotation | Must be assigned and tested |
| Staging/recovery approval | Deployment/recovery approver | isolated confirmation, deterministic integrity checks | Real approval not supplied by CI |

## Access boundaries

- POS runtime owns native authentication transactions but cannot perform role/disable/active-MFA-reset database transitions. Dedicated identity-operator commands use a separate mounted connection; normal app containers receive no such file.
- Admin session runtime can access its durable ticket table only, not the outbox or operator state.
- Migration/database owner performs schema/role/retention administration. `merchant_backup` has read-all-data only, no superuser/write authority.
- `merchant_security_exporter` reads queued safe events and updates delivery/cursor columns only; it cannot change payloads or delete rows. `merchant_audit_reader` can read security events/export state. `merchant_monitor` reads aggregate view only.
- Backup/audit writers have distinct purpose-restricted storage credentials; recovery/witness readers have no object-write/delete permission. Provider policy templates require review/application by the storage owner; real IAM enforcement remains unverified.
- Backup-decryption and witness-signing keys are never app/backup-writer mounts. Key-management configuration stays on read-only app filesystems/secret mounts. Host/database/storage administrators remain privileged trust boundaries.

## Incident exercises / response sequence

| Incident | Detect/alert | Contain → recover → validate | Evidence / human approval |
|---|---|---|---|
| Backup failure | BackupFailed/Overdue; safe job status | Preserve unuploaded spool; fix capacity/trust/config; bounded retry; verify receipt/signature and restore | Backup operator approval; save safe status and object version IDs |
| Lost app host | Availability + stale backup/audit signals | Isolate old host credentials; rebuild fresh environment; approved encrypted retrieval and protected-dependency recovery; reconcile identities; smoke test | Incident commander + separate key custodians; CI simulates app-directory/volume loss, not physical off-host durability |
| Database loss/corruption | Readiness/DB/5xx | Isolate writes; approved fresh-target restore; schema/hash checks and identity quarantine; only then reconcile/start | DBA and recovery approval; preserve original media/snapshots where appropriate |
| Compromised Admin session | Privileged activity/MFA signals | Revoke sessions/challenges; verify impact; change credential/factor with separate approvals if needed; validate stolen cookies fail | Security responder; preserve signed/event evidence, never copy cookies to reports |
| Suspicious MFA recovery | PrivilegedSecurityEvent | Confirm case independently, revoke suspicious access; contain operator credentials; follow recovery runbook | Incident commander + verified person/identity operator approval |
| Audit destination outage | AuditBacklog/SignalsUnavailable | Keep durable queue; restore destination/exporter; verify retries/cursor/checkpoint continuity | Audit operator; preserve pending count/age, no queue deletion |
| Missing encryption key | Restore fails closed | Stop recovery; locate approved independent custody; no bypass or new key pretending to decrypt old data | Recovery custodian approval; key inventory/fingerprint only in ordinary evidence |
| Expired/untrusted certificate | Certificate/availability alerts | Isolate unsafe transport; approved renewal/trust rotation; retain required old decryption/verification material; repeat TLS smoke | Certificate custodian; record public fingerprint and tested validity |
| Release gate failure | ReleaseVulnerability/ExceptionExpiry | Block release; fix supported dependency/rebuild; retain all findings; repeat gate and HTTPS regression | Vulnerability reviewer; explicitly justified exceptions, no automatic extension |
| Interrupted checkout/DB outage | DB/5xx/checkout alerts | Recover service; query/retry with original idempotency key; verify one order/payment/stock deduction | Service/DB operator; preserve correlation ID and business-safe result, never create duplicate financial writes |

CI performs destructive recovery only against its freshly generated disposable directories, databases and volumes under a CI-only guard. No runbook authorizes automatic destructive recovery against a live installation. Proposed RPO/RTO, retention/legal obligations and on-call escalation require the deployment owner's organizational review.
