> M9 operational addition: [backup/recovery](operations/backup-recovery.md), [access/incident responsibilities](operations/ownership-incidents.md), [audit trust boundaries](operations/architecture.md). Operator account commands now use the dedicated identity-operator connection; private recovery material is outside normal app mounts. Earlier milestone evidence remains historical.

# Milestone 8 MFA and account recovery

POS is the sole identity authority. Admin remains a server-side BFF over the same PostgreSQL database. No browser role or MFA flag grants authority. Administrator MFA is mandatory in Development and Staging as well as production configuration. Cashiers retain password sign-in; recovered Cashiers must replace their temporary credential through the POS sign-in screen before checkout.

## Administrator enrollment and sign-in

On a trusted device, open Admin over the existing private HTTPS edge and submit your assigned username/password. A successful password creates only a five-minute restricted challenge. It cannot authorize Admin business screens or direct administrative POS APIs. For a new Administrator, scan the locally generated QR with a standard authenticator or enter the displayed key: TOTP/SHA-1, six digits, 30 seconds. Confirm a valid code before the factor becomes active. The key is shown once per challenge; cancel/restart if it was lost before confirmation. Never screenshot or share enrollment material. Initial credentials require verified handover: an attacker who steals them before first enrollment could enroll their own factor.

Save the ten recovery codes offline, separately from the password and authenticator. They appear only in the enrollment response and cannot be retrieved later. Each is a random 256-bit second factor stored only as a SHA-256 verifier. A recovery code still requires a valid primary-password challenge. It is not a password reset. Ordinary sign-in accepts a current six-digit authenticator code or one unused recovery code. Invalid/expired challenges can be cancelled and restarted. An accepted TOTP time step and consumed challenge/code cannot be redeemed again, including concurrent submissions.

POS limits skew to one 30-second step each way. Challenges expire after five minutes, permit at most five failed factors and are replaced by a new primary login. Five factor failures lock MFA for five minutes; successful primary-password validation does not reset that counter. Separate IP/user rate limits apply. Full sessions have an absolute 30-minute expiry and a database security version/MFA timestamp. Restarts do not renew them. Session theft remains a risk despite MFA; cookie and host protections still matter.

## Account security

Select your username in Admin to open account security. Password changes require the current password, a different 14–128 character replacement and authoritative MFA within five minutes. Sign in again if verification is older. Every POS session and pending challenge is revoked, including the current Admin session. Recovery regeneration requires the current password and a fresh, unused authenticator code; it replaces all old recovery verifiers, revokes every session/challenge and displays the new batch once. Keep it safe before returning to sign-in.

## Operator-assisted recovery

There is no anonymous reset endpoint or email dependency. An authorized operator must independently verify the person's identity and account status, record an incident/case UUID outside the application, and obtain separate authorization for password recovery versus authenticator loss. Do not treat possession of a username or an application cookie as sufficient evidence. Two-person approval and assigned custody are organizational production requirements, not an automated identity-verification claim.

Use the existing controlled `pos-api --account` operation over a private, short-lived operator container. Supply usernames and temporary credentials through mode-0600 secret files mounted read-only; never put credentials in command arguments, URLs, shell history or logs. Required configuration for password recovery is `Operations__AllowAccountCommand=true`, `Operations__AllowRecovery=true`, `Operations__OperatorCase=<case UUID>`, `Account__Operation=recover`, `Account__UsernameFile=<private path>`, `Account__PasswordFile=<private temporary credential path>`. The native password hasher is retained. This revokes sessions/challenges, forces a different password before access, and preserves the existing MFA factor/codes.

For verified authenticator loss, authorize a separate `mfa-reset` operation with `Operations__AllowMfaReset=true` and the case UUID. It removes the encrypted active factor, resets replay/lockout state and invalidates recovery verifiers, sessions and challenges. The next Administrator sign-in must complete fresh enrollment. If both password and factor were lost, perform separately authorized password recovery and MFA reset. Neither operation silently enables disabled accounts. Remove operator flags and secret mounts immediately afterwards. Never mount these authorizations in normal app services.

The controlled `mfa-seed` command is for first-time verified operator enrollment/isolated CI provisioning only. It requires explicit `AllowMfaEnrollment`, a private new Base32 secret, a matching live TOTP confirmation, and a new absolute private recovery-output file. It cannot replace an active factor. Normal users enroll through Admin. CI runs real confirmation and one-use factor redemption; there is no Administrator MFA test bypass.

## Restore reconciliation

The supported restore tool creates a fresh isolated `merchant_restore_*` database, applies current migrations and quarantines **every** restored identity. Restored credentials, sessions, challenges and codes cannot authorize access while blocked, even if a backup predates revocation. Preserve the protected key rings/certificates separately for encrypted-data recovery; MFA secrets now outlive sessions, so old decryption keys/certificates cannot be removed merely because all sessions expired.

Verify business-data hashes and account status before cutover. For each verified person, owner-authorized `restore-recover` requires `AllowAccountCommand`, `AllowRecovery`, `AllowMfaReset`, `AllowRestoreRelease` and the case UUID, plus a private owner connection file and temporary credential. It revokes restored sessions/challenges, rotates the security version, removes old MFA/recovery verifiers, forces password replacement and releases only that person's restore block. Disabled status is preserved. All other users remain quarantined. The Administrator then enrolls a new factor and receives new codes; Cashiers replace temporary passwords. Old backup recovery codes and session cookies fail. A raw manual database restore outside this tool does not provide these guarantees and is not the supported recovery procedure.

## Security events and retention

`security_events` records a UUID, UTC time, fixed category/outcome, actor/target UUIDs and a normalized correlation UUID only. Categories cover restricted primary authentication, MFA enrollment/failure, recovery redemption/regeneration, successful authentication, password changes, logout, operator operations and restore quarantine. Critical state transitions and event writes commit together; a failed event write prevents authentication completion. No passwords, secrets, OTPs, QR content, recovery material or cookies are stored in events.

POS runtime has SELECT/INSERT on events; it cannot UPDATE/DELETE them. Admin ticket runtime has no event-write permission. Authorized Administrators can read the newest 100 via `/api/admin/security-events`; it is a bounded security view, not an export/analytics service. `deploy/security-retention.py` is an explicit database-owner maintenance task deleting at most 1,000 events older than 90 days per invocation. Schedule and custody must be assigned before production. Database owners can alter records; this is not immutable/off-host audit storage.

## Verification and release scope

Keep complete unsuppressed npm/NuGet/Trivy evidence. Collection and staging-policy enforcement are separate steps. The narrow expiring go-jose v3 exception is specified in `deploy/security-policy.json`, tied to the reviewed Caddy configuration, owner and isolated scope; a newly available fix, expiry or changed configuration fails the gate. It does not approve public deployment. See dependency review and staging-readiness documents for exact executed evidence, residual vulnerabilities and production blockers.

Never upload active enrollment QR screenshots, browser storage state, traces, recovery output, key archives or database backups. New browser enrollment screenshots mask the entire sensitive region. CI uses disposable identities and private temporary files, with retries disabled and artifact screening before upload. Do not infer a completed check from a test's existence.
