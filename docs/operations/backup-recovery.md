# Backup, custody and disaster recovery runbook

## Installation and configuration

Use the supported operator image (PostgreSQL 17 client, OpenSSL, checksum-locked boto3/psycopg) or install the matching PostgreSQL 17 tools and reviewed locked Python environment on the backup host. Do not use an older pg_dump against PostgreSQL 17. The normal POS/Admin images contain no backup/recovery credentials or decryption key.

Keep configuration in private 0600 JSON files and mount them read-only. No credentials in images, Git, command arguments, URLs or logs. Use separate files/principals for backup writer, audit writer, recovery reader and witness reader. Each S3 configuration has:

```json
{"endpoint":"https://storage.example.invalid","region":"us-east-1","bucket":"OWNER_CONFIGURED_BUCKET","prefix":"PURPOSE_NAMESPACE","accessKeyId":"FROM_PRIVATE_SECRET_SOURCE","secretAccessKey":"FROM_PRIVATE_SECRET_SOURCE","caBundle":"/run/secrets/storage-ca.pem","retentionDays":30}
```

Optional `sessionToken` supports temporary credentials. TLS, explicit CA trust and SigV4 are mandatory. URL userinfo/query strings are rejected. Credentials are read from the specified private file rather than discovered from a cloud account. The deployment owner must provision and independently verify versioning, Object Lock, writer/reader policies, lifecycle and storage-admin access. The adapter refuses an unsupported provider; it does not emulate immutability using file permissions.

A private backup job configuration contains `stateDirectory`, `spoolDirectory`, `encryptionCertificate`, `storageConfiguration`, optional `protectedKeyDirectories` (`pos-keys`/`admin-keys` only), and `databaseEnvironment` with PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSFILE. Use `merchant_backup`, which has read-all-data and no write/superuser authority. PostgreSQL passfiles must be 0600. Protected-key archives include encrypted XML only; the private wrapping certificate/password require a separately protected recovery bundle/interface.

Run one controlled cycle:

```sh
python deploy/operations/backup_job.py run --config /run/secrets/backup-job.json
```

Install `deploy/systemd/merchantos-backup.service` and `.timer` on a reviewed backup host. CI parses the calendar and executes successive cycles/overlap/failure tests; it does not claim that a real host timer has been installed. The default timer runs daily at 02:00 UTC with at most 60 seconds jitter; override OnCalendar in a reviewed drop-in. The unit uses a private /tmp tmpfs, restrictive filesystem access, non-root account, bounded execution and control-group shutdown. Adjust explicit capacity limits after testing representative data. A bare host invocation without the private tmpfs/unit does not provide the same plaintext-temp protection.

`flock` prevents overlapping cycles on one host. Native commands and S3 operations have bounded timeouts/retries. Success is recorded only after exact-version ciphertext readback and retention-header verification. An interrupted cycle remains `running` and becomes an alert after 15 minutes; it cannot produce an acknowledged verified receipt. Completed uploads are idempotent; `.partial` files are never uploaded. A failed cycle remains observable, and the next scheduled cycle retries operation without overwriting prior objects.

## Retention and backup integrity

Single-object uploads are streamed and bounded to 5 GiB. Larger objects require a separately reviewed multipart implementation; this is not a production capacity claim. Receipts record SHA-256, byte count, object key/version ID, upload-verification time and COMPLIANCE retain-until time. CMS-encrypted dumps and separately encrypted protected dependencies are the only backup payloads sent to S3; no plaintext database dump leaves private temporary storage.

Requested remote lock periods must be 30–90 days. Retry verifies the existing object's original retention period rather than falsely extending its age. Local spool cleanup removes only known, successfully uploaded objects older than seven days after checking their retained remote version metadata. Unverified/failed uploads are retained locally and require capacity monitoring. The direct M7 backup CLI retains its seven-day local behavior; use the upload worker for remote-aware retention.

Lock duration is not an automatic object-lifetime cap. The writer never deletes remote objects or changes bucket policy. The storage owner must set and test a legally appropriate lifecycle/max-lifetime policy. Audit chains must not be lifecycle-deleted before independent archive/checkpoint recovery has been reviewed: deleting an ancestor makes full-chain verification fail. Do not claim indefinite audit verification after automatic pruning, or immutable storage from a local read-only file.

## Independent witness and recovery-key custody

The encryption certificate is public. The backup private key is generated once into the controlled recovery-material interface; normal app/backup containers do not mount it. A witness signs receipts using a **different** private key kept outside application/exporter administration. The witness independently reads and hashes every receipt object before signing:

```sh
python deploy/operations/witness.py backup-checkpoint --storage /run/secrets/reader.json --document /private/approved-receipt.json --certificate /custody/witness.crt --private-key /custody/witness.key
```

Retain receipt, detached `.p7s` signature and pinned public verification certificate independently. Never copy the decryption/signing private keys into the app spool or routine artifacts. Generate public inventory with `key_inventory.py --certificate backup-encryption=/path/public.pem --output inventory.json`; additional purposes are data-protection, audit-witness and tls. Inventory does not assign a human custodian.

Assign separate backup/recovery and witness custodians, access approvals, break-glass handling and a second-person verification procedure before production. Keep old backup private keys for all retained encrypted backups. Keep old Data Protection keys and wrapping certificates/passwords until retained data has been reprotected or its recovery obligations expire: MFA secrets outlive sessions. On rotation, inventory public fingerprints, test old/new recovery, approve the new pinned witness certificate independently, and preserve historical verification certificates. Never erase old material because a session expired.

## Protected dependency bundle interface

For controlled custody packaging, `recovery_bundle.py create --config /custody/bundle.json --output /private/new-dependencies.cms` streams a CMS envelope without a plaintext tar file. Its private JSON specifies posKeys, adminKeys, wrappingPfx, wrappingPasswordFile, wrappingPublicCertificate and encryptionCertificate. It rejects unprotected/symlinked ring material and mismatched PFX/public certificates. Run this under approved custody, not as the normal backup writer; do not include the backup decryption key.

Include the encrypted bundle in the independently signed receipt. Recovery uses `recovery_bundle.py extract --bundle /private/dependencies.cms --private-key /custody/backup.key --receipt /custody/approved-receipt.json --witness-certificate /custody/witness.crt --output /private/new-dependencies`. It verifies the signature/checksum before decrypting, permits only bounded regular whitelisted entries and never copies the recovery private key. Bind recovered rings and wrapping dependencies only after approved integrity checks.

## Retrieve and restore

1. Incident commander approves isolation and identifies an independently retained signed receipt/checkpoint. Verify its provenance, storage version IDs, selected backup time and expected recovery gap.
2. On a fresh isolated recovery host, provide read-only reader credentials, the pinned witness certificate, and the approved receipt/signature. Download verifies the signature **before** accepting objects and streams checksum validation:

```sh
python deploy/operations/backup_job.py retrieve --storage /run/secrets/reader.json --receipt /custody/approved-receipt.json --witness-certificate /custody/witness.crt --output /private/new-download
```

3. Mount the backup private key only for the controlled restore job. Missing key/signature/corrupt data is a hard failure. Never substitute an unverified newer object/version.
4. Use `restore.py` with a fresh `merchant_restore_*` target and `--confirm-isolated`. It refuses an existing target, verifies ciphertext, performs atomic pg_restore, validates/applies checksummed migrations and quarantines every restored identity. No automatic destructive replacement of a running database is authorized.
5. Recover protected DP XML and its wrapping PFX/password through the approved encrypted recovery interface. Rebuild images from the verified source revisions; generate fresh application TLS certificates and trust. Compare deterministic business/identity/MFA/audit hashes and security-event counts before reconciliation.
6. Follow the retained MFA runbook using the dedicated `operator_connection`, explicit recovery/MFA-reset/restore-release flags and a case UUID. Verify each person's current account status independently of the old backup. Disabled accounts remain disabled; all unreconciled identities remain blocked. Reset credentials/factors/codes and revoke sessions/challenges before release.
7. Compare audit-export state against the independent minimum checkpoint. Resolve any fork/rollback through incident review; never silently discard retained audit history.
8. Start services, validate readiness/TLS/MFA, verify old cookies/codes fail, run authenticated catalog/receipt/report/CSV and idempotent checkout/inventory smoke checks, and deliver alert resolutions. Preserve bounded nonsecret evidence.

Lost private key means the encrypted backup cannot be recovered by this design. Escalate to approved independent custody; do not add a decryption bypass or an unprotected convenience copy.

## Measured versus proposed objectives

CI reports backup creation, upload, download, restore, app startup, identity reconciliation and full-environment recovery durations in `operations-results.json` and `disaster-recovery-results.json`. The full drill deletes the original app work directory and PostgreSQL volume, rebuilds fresh images/volume, retrieves encrypted objects from a separate TLS S3 fixture and recovers protected dependencies through the fixture custodian interface.

Proposed planning targets are RPO 24 hours and RTO 60 minutes, subject to representative-volume tests, scheduling safety margin and staffed custody/approvals. Daily scheduling/jitter/failure periods do not themselves guarantee a 24-hour RPO. CI image rebuilds may reuse Docker layer cache; timings exclude real human response, clean-machine build costs and external-provider latency. Production RPO/RTO remain **uncommitted**. No WAL archival, PITR, HA or distributed recovery is implemented.
