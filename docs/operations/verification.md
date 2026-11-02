# Executed M9 verification

The functional implementation at POS `95581ec7ab82346f40df57e6b8c8a20a42f6e8a3` and Admin `9bfd00529f28c714eef36f552435048955f6809c` passed real CI. Final submitted heads must also have all checks green; PR descriptions provide final-head commits/links.

| Verification | Executed result |
|---|---|
| [POS integration](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41325541200) | 48 .NET (47 baseline retained), 72 PostgreSQL identity assertions, 21 Angular, 24 browser, 383 reporting, 99 management and 40 direct security checks |
| [POS operational integration](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41325541302) | 51 actual PostgreSQL/TLS S3/alert assertions, including transactional rollback, retry/restart, duplicate/reorder/rollback rejection, independent signature verification, missing/modified data, retained-version delete denial, encrypted backup/restore, verified-only local retention, old-pending preservation and role denials |
| [POS security](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41325541382) | Separate policy gate and nine regression tests pass; exact-image reports and CycloneDX SBOMs retained |
| [Admin integration](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41325706260) | 69 .NET (68 baseline retained), all 109 browser cases, full catalog/checkout/reporting/management/security regression |
| [Admin security](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41325706263) | Passing exact-image/dependency gate |
| [Full HTTPS recovery](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41325706174) | 369 assertions; 283 baseline scenarios retained and extended. The reusable protected-dependency interface performs its entry checks internally, replacing duplicated fixture checks; no M8 assertions were removed. |
| [Audited staging evidence](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41325706174/artifacts/13091352194) | Actual readiness/database outage alert firing and resolution through TLS fixture; original-host loss, fresh app directory/PostgreSQL volume, signed encrypted retrieval, protected dependency recovery, identity quarantine/reconciliation, old-cookie rejection, authenticated smoke and both image sets scanned |

Six artifact-auditor regression tests pass locally; actual integration/staging artifact screening passes before upload. Known OTP detection distinguishes a standalone code from an unrelated hexadecimal digest, while preserving long-credential, cookie, enrollment, private-key and dump detection.

An earlier full drill at Admin `799d0d55455572d27d7ed7f80c83e93e524da1a5` / POS `aed2f49ad9e059e0b0f96716de6a1307b2d513e7` measured backup 1.767s, upload 0.306s, download 0.042s, restore 0.542s, app startup 14.081s, reconciliation 2.878s and full environment recovery 37.638s. These are small disposable-fixture observations with Docker cache, not production promises. Subsequent results remain in their exact-run artifacts.

The isolated S3 service reports and enforces retained-version deletion denial in tests. This does not establish real-provider IAM correctness, immutable external retention or physical off-host durability. The witness and recovery materials occupy separate controlled fixture interfaces, not actual organizational custody. Alert delivery reaches only an isolated test receiver. No real notifications, merchant data, public deployment or paid resources are involved.

Readiness: isolated staging GO for a fully passing reviewed revision; public production NO-GO. Proposed RPO 24h / RTO 60m are uncommitted targets. Real storage/retention, independent custodians/witness operation, live alert/on-call routing, restore cadence, infrastructure/capacity/privacy review and the remaining staging-only go-jose/v3 high exception still block production. The 2026-12-01 exception is not extended.
