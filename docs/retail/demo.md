# Private retail demo and portfolio walkthrough

Prerequisites: Linux/macOS Docker Engine with Compose v2 (Linux CI verified), Python 3, OpenSSL, Git, adequate disk/CPU and outbound access for pinned build dependencies. Use a trusted operator machine and two reviewed source checkouts. Source tooling is .NET 10, Node 24 and PostgreSQL 17. `deploy/images.json`, lockfiles and final CI artifacts record dependencies. Do not reuse production data, permanent credentials or an existing installation directory.

From the POS checkout, with the Admin checkout as a sibling:

```sh
python3 deploy/demo.py init --directory "$HOME/merchantos-demo-m10" --admin ../MerchantOS-Admin
python3 deploy/demo.py start --directory "$HOME/merchantos-demo-m10"
python3 deploy/demo.py status --directory "$HOME/merchantos-demo-m10"
```

The launcher generates private TLS/DP/backup material and random passwords, seeds the unchanged fictional 30-product catalog on a fresh database, creates native cashier/admin identities through the isolated operator command and checks real HTTPS readiness. The marker records exact source commits. It binds only loopback POS `https://localhost:8443/` and Admin `https://localhost:9443/`. No hosted service or public certificate is created. Keep `secrets`, keys, recovery material and the marker outside source control. Open the generated `cashier_username`, `cashier_password`, `admin_username` and `admin_password` files locally in a protected editor; never paste credentials into documentation, screenshots, shell commands or issue comments.

Trust this installation's `secrets/ca.crt` in the demo browser following your browser's private-CA process. Do not disable TLS validation globally or install this CA on unrelated machines. Admin's first sign-in requires actual authenticator enrollment and confirmation. Save one-use recovery codes privately; no MFA bypass/demo factor is provided. Do not record the QR, manual setup key, typed factor, password or recovery-code page. Safe screenshots use a blank verification form after enrollment.

## Demonstrate retail value (about 8–12 minutes, suggested)

1. Cashier signs in. Search “Braided”, clear search, add a cable and another category, adjust quantity/remove an item. Explain SAR and discount/VAT totals.
2. Use **Simulated card / Approve**. Show the completed receipt and print preview. No card details or real payment are taken. Read the order number; inspect the reduced stock on the next catalog load.
3. Manager signs in with MFA. Inspect Overview, search Orders for that order number and open its historical receipt. Show inventory and the corresponding balance.
4. Edit an allowed product description and save. Perform a small restock with a reason, review before confirming, then show audit history. Explain stale-version conflicts and authoritative stock.
5. Select a reporting period, compare cash/card and VAT/discount totals, export a fictional filtered CSV. The demo starts empty; create sales first. The separate CI historical fixture has 10,000 deterministic orders and date-boundary cases without changing the normal catalog.
6. Explain retry evidence: a lost response can hide a committed order; “Retry same sale” retains key/body across reload. CI deliberately drops a committed response and verifies exactly one order/deduction. Exact replay returns the same receipt; conflicting reuse is rejected. Do not call replay a second payment.
7. Show final CI and audited recovery evidence. Discuss the real destroyed-environment drill; never run destructive recovery on a valued installation as a live performance trick.

## Stop, resume and reset

```sh
python3 deploy/demo.py stop --directory "$HOME/merchantos-demo-m10"
python3 deploy/demo.py reset --directory "$HOME/merchantos-demo-m10" --confirm-reset
```

Reset removes only the marked demo's containers/volume after verifying its directory and project configuration. It keeps private custody material for deliberate disposal. Initialize a **new empty directory** to reset keys, accounts, data and MFA enrollment. Startup refuses already initialized demos so it cannot silently recreate identities. To resume a stopped demo, use the same `staging.env`, reviewed Compose file and demo project with `docker compose ... up -d`; run `status`. If initial startup fails partway, inspect bounded logs, then reset the disposable instance and initialize a fresh directory; do not overwrite an existing database or files.

A browser-tab pending-sale snapshot contains product/quantity/payment-simulation data and its request ID, never an auth cookie, CSRF value or factor. It is scoped by username and cleared after definitive completion/rejection. Same-tab reload/reauthentication can retry. Closing the tab, clearing storage, changing browser/machine or deliberate storage tampering loses this convenience; **do not assume failure**. A manager must reconcile Orders/inventory before another sale. Multi-register offline operation and an independent checkout reconciliation module are not implemented.

For troubleshooting and recovery, retain [operations configuration](../operations/configuration.md), [backup/recovery](../operations/backup-recovery.md) and [readiness](../operations/readiness.md). A passing demo is not permission to expose listeners or accept real merchant transactions.
