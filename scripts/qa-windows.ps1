# Run from MerchantOS repository root in Windows PowerShell.
# Requires Docker Desktop, Node 24.15+, npm 11+.
$ErrorActionPreference = 'Stop'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker compose failed' }
$health = Invoke-RestMethod 'http://localhost:5080/api/health'
if ($health.status -ne 'ok') { throw "Health check failed: $($health.status)" }
$products = @(Invoke-RestMethod 'http://localhost:5080/api/products')
if ($products.Count -ne 30) { throw "Expected 30 products; got $($products.Count)" }
$categories = @(Invoke-RestMethod 'http://localhost:5080/api/categories')
if ($categories.Count -ne 6) { throw "Expected 6 categories; got $($categories.Count)" }
$audio = @(Invoke-RestMethod 'http://localhost:5080/api/products?category=Audio')
if ($audio.Count -ne 5) { throw "Expected 5 Audio products; got $($audio.Count)" }
$sony = @(Invoke-RestMethod 'http://localhost:5080/api/products?search=Sony')
if ($sony.Count -ne 1 -or $sony[0].id -ne 'p08') { throw 'Sony search failed' }
$product = Invoke-RestMethod 'http://localhost:5080/api/products/p01'
if ($product.priceHalalas -ne 429900 -or $product.stock -ne 8) { throw 'Product lookup mismatch' }
try { Invoke-WebRequest 'http://localhost:5080/api/products/does-not-exist' -ErrorAction Stop | Out-Null; throw 'Missing product returned success' }
catch { if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw } }
$inventory = Invoke-RestMethod 'http://localhost:5080/api/inventory/p01'
if ($inventory.stock -ne 8) { throw "Incorrect p01 stock: $($inventory.stock)" }
npm ci
if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Angular build failed' }
npm test
if ($LASTEXITCODE -ne 0) { throw 'Vitest failed' }
Write-Host 'API and frontend smoke checks passed. Browser visual QA is still required.'
