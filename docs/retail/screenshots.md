# Actual browser evidence gallery

The final CI artifacts contain original PNGs and JSON measurements from the running applications, plus the Playwright report. Exact capture revisions and run links are recorded with the PRs. No image generation, retouching or hidden-defect masking is used. Enrollment material is never included in this gallery; the MFA verification form is empty.

| Evidence | Capture |
|---|---|
| POS catalog / cart / receipt | `e2e/retail.spec.ts`: `catalog.png`, `cart.png`, `receipt.png` |
| Checkout uncertainty / stock rejection | `committed-response-lost.png`, `insufficient-stock.png` |
| Arabic / accessible payment | `accessibility-arabic.png`, `accessibility-payment.png` |
| Narrow mobile | `narrow-320.png` |
| Admin Overview / products / inventory / orders | `retail.spec.ts`: `overview.png`, `products.png`, `inventory.png`, `orders.png` |
| Manager sale conflict / receipt | `manager-stale-after-sale.png`, `manager-receipt.png` |
| Product editor / stock review / audit history | Existing `management.spec.ts` screenshots |
| Historical reporting | Existing `reporting.spec.ts` dashboard/order captures |
| Safe MFA verification | `mfa.spec.ts`: `mfa-verification.png` (no active secret or typed code) |

Required viewport captures: desktop 1440×900, tablet 768×1024, mobile 390×844. POS also checks 320px width. The full CI gallery remains the authoritative evidence. Curated unmodified originals are delivered privately after visual review; they are not copied into the public repository. Artifact screening runs before upload; no traces, browser storage state, private fixtures or recovery keys are uploaded. Screenshots are loopback UI-suite captures, not a claim of public hosting or human UAT.

Audited capture sets (the screenshot manifests record their source revisions):

- [POS: catalog, cart, payment, receipt, RTL and recovery screenshots](https://github.com/danishirfan21/MerchantOS-POS/actions/runs/41380882492/artifacts/13113059020), source `cc8a11fe2d39e3aa02bfb860ae5a36c839fef3b4`.
- [Admin: all 115 browser cases and safe MFA captures](https://github.com/danishirfan21/MerchantOS-Admin/actions/runs/41379963932/artifacts/13113570282), source `debf6292147518fa8c18322ad1a38aa5661804b3`.

Final PR-head runs regenerate the same capture set against the final tested source. Older capture sets are explicitly revision-labelled; no screenshot is relabelled as a different commit.
