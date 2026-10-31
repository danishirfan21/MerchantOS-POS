# Isolated staging operations (Milestone 7)

## Scope and assessment

This is a single-instance, operator-managed localhost staging topology, not a public production release. Baselines: POS `7adf607567666d2d9fbbe8549a3d56663263384e`, Admin `151e7d9a5f5aef47c1c22dc841cc0b26d0a5c741`. Existing merged PRs remain history.

Before this change Admin tickets existed only in memory; process restarts lost sessions. Neither app explicitly provisioned an encrypted persistent key ring. Development HTTP and local service addresses were embedded in operating assumptions. The old Compose database had a known password and an incomplete migration chain. There was no verified encrypted restore, readiness distinction or unified safe request correlation. Those were correctness/recovery risks before any public deployment.

The implementation retains native POS database sessions and identity. A new table in the same database stores native ASP.NET serialized Admin tickets, encrypted by Data Protection, indexed by SHA-256 of a random reference. POS revalidation on every MVC request remains authoritative. No identity duplication or new distributed service. Both apps have separate key rings and application names; keys use native certificate encryption. Key creation lifetime is 30 days; authentication lifetime remains absolute 30 minutes, never renewed by restart or reads. Transient backend failure returns a safe failure without deleting a valid ticket. Real revocation/expiry rejects it.

## Prerequisites and boundaries

Linux with Docker Engine, Compose v2, Python 3 and OpenSSL; .NET 10/Node 24 for source tests. Clone the two reviewed feature commits into sibling `MerchantOS-POS` and `MerchantOS-Admin` directories. Record exact Git commit IDs and `deploy/images.json` with your installation record. Dockerfiles pin base-image digests; npm uses lockfiles. OS package repositories used by APK remain mutable, so image bytes are not claimed to be identical across rebuilds. Keep built images by digest for an exact rollback.

Only `127.0.0.1:8443` (POS), `:9443` (Admin), `:8080` and `:9080` (redirects) are published. PostgreSQL and both apps have no host ports. The internal network is `172.29.70.0/24`; change both Compose and trusted-proxy configuration together if it conflicts with an existing network. Caddy additionally joins a dedicated ingress bridge for the loopback-published listeners; database/apps remain exclusively on the internal network. Fixed app container names intentionally prohibit scaling. Do not remove this restriction or expose the listeners publicly.

Runtime apps and Caddy are non-root, read-only, capability-free, constrained to 512 MiB/one CPU with private tmpfs and 30-second shutdown. PostgreSQL uses its image-supported entrypoint privilege drop and a persistent named volume. Operator migration/backup containers have privileged database credentials; run only on a trusted operator host. The runtime POS role cannot alter schema or edit audit rows; Admin session role has only SELECT/INSERT/DELETE on its ticket table. Docker host access is equivalent to access to secrets.

## Provision and start

Run from the POS repository. Use a fresh private directory outside source control; never overwrite an installation's material. Replace the example home path with a private path for your account.

```bash
python3 deploy/init-local.py --output "$HOME/merchantos-local-staging"
export STAGING_DIR="$HOME/merchantos-local-staging"
export ADMIN_CONTEXT="$(realpath ../MerchantOS-Admin)"
alias mc='docker compose --env-file "$STAGING_DIR/staging.env" -f deploy/compose.yml'
mc config --quiet
mc build
mc up -d db
mc run --rm migrate
mc up -d pos-api admin web
mc ps
```

The generator uses random credentials, an isolated local CA, short-lived local TLS certificate, a private Data Protection PFX and an offline backup recovery key. Private files use 0600; directories use 0700. Protect the parent directory too. It never obtains a public certificate. Runtime gets selected files only; the CA private key and backup private key are not mounted into normal services. Move offline recovery material to a separately protected offline copy after validating recovery; `BACKUP_PRIVATE_KEY_FILE` selects that offline key for restore.

Do not execute `down --volumes` on an installation you want to preserve. Normal shutdown is `mc down`. Back up keys and the database before changing images or migrations.

To populate demonstration products on a completely fresh disposable database only, run `SEED_DEMO=true mc run --rm migrate` (or export `SEED_DEMO=true` before the command). Default is no seed. The migrator only seeds on its first fresh schema creation; it does not recreate a database or reseed populated data. For an established environment, first take and restore-test a backup, stop writes, run the migration container, then bring apps up and check readiness. The owner role is separate from both runtime roles. A single PostgreSQL advisory lock serializes migration runners; each file and checksum-ledger insert commits atomically. Existing pre-ledger additive migrations are replayed using their existing idempotent DDL. A changed recorded checksum fails. Never edit an applied migration: add the next numbered file. A failure rolls back the current file; inspect the ledger before resuming. Earlier committed migrations are retained.

Trust only this installation's `secrets/ca.crt` in the test browser, or use `curl --cacert`; do not disable TLS validation. Do not install the private CA on unrelated machines. HTTPS is verified on both the browser-to-edge and edge-to-app hops. Admin validates its POS backend against the local CA and exact backend hostname. Both apps accept forwarded headers only from Caddy's fixed address; Caddy overwrites client forwarding claims. No arbitrary proxy trust.

```bash
curl --cacert "$STAGING_DIR/secrets/ca.crt" https://localhost:8443/api/health/live
curl --cacert "$STAGING_DIR/secrets/ca.crt" https://localhost:8443/api/health/ready
curl --cacert "$STAGING_DIR/secrets/ca.crt" https://localhost:9443/health/ready
```

Liveness is dependency-independent. Readiness verifies database connectivity and required objects; Admin additionally requires its ticket store and POS readiness. Readiness is not a full schema checksum check: the deployment migration ledger is mandatory. Responses contain no connection details. Missing mandatory operation settings, private certificate, password or protected key directory fails startup; staging cannot use the development HTTP exception. `AllowedHosts` is explicit. Containers also have readiness health checks.

## Provision identities and verify workflows

No default administrative account is created. On the isolated staging host, use an authorized one-shot POS account command. The generator creates private example username/password files; read them locally with a password manager or protected editor, never put values in command lines, issue descriptions or CI artifacts.

```bash
mc run --rm --no-deps -v "$STAGING_DIR/secrets:/operator:ro" \
  -e Operations__AllowAccountCommand=true -e Account__Operation=create \
  -e Account__UsernameFile=/operator/admin_username \
  -e Account__PasswordFile=/operator/admin_password \
  -e Account__Role=Administrator pos-api --account
```

Repeat with cashier files and `Account__Role=Cashier`. Roles are exactly Administrator or Cashier. New passwords require 14–128 characters; existing native PBKDF2 hashing is retained. Create refuses an existing username. Provisioning is not a public endpoint. Sign in at `https://localhost:9443/Account/Login` and `https://localhost:8443/`; verify Administrator management, Cashier checkout and Cashier rejection by Admin. Verify cookie Secure/HttpOnly/SameSite, sign out, refresh and restart. Preserve the three approved Admin viewports and bilingual POS workflow.

Account operations use the same command pattern: `Account__Operation=password` with private username/password files; `role` with username and Account__Role; `disable` or `revoke` with username only. Changes revoke that user's POS sessions transactionally. Admin rejects revoked sessions at its next backend validation. These are operator commands with no self-service recovery capability. Never grant command authorization to a normal running container. Disabled accounts cannot be re-enabled by this CLI: investigate first using a reviewed operator procedure.

## Monitoring and safe diagnostics

`mc logs --tail 200 pos-api admin web db` shows JSON application logs, safe route patterns, method, status, duration and correlation ID. A valid incoming GUID correlation ID is normalized; malformed IDs are replaced. Admin forwards correlation to POS using an HTTP handler. Caddy's global error encoder deletes request metadata and response headers, including CSRF values on upstream failure; PostgreSQL suppresses error parameters/statements. No request bodies, query values, cookies, authorization values, passwords or CSRF tokens are deliberately logged. Built-in verbose HTTP logs are suppressed. Do not enable sensitive logging in staging.

Administrator-only `/api/ops/metrics` and `/ops/metrics` expose process-local status counts and cumulative duration. Native `MerchantOS.Operations` Meter records latency and request counts with route/status labels. Logs distinguish failure categories and expired-session cleanup counts. Use 401/403/429 for authentication/rate-limit signals, 409 for inventory conflicts and 5xx for failures; correlate with the route to distinguish checkout, reporting and database trouble. No external dashboard, historical store, alert service or distributed metric aggregation is installed. Set up an operator-owned collection/alert destination before public use. Counters reset on restart and do not establish an SLA.

Login throttling is single-process and keyed to the trusted source address. Forged client XFF cannot choose a bucket. POS users behind the same public IP share a bucket. Admin BFF logins share the Admin service source-IP bucket at POS; do not forward an untrusted browser IP to bypass this limit. Proxy restart preserves app counters; app restart resets process rate counters, while database account lockout/session revocation persists. Multiple instances and distributed throttling are unsupported. Cleanup removes at most 1,000 expired POS/Admin sessions per minute and never extends expiry; monitor backlog and provision capacity before higher load.

## Backup and actual recovery

```bash
mc run --rm --no-deps backup
# Select an existing ciphertext filename from the private backups directory.
mc run --rm --no-deps restore /ops/restore.py /backups/SELECT.dump.cms \
  --target merchant_restore_operator_drill --confirm-isolated
```

Backup uses custom-format pg_dump, checks its catalog and encrypts with OpenSSL CMS/AES-256 using a public recovery certificate. Plaintext exists only in private tmpfs. Final ciphertext has a SHA-256 manifest; retention removes encrypted backups older than seven days. A completed dump is not a successful recovery: manifest says restoreVerified=false until an operator records a separate drill. Restore checks ciphertext checksum, requires a `merchant_restore_*` database, refuses an existing target, decrypts using the offline private key and restores transactionally. Never use it to overwrite the operational database. Roles are cluster objects; provision runtime roles/grants for the restored DB with `PGDATABASE=merchant_restore_operator_drill mc run --rm migrate /ops/roles.py` via an explicit Compose `-e PGDATABASE=...` override if needed.

Store a second encrypted backup copy off the Docker host. Include the key rings, DP wrapping PFX/password, application-name configuration and offline backup private key in a separately encrypted, access-controlled recovery archive. A DB backup alone cannot recover encrypted tickets. Do not place these in CI artifacts. Schedule `deploy/backup-cron.sh` under your operator account with an absolute Compose environment, external `flock` to prevent overlap, and alert on nonzero status. Seven-day on-host retention provides no disaster recovery if the host is lost. No automatic scheduler/alert recipient is configured by this repository.

For a real cutover: stop API/Admin writes, preserve old installation, restore a fresh isolated target, compare row counts and canonical hashes for products, stock, orders, order items, payments, identity, audit, idempotency, adjustments and tickets. Restore matching protected key rings/PFX; provision grants; change the private connection files to the verified target; recreate app containers and verify readiness and old unexpired sessions. Record the backup timestamp and the data-loss interval. Never copy keys over a running writer. CI performs this drill only against disposable data and uploads hashes/results, not dumps or keys.

## Keys and incidents

Normal rotation: `mc run --rm --no-deps -e Operations__AllowKeyCommand=true pos-api --rotate-keys`, and repeat for `admin`, then restart consumers. Existing non-revoked keys remain for old cookies/tickets. Native automatic key rotation also uses the persistent protected directory. Back up the ring after rotation. Certificate rollover is separate: create a new private wrapping certificate, keep the old certificate/password available as `Operations__PreviousCertificatePath`, and protect newly generated keys with the current certificate. The configured current and previous PFX files currently use the same protected password file. Retain every certificate needed by retained keys; copying only a new certificate will not decrypt the old ring. Test rollover on a disposable copy before replacing mounts.

Compromise: disable/revoke the affected account first. For system-wide invalidation run explicitly gated `--revoke-keys` separately for POS and Admin, revoke POS database sessions through the approved operator process, restart consumers and require fresh logins. Key revocation invalidates cryptographic cookies/tickets; deleting key files is not a controlled revocation procedure. Lost wrapping private keys or ring files cannot be reconstructed. Restore a matching protected backup or revoke sessions and require all users to sign in again. Historical business data remains in PostgreSQL.

| Incident | Response and retry boundary |
|---|---|
| PostgreSQL outage | Observe readiness 503, preserve volumes/secrets, restore connectivity, wait for readiness. Liveness remains 200. No blind database recreation. |
| API/Admin outage | Inspect safe correlated logs and container health; restart the affected service, then verify readiness and session access. Do not delete keys. |
| Failed migration | Stop rollout/writes, inspect owner-only ledger/checksum and migration. Current transaction rolls back. Fix with a new reviewed migration; restore a disposable copy before retry. |
| Failed backup | Treat as no backup. Check disk, pgpass, database and encryption certificate; remove stale partial files after investigation, rerun and restore-test. Alert operator. |
| Authentication failure | Check clock, TLS validity, authoritative account/role/session and key permissions. Do not weaken cookies, CSRF or HTTPS. |
| Interrupted checkout | Result may be committed despite a missing reply. Retry the original payload with the SAME idempotency key and retrieve its receipt. A new key can create another sale. |
| Uncertain stock adjustment | Retain exact request and SAME adjustment idempotency key; query audit/stock. Do not generate another key to resolve uncertainty. |
| Reporting timeout | Retry the read with a bounded date/page range after dependencies recover. Do not replay administrative writes. |
| Compromised session/key | Revoke affected accounts/sessions, preserve safe incident evidence, rotate/revoke keys with operator authorization, verify fresh sign-in. |

## Verification and deployment gate

`deploy/verify_staging.py` is CI-only and intentionally mutates a **fresh** disposable directory/Compose project. It builds all four images, uses real validated TLS and PostgreSQL, verifies separate users, restarts all services, rotates keys, kills an active checkout, stops the DB, replays concurrent migrations, exercises failed-migration rollback and restores encrypted DB/key backups into an isolated database. It then runs the apps against that restored target. It always destroys only its own disposable volume. Never point it at an existing installation. See `staging-readiness.md` for executed evidence and unresolved gates.
