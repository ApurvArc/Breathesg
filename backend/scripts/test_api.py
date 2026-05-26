"""Comprehensive API smoke test."""
import urllib.request, json, sys

base = 'http://localhost:8000/api/v1'
results = []

def test(label, fn):
    try:
        fn()
        results.append(f'PASS  {label}')
    except Exception as e:
        results.append(f'FAIL  {label}: {e}')

# --- Login ---
req = urllib.request.Request(
    f'{base}/auth/login/',
    data=json.dumps({'username': 'analyst', 'password': 'breathesg2024'}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST'
)
resp = urllib.request.urlopen(req, timeout=5)
tokens = json.loads(resp.read())
token = tokens['access']
H = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def get(path):
    r = urllib.request.Request(f'{base}{path}', headers=H)
    return json.loads(urllib.request.urlopen(r, timeout=5).read())

# Auth
test('GET /auth/me/', lambda: get('/auth/me/'))

# Dashboard
def check_dashboard():
    d = get('/dashboard/')
    q = d['data']['review_queue']
    assert q['pending'] >= 0
    assert d['data']['total_co2e_metric_tons'] >= 0
    print(f'       queue: {q}')
    print(f'       recent_batches: {len(d["data"]["recent_batches"])}')
test('GET /dashboard/', check_dashboard)

# Batches
def check_batches():
    b = get('/batches/')
    assert b['count'] == 5, f"Expected 5 batches, got {b['count']}"
    print(f'       batches: {b["count"]}')
test('GET /batches/', check_batches)

# Records
def check_records():
    r = get('/records/')
    assert r['count'] > 0
    print(f'       records total: {r["count"]}')
    # Test filter
    pend = get('/records/?status=PENDING')
    flag = get('/records/?status=FLAGGED')
    print(f'       pending: {pend["count"]}, flagged: {flag["count"]}')
test('GET /records/ + filters', check_records)

# Ledger
def check_ledger():
    l = get('/ledger/')
    print(f'       ledger entries: {l["count"]}')
test('GET /ledger/', check_ledger)

# Audit log
def check_audit():
    a = get('/audit-log/')
    assert a['count'] > 0
    print(f'       audit events: {a["count"]}')
test('GET /audit-log/', check_audit)

# Facilities
def check_facilities():
    f = get('/facilities/')
    print(f'       facilities: {len(f["data"])}')
test('GET /facilities/', check_facilities)

# Print results
print()
print('=' * 50)
for r in results:
    print(r)
print('=' * 50)

fails = [r for r in results if r.startswith('FAIL')]
if fails:
    sys.exit(1)
else:
    print(f'All {len(results)} tests passed!')
