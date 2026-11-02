# Retail journey assessment and acceptance checklist

This is simulated-persona exploratory testing and deterministic browser/API/PostgreSQL verification. No external cashier, manager, interviewer or assistive-technology user has accepted this release. Participant acceptance and signatures remain **pending**.

Cashier: start at POS sign-in; find products, assemble a cart, review discount/VAT, pay cash or simulated card, show/print a receipt. The receipt is the completion signal. Stock rejection retains the sale context and refreshes stock; a definite declined card can be corrected. An uncertain response must retain the exact request and must never be treated as a failed sale. Manager: start at Admin password plus MFA; review Overview, inspect orders, update allowed product fields, review stock changes and adjustment history, export filtered reporting. Evaluator: initialize an isolated demo, enroll MFA, follow the walkthrough and inspect CI evidence.

## Acceptance matrix

Each row identifies the starting point, actions, result, failure/recovery and executable evidence. POS paths refer to MerchantOS-POS; Admin paths to MerchantOS-Admin. Final exact revisions/run links are in the PR descriptions and screenshot artifacts. Automated PASS is distinct from human acceptance.

| ID / starting point | Actions and expected result | Failure / recovery | Verification |
|---|---|---|---|
| C01 POS login | Cashier signs in, browses 30 fictional products | Bad credentials: safe generic error; retry | POS `e2e/auth.spec.ts` |
| C02 catalog | Search name/SKU/category; clear filters restores both input and products | No matches: explicit empty state and clear action | POS `e2e/retail.spec.ts`, `catalog.spec.ts` |
| C03 cart | Single and mixed products; quantity up/down; remove; total updates | At stock limit increase disabled; empty cart blocks payment | POS `catalog.spec.ts`, `retail.spec.ts`; `cart.service.spec.ts` |
| C04 cash dialog | Single/multiple-product cash purchase, discount 0/5/10%, 15% VAT, change and receipt | Invalid/insufficient cash rejected without order | POS `catalog.spec.ts`, `retail.spec.ts`; `order-totals.spec.ts`; `scripts/verify_checkout.py` |
| C05 card dialog | Simulated card approve, receipt, one stock deduction | Decline: visible error, preserve cart, correct scenario | POS `catalog.spec.ts`, `scripts/verify_checkout.py` |
| C06 checkout | Repeated/rapid submission cannot create duplicate order | Disable while processing; committed-but-lost response retries same key/body | POS `retail.spec.ts`, `checkout.component.spec.ts`; API `verify_checkout.py` |
| C07 interrupted checkout | Actual API commits, browser route drops response, reload, retry | Frozen pending sale; exact original request resolves to original receipt | POS `retail.spec.ts`; HTTPS `deploy/verify_staging.py` |
| C08 API/DB outage | Actual service/DB interruption; no false success; restart/retry | Preserve idempotency identity; readiness/alerts, authoritative receipt | HTTPS `deploy/verify_staging.py` (actual stopped services, 369+ baseline); UI dropped-response branch in `retail.spec.ts` |
| C09 inventory changed | Backend checks current stock, UI handles rejection | Refresh catalog; adjust quantities after definite rejection | POS `verify_checkout.py`; Admin `retail.spec.ts`, `management.spec.ts` |
| C10 receipt | Display correct snapshot, print action, history navigation | Failed history request shows error/retry | POS `catalog.spec.ts`; Admin `admin.spec.ts`, `mobile.spec.ts` |
| C11 expired/logged-out session | Protected checkout fails; sign in again | 401 returns login; pending tab snapshot remains scoped to same username | POS `auth.spec.ts`; native expiry/old-cookie rejection in HTTPS suite; pending reload in `retail.spec.ts` |
| M01 products | Search/filter/detail/edit valid field values; save; compare authoritative API | Invalid values blocked; stale version: refresh/review, no overwrite | Admin `management.spec.ts`; POS `verify_management.py` (actual PostgreSQL assertions) |
| M02 inventory | Restock, damage and correction; reason/review; history | Negative/excess/invalid values rejected; repeated request exact once | Admin `management.spec.ts`; POS `verify_management.py` |
| M03 cashier-manager | Manager opens adjustment; cashier sale changes stock; manager submits stale count | Conflict visible; refresh/review exposes new authoritative balance | Admin `retail.spec.ts`; final cleanup restores only disposable stock fixture |
| M04 orders | Filter, paginate past first 100 orders, inspect historical receipt | Empty results retain filters; expired session reveals no data | Admin `reporting.spec.ts`, `mobile.spec.ts` |
| M05 reporting | Store-local date boundaries, cash/card split, historical price/VAT/discount totals, CSV | Invalid range and >10,000-row export fail visibly; narrow filters | Admin `reporting.spec.ts`; POS `verify_reporting.py` (383 assertions) |
| M06 MFA | First enrollment, code, invalid/expired challenge, one-use recovery, password change, logout | Restricted pending ticket never grants Administrator; safe errors/cancel | Admin `mfa.spec.ts`, `auth.spec.ts`; POS 72 identity assertions; HTTPS expiry/revocation |
| E01 demo | Fresh private init, start, health, generated native accounts, card sale, duplicate retry | Missing prerequisites fail; marked demo reset only; MFA never bypassed | `deploy/verify_demo.py`, final Admin HTTPS workflow |
| E02 responsive | Desktop 1440×900, tablet 768×1024, mobile 390×844, POS 320px reflow | Screenshot review, keyboard correction; no design replacement | Both `retail.spec.ts`; preserved Admin tablet/mobile suites |
| E03 Arabic | Arabic search/product labels/cart/payment/receipt; SAR remains exact | English/Arabic copy complete for new pending-sale messages | POS `catalog.spec.ts`, `checkout.i18n.spec.ts`, `retail.spec.ts` |

C08's real infrastructure drill uses HTTP clients, rather than claiming a graphical browser physically disconnected the database. Browser fault injection and infrastructure interruption are separate evidence. No actual printer hardware, real card network, human screen-reader session or public deployment is tested.

## Human session guide (pending)

Use a fresh fictional demo. Give the participant the goal, not click-by-click answers: “Sell two different items and provide a receipt”; “Find that sale and correct stock after a delivery”; “Export yesterday's cash sales.” Observe task completion, mistakes, hesitation, error comprehension and recovery. Record consent, role (no unnecessary identity), viewport, exact revisions, task duration, outcome and participant wording. Never collect passwords/factors or record enrollment/recovery screens. Ask whether they know the final transaction outcome. Mark acceptance only after actual participation; no acceptance names or signatures are prefilled.

Exit: no unresolved critical integrity issue or high core-demo blocker; all retained security/financial/concurrency tests green; core responsive/RTL/keyboard paths checked; automated accessibility findings triaged; measured performance within scoped smoke budgets; reproducible demo and known limitations. Failure blocks the candidate. Human acceptance remains pending even after automated exit criteria pass.
