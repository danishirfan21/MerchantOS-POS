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

Required viewport captures: desktop 1440×900, tablet 768×1024, mobile 390×844. POS also checks 320px width. The full CI gallery remains the authoritative evidence; curated repository PNGs are selected only after visual review. Artifact screening runs before upload; no traces, browser storage state, private fixtures or recovery keys are uploaded. Screenshots are loopback UI-suite captures, not a claim of public hosting or human UAT.
