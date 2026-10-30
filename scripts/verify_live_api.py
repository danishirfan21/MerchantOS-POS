"""Assert the five live catalog endpoints against the seeded PostgreSQL database."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from auth_client import Client
auth=Client("ADMIN")

BASE = os.environ.get('MERCHANTOS_API_URL', 'http://127.0.0.1:5080').rstrip('/')


def get(path, expected=200):
    try:
        with auth.opener.open(BASE + path, timeout=10) as response:
            status = response.status
            data = json.load(response)
    except urllib.error.HTTPError as error:
        status = error.code
        data = None
    assert status == expected, f'{path}: expected HTTP {expected}, got {status}'
    return data


assert get('/api/health')['status'] == 'ok'
products = get('/api/products')
assert len(products) == 30, f'Expected 30 products, got {len(products)}'
assert len({p['sku'] for p in products}) == 30
assert all(isinstance(p['priceHalalas'], int) and p['priceHalalas'] >= 0 and isinstance(p['stock'], int) and p['stock'] >= 0 for p in products)
assert len(get('/api/categories')) == 6
assert len(get('/api/products?category=Audio')) == 5
assert [p['id'] for p in get('/api/products?search=Sony')] == ['p08']
assert [p['id'] for p in get('/api/products?category=Audio&search=Sony')] == ['p08']
assert get('/api/products/p01')['priceHalalas'] == 429900
assert get('/api/products/p01')['stock'] == 8
assert get('/api/inventory/p01') == {'productId': 'p01', 'stock': 8}
get('/api/products/missing', 404)
get('/api/inventory/missing', 404)
print('Live API passed: health, 30 products, categories, search, filtering, detail, inventory, and 404 responses.')
