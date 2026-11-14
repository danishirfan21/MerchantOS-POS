# Dependency review — Milestone 8 and historical baseline

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

The trusted local staging scope uses generated disposable data. Public production remains blocked on unresolved image findings, assigned recovery/operator and backup/key custody and alerting ownership. Do not reinterpret a green evidence job as permission to publish this stack or import real customer data.

## Verified updated scans

[POS run 41243400011](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41243400011) and [Admin run 41243440648](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41243440648) execute successfully on the verified runtime commits. npm reports zero advisories; NuGet reports no vulnerable declared/transitive packages. Runtime image findings remain:

| Image | Critical | High | Medium | Low | Unknown |
|---|---:|---:|---:|---:|---:|
| POS API / Admin (each) | 0 | 0 | 21 | 5 | 0 |
| Caddy/static frontend | 0 | 7 | 16 | 1 | 3 |
| Operator tools (unused gosu removed) | 0 | 0 | 0 | 0 | 0 |
| PostgreSQL base (gosu retained for supported entrypoint) | 1 | 25 | 31 | 3 | 1 |

No finding is hidden by an ignore rule. The public-deployment decision remains BLOCKED. These counts are advisory-database/build observations and must be rechecked for a release.

## Milestone 8 database helper build correction (verification in progress)

The initial helper rebuild requested `github.com/tianon/gosu@v1.19`, which is not an installable upstream module tag. The upstream release is tagged `1.19` at commit `6456aaa0f3c854d199d0f037f068eb97515b7513`. The database builder now fetches and verifies that exact source commit, verifies its checked-in Go dependency checksums, and builds with the digest-pinned patched Go toolchain. The supported digest-pinned PostgreSQL image and its entrypoint remain in place. Only the gosu binary is replaced; its source-defined version is retained. No executable installer or third-party binary is downloaded.

The build runs `gosu --version` and verifies a `nobody` process has a nonzero UID. PostgreSQL initialization and migration are verified separately by integration CI. Build flags retain symbol information for vulnerability analysis, following upstream guidance. Full unsuppressed image reports and the staging-policy gate remain enabled. This correction is not evidence of a clean scan or completed Milestone 8; final results must be recorded after the exact-head workflows finish.

Upstream references: [release tag](https://github.com/tianon/gosu/tree/6456aaa0f3c854d199d0f037f068eb97515b7513), [source build instructions](https://github.com/tianon/gosu/blob/6456aaa0f3c854d199d0f037f068eb97515b7513/Dockerfile).

## Executed M8 remediation evidence

At POS commit `22747b26d130a7792c1fe8f54042d9bd42a60788`, [integration run 41294056990](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41294056990) and [security run 41294057012](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41294057012) passed. [Complete unsuppressed reports](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41294057012/artifacts/13078622600) include immutable image IDs and layer digests, installed/fixed versions and all advisories. These are executed observations at that revision; later final-head/staging image reports remain authoritative for review.

| Runtime image | M7 critical/high | M8 critical/high | M8 medium/low/unknown | Change |
|---|---:|---:|---:|---|
| POS API | 0 / 0 | 0 / 0 | 21 / 5 / 0 | Available OS patches; native .NET 10 retained |
| Caddy/static web | 0 / 7 | 0 / 1 | 3 / 0 / 3 | Same Caddy 2.11.7 source rebuilt with patched Go, x/net v0.60.0 and go-jose/v4 v4.1.6; Alpine patches |
| PostgreSQL | 1 / 25 | 0 / 0 | 1 / 0 / 1 | Same supported official digest/entrypoint; exact upstream gosu source rebuilt with patched Go |
| Operator tools | 0 / 0 | 0 / 0 | 0 / 0 / 0 | Unused helper absent |

Go build toolchain is `golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb`. Go dependency sums are verified for gosu. Registry APK/apt repositories and advisory databases can change, so rebuilds are not promised byte-identical; exact tested local image IDs/layers are captured, and staging scans the images it actually runs.

Remaining high finding: `CVE-2026-116587`, `github.com/go-jose/go-jose/v3` at `v3.0.5`, no fixed version reported. No JWT/JWK verification or automated issuer is configured in the reviewed Caddy configuration; local certificates and fixed HTTPS backends constrain reachability. This is a bounded reachability assessment, not proof that every linked dependency is unreachable. The owner-documented staging-only exception expires 2026-12-01 and fails when a fix becomes available, the configuration changes or a new high/critical appears. There is no broad ignore file. Public production remains blocked. Other medium/low/unknown findings remain in the full reports for periodic review.

`security-review.py` collects reports without hiding findings. `security-gate.py` independently enforces image-role completeness, immutable identities and high/critical policy, and writes `release-gate.json` with `publicProductionApproved=false`. Nine policy regression tests cover missing/empty evidence, new high findings, exception expiry, changed configuration and newly available fixes. npm and NuGet high/critical advisories also fail the gate.

## M9 supply-chain review (2026-11-01)

The current upstream Caddy release remains 2.11.7. GitHub's reviewed advisory GHSA-mgcc-cww5-fp2q still lists no patched go-jose/v3 version; v4 is already patched to 4.1.6. The existing v3.0.5 staging-only exception and its **2026-12-01** expiry are retained without extension. Reachability remains constrained by the unchanged local-certificate/fixed-backend Caddy configuration. Exact rebuilt images and current advisory data remain authoritative.

New operational dependencies are boto3 1.43.123 and psycopg 3.3.6 with hash-locked runtime wheels. Moto 5.2.5 and its checksum-locked dependency closure are CI-only fixtures. An initial direct installation of APK's pip pulled vulnerable installer dependencies (msgpack 1.1.2, setuptools 70.3.0, urllib3 2.7.0); the gate rejected them. Installation now occurs in a disposable builder, only the locked SDK environment is copied, and unused pip/setuptools and fixture code are absent from the operator runtime. No findings were suppressed to pass the gate.

Trivy now retains CycloneDX SBOMs alongside every unsuppressed exact-image JSON report, IDs and layer digests. OS repositories remain mutable; byte-for-byte reproducible image builds are not claimed. Existing GitHub Actions commit pins, digest-pinned PostgreSQL/Caddy/Go/.NET/Node bases, read-only/capability/non-root runtime controls and checksum-verified scanner installation remain in force. Final M9 scan evidence is recorded with the submitted PR heads.

Primary references: https://github.com/advisories/GHSA-mgcc-cww5-fp2q ; https://github.com/caddyserver/caddy/releases/tag/v2.11.7 ; https://trivy.dev/docs/latest/guide/configuration/reporting/ ; https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html .

## Security gate remediation (2026-11-14)

**Why.** New advisories published after the last green run (2026-11-02) made the staging vulnerability gate fail for any branch, independent of its code. Failing run: [43562605154](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/43562605154) on POS PR #10 (the same gate failed on the push run 43555664084).

| Finding | Component | Before | Fixed in | After |
|---|---|---|---|---|
| CVE-2026-114146 (GHSA-67wp-ghc2-fw2g, ASP.NET Core elevation of privilege) | `Microsoft.AspNetCore.App.Runtime.linux-x64` in the API image | 10.0.14 | 10.0.15 | 10.0.15 |
| CVE-2026-114147 | same | 10.0.14 | 10.0.15 | 10.0.15 |
| CVE-2026-114149 (GHSA-x33c-w48q-qrgc, ASP.NET Core denial of service) | same | 10.0.14 | 10.0.15 | 10.0.15 |
| CVE-2026-78661 (GO-2026-6860, quadratic html text-node coalescing) | `golang.org/x/net` in the rebuilt Caddy | v0.60.0 | v0.62.0 | v0.62.0 |

Advisory data was checked against OSV (`api.osv.dev`) on 2026-11-14: no advisories are listed for ASP.NET runtime 10.0.15 or `golang.org/x/net` v0.62.0. `x/net` v0.60.0 also carried GO-2026-6866 (CVE-2026-97045), fixed in the same v0.62.0.

**Base images** (index digests resolved from `mcr.microsoft.com`; the version was read from the image configuration of the linux/amd64 manifest):

| Image | Before | After |
|---|---|---|
| `mcr.microsoft.com/dotnet/sdk:10.0` | `sha256:de4fe90a…c02b` (SDK 10.0.403, runtime 10.0.14) | `sha256:fe0fd4e93bd2fbb47c883b7a6369e5c8d3db8bf01cdc5981f6ee35fbdf3ff4fb` (SDK 10.0.404, runtime 10.0.15, built 2026-11-10) |
| `mcr.microsoft.com/dotnet/aspnet:10.0` | `sha256:de0ee358…2fa7fee` (10.0.14) | `sha256:bfd912c83295ce66d4b706ebb8541b9f14259b0e76fbb88b2751f58ce2399d2e` (10.0.15, built 2026-11-10) |

Digest pinning is preserved in `services/merchant-api/Dockerfile` and `deploy/images.json`. `deploy/Dockerfile.web` now requests `golang.org/x/net@v0.62.0`; Caddy stays at v2.11.7 and go-jose/v4 at v4.1.6, the Go builder image is unchanged, and no Caddy configuration changed.

**Policy.** No exception was added or changed, no threshold or scanner version was altered, and the security workflow is untouched. The existing staging-only exception for `github.com/go-jose/go-jose/v3` CVE-2026-116587 (expires 2026-12-01) is unchanged. Public production remains blocked.

**Local verification (Windows host, no Docker available, so container builds and Trivy scans were not run locally):**

- Module graph: with Go 1.27.3 and the Dockerfile's exact `go get` line, `go list -m` resolved `golang.org/x/net v0.62.0`, `go-jose/v4 v4.1.6`, `caddy/v2 v2.11.7`; the binary built for linux/amd64 and `go version -m` on it reports the same versions.
- Image versions: the .NET runtime version of both pinned digests was read from the registry image configuration (10.0.15).
- `dotnet test` (48 tests, isolated PostgreSQL available) passed; `deploy/test_security_gate.py` passes (9 tests) once a `python3` command exists on PATH (on this Windows host it needed a shim).
- `govulncheck` on the rebuilt Caddy binary (informational, not the repository gate) no longer reports GO-2026-6860/6866 but lists other findings that the repository gate did not report: `github.com/klauspost/compress` v1.20.1 (fixed v1.20.2), Go standard library `net/http` in go1.27.3 (fixed go1.27.4) and `golang.org/x/crypto` v0.58.0 (openpgp packages). These are outside this change and are left for a separate review.

**GitHub Actions verification** of this change is recorded in the pull request, not here.
