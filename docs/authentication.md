# Authentication and access boundaries

MerchantOS uses the existing PostgreSQL database as the identity authority. `004_identity.sql` adds users, absolute-expiry sessions and nullable order ownership without resetting products, stock, receipts or checkout tables. Apply all versioned migrations with `ON_ERROR_STOP=1`; old receipts remain Administrator-visible and are not assigned arbitrarily to a cashier.

ASP.NET Core CookieAuthentication and Data Protection protect opaque HTTP-only session cookies; `PasswordHasher<T>` supplies the standard salted, versioned PBKDF2 password format. The small native user store is intentional: only controlled provisioning, two roles and revocable sessions are needed. Full ASP.NET Identity UI, registration, reset emails and permission-management infrastructure are out of scope. No homemade password hashing or bearer-token protocol is used.

`ITicketStore` keeps sessions in PostgreSQL. Each authenticated request re-reads enabled status and role from the authority. Sessions expire absolutely after 30 minutes, do not slide, and are deleted by logout. Sign-in with an existing cookie first clears it and asks for a fresh attempt, preventing ticket reuse/session fixation. Expired rows are pruned on new sessions. Cookies are HttpOnly, SameSite=Strict and Secure by default; Data Protection keys live outside the repository in the host-managed key ring. Protect and persist that directory with OS permissions (and encryption/certificate protection for a future production setup).

| Route | Access |
| --- | --- |
| GET `/api/health` | Anonymous minimal status |
| GET `/api/auth/csrf` | Anonymous CSRF bootstrap, no-store |
| POST `/api/auth/login` | Anonymous, CSRF, IP throttle and DB lockout |
| GET `/api/auth/me`, POST `/api/auth/logout` | Signed-in Administrator/Cashier; POST requires CSRF |
| Products/categories/inventory GET routes | Administrator or Cashier catalog policy |
| GET `/api/orders` | Administrator reporting only |
| GET `/api/orders/{id}` | Administrator; Cashier only if owned (otherwise 404) |
| GET `/api/receipts` | Cashier's own latest 100 receipts |
| POST `/api/checkout` | Cashier only; CSRF and user-scoped idempotency |
| Unclassified/new endpoints | Denied until an explicit policy is assigned |

Administrator does not imply checkout permission. Checkout arithmetic, stock locks, transaction boundaries and payment validation are unchanged. Idempotency keys are namespaced by authenticated user before taking locks/reading records; users cannot replay another user's receipt by guessing their key. No client role header is trusted.

Every unsafe API method validates ASP.NET antiforgery tokens in `X-CSRF-TOKEN`. Fetch `/api/auth/csrf` before login, then fetch a new user-bound token after login. No CORS credentials policy is exposed; Angular uses its same-origin `/api` proxy. Credentials/session material are never placed into localStorage or sessionStorage. A 401 returns the POS to sign-in; the cart service remains responsible for cart state. Five failed attempts lock an account for five minutes; login also limits each source IP to 60 requests/minute. Failure messages do not distinguish disabled, missing or locked users.

## Local setup and account provisioning

1. Set `ConnectionStrings__MerchantDb` in your environment (no connection password is supplied by application defaults). Apply existing schema/seed and every `db/migrations/*.sql` to your development database. Do not reseed a populated database unless explicitly intended.
2. Prefer HTTPS (`dotnet dev-certs https --trust`, HTTPS API URLs and matching frontend proxy). For a strictly loopback development process only, set `ASPNETCORE_ENVIRONMENT=Development` and `Security__AllowLoopbackHttp=true`. HTTP requests are still rejected unless both Host and remote IP are loopback. No forwarded headers are trusted. This exception cannot start outside Development. Docker/internal-network HTTP is not loopback; configure a proper HTTPS deployment rather than weakening this guard.
3. To provision one development account, supply `Bootstrap__Username`, `Bootstrap__Password` (14–128 characters) and `Bootstrap__Role` (`Administrator` or `Cashier`) through environment variables, then run `dotnet run --project services/merchant-api -c Release -- --bootstrap-user`. Clear those variables afterwards. Repeat explicitly for the second role. Existing accounts are never overwritten; no public registration or known default account exists. This command refuses non-Development environments.
4. Run the API, then Angular using its same-origin proxy. Admin uses its own server-managed session and forwards the user's backend session only from its server-side HttpClient, with cookies disabled on pooled handlers. Admin must point to this authentication-enabled API revision; it has no second identity database or embedded service-account password.

## CI and limits

CI generates random ephemeral account passwords, masks them immediately and provisions them with the same command in an isolated database. All API and browser fixtures authenticate for real. Trace capture is disabled because traces can contain cookies and form bodies. Browser storage states exist only in `/tmp`, with mode 0600, outside uploaded report paths. A fail-closed artifact audit inspects files and embedded HTML report archives for the actual ephemeral passwords and protected Data Protection cookie/CSRF values before upload; a failure blocks the upload. Security cases exercise actual requests, CSRF, 401/403, ownership, tampering, revoked/expired/disabled sessions, lockout and throttling; lockout/throttle cases run last. SQL state changes are restricted to disposable CI identities.

This remains a local portfolio demo, not a public deployment approval. MFA, password reset/change, audit retention, distributed rate limiting/trusted proxy design, managed encrypted key storage and production provisioning are future work. Roles are constrained to two values; future operations need separate explicit policies. Administrator does not receive blanket backend privileges. Local browser tests use the explicitly documented loopback transport exception; HTTPS-only cookies remain the default.

## Executed evidence

[Implementation CI 41138325213](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41138325213) passed 9 .NET, 21 Angular unit and 21 browser tests, including cashier login/logout at all three viewports, plus 38 real direct security/log checks. Protected catalog and existing checkout/concurrency scripts passed. The final security fixture also re-applies the additive identity migration after checkout and compares persisted product/stock/order totals. Final-head CI and matching Admin dependency are linked in the two open security PRs.
