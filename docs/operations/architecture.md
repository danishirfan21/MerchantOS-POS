# Security operations architecture and trust boundaries

M9 extends the existing two repositories. POS owns identity and transactional security events; Admin adds only sanitized operational metrics and shared workflow compatibility. No business screens, financial arithmetic or inventory transaction semantics change.

| Boundary | Mechanism | Limit |
|---|---|---|
| App runtime → database | Existing POS/Admin roles; added runtime identity-transition guard | POS remains the identity authority; compromise of its identity DB credential is serious, not solved by these controls |
| Operator → identity authority | Dedicated `merchant_identity_operator` connection, existing CLI authorizations/case UUID; connection mounted only for the command | Human identity verification/approval must be assigned; flags do not prove organizational authorization |
| Database → audit exporter | AFTER INSERT trigger queues safe event JSON in the same transaction; sequence/cursor + advisory lock | A database owner can rewrite unexported records; delivery latency is an exposure window |
| Exporter → retained audit objects | TLS/SigV4 S3, conditional writes, checksum readback, exact object retention headers, retry-safe deterministic batch names | Real provider permissions/retention/durability require external verification |
| Retained objects → witness | SHA-256-linked canonical batches plus CMS-signed independent checkpoints; pinned verification certificate | Witness key/checkpoint must be outside app/DB/exporter administration; a locally rewritable hash chain is insufficient |
| Backup writer → storage | Public-certificate CMS encryption, exact-version receipts, conditional S3 writes, readback verification | Encryption alone is not origin authentication; recovery requires an independently signed receipt |
| Storage → recovery operator | Separate reader credentials, pinned witness certificate, separately mounted decryption key | No normal runtime/writer/witness needs the backup private key |
| Collector → alerts | Aggregate-only metrics/DB view, durable ordered firing/resolved queue, TLS receiver with separate token | Real operator routing and staffing are not supplied by CI |

## Identity and delivery failure semantics

The trigger adds an outbox record for every security event, including operator commands and restore quarantine. The trigger and original event/state transaction commit together. A local event/outbox insertion failure aborts the critical identity transition, as the retained M8 rollback tests verify. A remote audit outage does **not** grant access or skip MFA: identity operations can commit with their durable local event/outbox record while export retries independently. HTTP requests never wait for an external audit destination.

The exporter holds its own transaction/advisory lock, reads up to 100 pending events in sequence order, uploads a deterministic batch, verifies it, then commits delivery/cursor state. A crash after upload but before commit retries the same bytes/key; `If-None-Match` plus SHA-256 readback suppresses duplicate logical delivery. Sequence gaps from rolled-back PostgreSQL sequence allocations are valid; event order is strictly increasing, not assumed contiguous. The security-event insertion lock preserves commit ordering. Pending rows are never age-pruned. Owner maintenance removes at most 1,000 delivered rows older than 90 days; runtime/exporter cannot delete them.

Checkpoint verification checks signature, pinned signer, batch hashes, parent links, event schema, sequence ordering and duplicate IDs. `--previous` requires a new checkpoint to extend the last independent checkpoint. An exporter can be configured with `minimumCheckpoint` and `witnessCertificate` to refuse a cursor rollback/fork. After a database restore, compare the restored export cursor against that independently retained checkpoint before resuming delivery. Investigate discrepancies; do not silently reset the trust anchor.

OpenSSL CMS performs the signatures. `-nointern -certfile <pinned cert> -noverify` uses only the explicitly pinned verification certificate, not attacker-supplied embedded certificates. It verifies the signature without public-CA validation; historical signatures remain verifiable after certificate expiry. Custody, revocation and approval of trusted certificate rotation remain separate controls. There is no trusted timestamp authority or claim that compromised source systems emit truthful events.

## Threats that remain

A storage administrator/provider failure may defeat an implementation that only reports Object Lock. Real enforcement must be tested independently. AWS-style COMPLIANCE semantics protect retained versions, but delete markers can hide latest objects and equivalent S3 implementations differ. Backup receipts preserve exact version IDs. Audit tampering/missing objects fail verification; recovery of retained versions requires authorized storage administration and comparison against the independent checkpoint.

Writers receive no deletion permissions. `policies/` contains **templates**, not evidence that an actual provider policy has been installed. A compromised app host must not share recovery/witness keys or storage-administrator credentials. CI separates interfaces/private paths and destroys the original app environment, but all fixtures run on one CI host. It does not establish geographic independence, off-host durability, human custody or immutable retention by a real external provider.
