# Production-readiness policy and evidence

`deploy/operations/readiness.py` consumes the actual operational integration result and complete HTTPS staging result. It emits a machine-readable decision, reviewed workflow revision, and control statuses. An absent/failed result or staging count below the preserved 283 baseline fails isolated staging. Artifact screening must pass before its input is marked credential-audited. Local success never sets real infrastructure/custody booleans.

| Control | Technical implementation / verification | External or organizational status |
|---|---|---|
| MFA, revocation, native identity | Existing M8 suites retained; runtime privileged-transition guard and limited monitor credential added | Initial credential handover/operator approval require real ownership |
| Encrypted backups/upload | CMS, streaming TLS S3, exact-version checksums/retention readback, bounded retries, non-overlap lock, verified-only spool retention | Real off-host storage, writer/reader policy and durability verification required |
| Recovery keys | Public-only encryption; private key only in recovery interface; signed receipt before download; inventory tool | Independent custodians, rotation/approval and off-site availability unassigned |
| Disaster recovery | Fresh PostgreSQL volume and app directory after destroying original; verified encrypted retrieval/protected dependencies, migrations, hashes, quarantine/reconciliation and smoke checks | Real provider outage/host loss, representative scale, staffed approvals and operational RPO/RTO unverified |
| Security audit | Transactional outbox, ordered retry/cursor, checksummed chain, independent pinned-certificate CMS checkpoint and anti-rollback checks | Genuine external retention and independent witness operation/custody unverified |
| Monitoring | Real readiness/database-outage collection plus rule simulations, durable TLS test-receiver delivery and resolution | Live operator receiver, on-call ownership and escalation path unverified |
| Supply chain | Digest-pinned images; runtime/test dependency locks, exact-image unsuppressed scans and CycloneDX SBOM, separate gate | Remaining go-jose/v3 high exception restricts scope to staging; no auto-extension |
| Operations | Practical service/timer and incident/ownership runbooks | Real service accounts, approvers, restore cadence and privacy/compliance review unassigned |
| Distributed operation/PITR/real payments | Not implemented; outside this milestone | No readiness claim |

Status vocabulary: `verified`, `partially_verified`, `not_implemented`, `requires_external_configuration`, `requires_organizational_approval`, `blocked`. Optional externally supplied assessment records must include evidence, reviewer role and review time; the tool does not authenticate a human's claim or deploy anything. Independent organizational approval remains required even if a future assessment evaluates GO.

## Decisions

- **Isolated staging:** GO only when the exact reviewed revisions' complete integration, security, operational-adapter, credential-audit and extended HTTPS recovery checks pass. Pending/failing CI means NO-GO for that revision. Use final PR links and generated `production-readiness.json`.
- **Public production:** NO-GO. Real off-host storage/retention/custody, independent witness retention, live alert delivery and on-call ownership are not configured or independently verified. The existing unfixed high vulnerability exception does not permit public deployment.

Proposed RPO 24 hours / RTO 60 minutes are planning targets only. No production SLA, HA, PITR, distributed rate limiting or real payment processing is approved. A deployment owner must review infrastructure/capacity/privacy obligations, assign and test the roles in ownership-incidents.md, independently verify provider policies, approve restore cadence and rehearse live escalation before revisiting this decision.
