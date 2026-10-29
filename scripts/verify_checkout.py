"""Live PostgreSQL checkout assertions; use fresh CI database state."""
import concurrent.futures
import json
import urllib.error
import urllib.request
import uuid

BASE = 'http://127.0.0.1:5080'

def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status, json.load(res)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)

def checkout(product='p01', qty=1, method='cash', tender=1000000, discount=0, scenario=None, key=None):
    return {'items': [{'productId': product, 'quantity': qty}], 'discountPercent': discount, 'paymentMethod': method, 'cashTenderedHalalas': tender if method == 'cash' else None, 'cardScenario': scenario if method == 'card' else None, 'idempotencyKey': key or str(uuid.uuid4())}

assert request('/api/inventory/p01')[1]['stock'] == 8
cash = checkout(discount=5)
status, sale = request('/api/checkout', cash)
assert status == 200, (status, sale)
assert (sale['subtotalHalalas'], sale['discountHalalas'], sale['vatHalalas'], sale['payableHalalas']) == (429900, 21495, 61261, 469666)
assert sale['changeHalalas'] == 530334
assert request('/api/inventory/p01')[1]['stock'] == 7
assert request('/api/checkout', cash)[1]['id'] == sale['id']
assert request('/api/inventory/p01')[1]['stock'] == 7
conflict = {**cash, 'discountPercent': 10}
assert request('/api/checkout', conflict)[0] == 409
assert request('/api/orders/' + sale['id'])[1]['orderNumber'] == sale['orderNumber']
assert any(o['id'] == sale['id'] for o in request('/api/orders')[1])
assert request('/api/checkout', checkout(tender=1))[0] == 400
assert request('/api/checkout', checkout(method='card', scenario='decline'))[0] == 402
assert request('/api/inventory/p01')[1]['stock'] == 7
rejected = checkout(method='card', scenario='decline')
assert request('/api/checkout', rejected)[0] == 402
assert request('/api/checkout', {**rejected, 'cardScenario': 'success'})[0] == 200
assert request('/api/inventory/p01')[1]['stock'] == 6
assert request('/api/checkout', checkout(product='missing'))[0] == 404
assert request('/api/checkout', checkout(qty=0))[0] == 400
assert request('/api/checkout', checkout(qty=99))[0] == 409
assert request('/api/inventory/p01')[1]['stock'] == 6
status, card = request('/api/checkout', checkout(method='card', scenario='success'))
assert status == 200 and card['paymentMethod'] == 'card'
assert request('/api/inventory/p01')[1]['stock'] == 5
same_key = checkout(product='p29', qty=1)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    duplicates = list(pool.map(lambda _: request('/api/checkout', same_key), range(2)))
assert all(status == 200 for status, _ in duplicates), duplicates
assert duplicates[0][1]['id'] == duplicates[1][1]['id']
assert request('/api/inventory/p29')[1]['stock'] == 4  # p29 starts at five units
# p30 starts with three units; only one competing request can buy two.
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    outcomes = list(pool.map(lambda _: request('/api/checkout', checkout(product='p30', qty=2))[0], range(2)))
assert sorted(outcomes) == [200, 409], outcomes
assert request('/api/inventory/p30')[1]['stock'] == 1
print('Checkout integration passed: cash, card, failures, idempotency, snapshots, inventory, orders and concurrency.')
