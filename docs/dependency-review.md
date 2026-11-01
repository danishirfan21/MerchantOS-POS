# Dependency review — Milestone 7

The `Container and dependency evidence` (POS) and `Admin container and dependency evidence` workflows build release images, run npm audit, NuGet transitive advisory queries and checksum-verified Trivy 0.76.1. JSON reports include every reported finding without ignore rules. Workflow success means evidence was collected, not that an image has no vulnerabilities. Re-run on the exact release SHA; advisory databases change independently of code.

Initial executed scans:

- POS [run 41240500895](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41240500895), [reports](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41240500895/artifacts/13057321376).
- Admin [run 41240545339](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41240545339), [reports](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41240545339/artifacts/13056883857).

| Finding | Action / actual exposure |
|---|---|
| Vite 8.3.0–8.3.2 via Angular build 22.2.3, including GHSA-587h-7wmj-h5pm | Patched direct build package to 22.2.5 with regenerated lockfile. Local npm audit then reported zero findings; 21 Angular tests pass. This is build/dev-server tooling, absent from Caddy's static runtime. No major framework upgrade. |
| Caddy Alpine brotli/curl packages | Runtime build now applies available Alpine security patches; retain final scan evidence. Source rebuilds use mutable APK repositories and are not byte-identical. |
| Caddy Go stdlib/modules | Pinned official Caddy 2.11.7 image reports CVE-2026-111943 (certificate validation), CVE-2026-78667/78669/97031 (HTTP/TLS denial of service), and go-jose CVE-2026-116587. These remain explicit findings until a patched/rebuilt upstream image is reviewed. TLS upstream trust here is restricted to a private local CA, and listeners are loopback-only. No JWT/JWK authentication configured. These boundaries reduce exposure but do not remove the scanner findings or permit public deployment. |
| PostgreSQL image `/usr/local/bin/gosu` Go runtime | Scanner reports numerous Go TLS/HTTP/parser findings, including critical CVE-2025-68121. gosu is a privilege-drop helper used at database startup, not the PostgreSQL wire server; affected Go network APIs are not its intended execution path. PostgreSQL has no host port. Operator image removes this unused executable because its entrypoint is Python. Database base image remains scanned separately and findings remain visible. |
| .NET runtime images | Initial POS and Admin images each: 0 high/critical, 21 medium, 5 low. NuGet report found no vulnerable declared/transitive packages. OS findings still require periodic base refresh; this is not a vulnerability-free statement. |
| Admin npm | Initial scan zero advisories. Exact frontend runtime versions retained. |

Both apps retain existing password hashing, transaction arithmetic, authorization and reporting. Actions are pinned to verified maintained release commit SHAs: checkout 7.0.1, setup-node 7.1.0, setup-dotnet 6.0.0 and upload-artifact 7.0.2. Workflows grant contents:read only. No OIDC/cloud deployment permission. Runtime image bases are recorded by digest in `deploy/images.json` in POS. No downloaded installer is piped into a shell; the scanner archive checksum is checked before extraction.

The trusted local staging scope uses generated disposable data. Public production remains blocked on unresolved image findings, MFA/recovery, assigned backup/key custody and alerting ownership. Do not reinterpret a green evidence job as permission to publish this stack or import real customer data.

## Verified updated scans

[POS run 41243400011](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41243400011) and [Admin run 41243440648](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41243440648) execute successfully on the verified runtime commits. npm reports zero advisories; NuGet reports no vulnerable declared/transitive packages. Runtime image findings remain:

| Image | Critical | High | Medium | Low | Unknown |
|---|---:|---:|---:|---:|---:|
| POS API / Admin (each) | 0 | 0 | 21 | 5 | 0 |
| Caddy/static frontend | 0 | 7 | 16 | 1 | 3 |
| Operator tools (unused gosu removed) | 0 | 0 | 0 | 0 | 0 |
| PostgreSQL base (gosu retained for supported entrypoint) | 1 | 25 | 31 | 3 | 1 |

No finding is hidden by an ignore rule. The public-deployment decision remains BLOCKED. These counts are advisory-database/build observations and must be rechecked for a release.
