# Milestone 8 identity threat model

Prerequisite verified: POS M7 merged `2f5514156ba8acd4224dc5b92099335a95628e0a` ([post-merge CI](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41285416463)); Admin M7 merged `0bbe2e5849fc05b0092cce009cd9d6387ca4204a` ([post-merge recovery CI](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41285428663)). New branches start at these current mains; previous PRs are completed history.

Trust boundaries: browser → trusted local HTTPS edge → Admin BFF → authoritative POS → one PostgreSQL database. Operator/Docker host and private recovery-key custody are separate privileged boundaries. Admin full tickets remain server-held and revalidated against POS; a separate pending scheme never satisfies Administrator authorization. Data Protection rings remain certificate-encrypted and persistent.

| Threat | Control / remaining boundary |
|---|---|
| Stolen administrator password | Password validation creates only a five-minute restricted challenge; POS issues no full admin session until second-factor verification. |
| Stolen full session cookie | HttpOnly/Secure/Strict, CSRF, absolute 30-minute expiry and database revocation/version checks. MFA does not cure cookie theft; trusted host remains necessary. |
| MFA bypass / forged role | Full backend session must have server-recorded MFA timestamp and matching security version; legacy password-only Administrator sessions fail closed. |
| Enrollment takeover | Primary identity plus bounded enrollment challenge, one pending secret encrypted per reference, explicit code confirmation, no activation/redisplay after completion. Initial credentials must be handed to the intended operator on a trusted device. Stolen initial credentials before enrollment remain a bootstrap risk requiring operator identity verification. |
| TOTP/challenge replay or concurrent requests | User/challenge row locks; last accepted step strictly increases; one-time challenge consumption and session issuance in the same transaction. Six digits, 30-second step, ±one step tolerance; no client clock overrides. |
| Recovery-code theft/abuse | Cryptographically random 256-bit codes, equivalent SHA-256 verifiers only, one-time transactional redemption, attempt limits; never a public password reset. |
| Password-reset abuse | No email reset endpoint. Explicit operator command, case reference and identity-verification runbook; force password replacement, revoke sessions/challenges; MFA is preserved. MFA-loss reset requires separate explicit authorization. |
| Role/credential changes | Increment security version and revoke sessions/challenges transactionally; native session authority checks current role/enabled/version/MFA. |
| Process restart | Challenges, encrypted secrets, replay state and session authority are durable; expiry never extends. |
| Backup rollback | Restored identity data may predate revocation or code consumption. Restore quarantines all users; separately authorized per-person reconciliation revokes sessions/challenges and resets credentials/MFA/recovery state before accepting credentials; demonstrate this gate in isolated recovery tests. |
| Compromised operator/Docker credentials | Can change identity authority: explicit flags and database-backed security records provide bounded controls, not immunity. Two-person/offline identity verification, off-host immutable audit and operator ownership remain public-release requirements. |

No cryptographic primitives are implemented locally: Otp.NET RFC 6238, native Data Protection, native PasswordHasher and framework CSPRNG/SHA-256 APIs. No paid identity, email or QR service. Security events use fixed categories/outcomes and identifiers only, never authentication material. Runtime DB roles cannot update/delete event records; separate owner retention is bounded. Real database lifecycle/concurrency, rollback and HTTPS restore verification is linked in staging-readiness.md; no production approval is implied.
