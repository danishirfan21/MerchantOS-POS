"""Real authenticated API checks; destructive auth-state cases use only disposable CI users."""
import os,json,urllib.request,urllib.error,subprocess,http.cookiejar
from auth_client import Client,BASE
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only security verification')
def raw(path,payload=None,headers=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status
 except urllib.error.HTTPError as e:return e.code
def sql(statement):
 subprocess.run(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-v','ON_ERROR_STOP=1','-c',statement],check=True,stdout=subprocess.DEVNULL)
checks=0
def check(condition):
 global checks
 assert condition,'Security boundary assertion failed';checks+=1
for path in ['/api/products','/api/categories','/api/inventory/p01','/api/orders','/api/orders/00000000-0000-0000-0000-000000000000','/api/receipts']:
 check(raw(path)==401)
check(raw('/api/checkout',{})==401)
check(raw('/api/products',headers={'Cookie':'MerchantOS.Pos.Session=tampered','X-Role':'Administrator'})==401)
admin=Client('ADMIN');cashier=Client('CASHIER');other=Client('OTHER')
check(admin.request('/api/orders')[0]==200)
sql("UPDATE auth_users SET role='Cashier' WHERE username='ci-admin'")
check(admin.request('/api/orders')[0]==403)
sql("UPDATE auth_users SET role='Administrator' WHERE username='ci-admin'")
check(admin.request('/api/orders')[0]==200)
check(cashier.request('/api/orders')[0]==403)
check(admin.request('/api/checkout',{})[0]==403)
check(cashier.request('/api/checkout',{},csrf=False)[0]==400)
check(cashier.request('/api/auth/logout',{},csrf=False)[0]==400)
check(cashier.request('/api/products')[0]==200)
owned=cashier.request('/api/receipts')[1]
check(len(owned)>0)
check(other.request('/api/orders/'+owned[0]['id'])[0]==404)
check(cashier.request('/api/orders/'+owned[0]['id'])[0]==200)
# Copy a genuine cookie to prove logout revokes the server-side session, not merely browser storage.
old='; '.join(c.name+'='+c.value for c in other.jar)
check(other.request('/api/auth/logout',{})[0]==204)
check(raw('/api/products',headers={'Cookie':old})==401)
rotate=Client('OTHER');old_rotate='; '.join(c.name+'='+c.value for c in rotate.jar)
check(rotate.request('/api/auth/login',{'username':os.environ['TEST_OTHER_USERNAME'],'password':os.environ['TEST_OTHER_PASSWORD']})[0]==409)
check(raw('/api/products',headers={'Cookie':old_rotate})==401)
expired=Client('OTHER');sql("UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE user_id=(SELECT id FROM auth_users WHERE username='ci-other')")
check(expired.request('/api/products')[0]==401)
disabled=Client('OTHER');sql("UPDATE auth_users SET enabled=false WHERE username='ci-other'")
check(disabled.request('/api/products')[0]==401)
# Wrong password, nonexistent user and disabled account return the same response.
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
with opener.open(BASE+'/api/auth/csrf') as r:token=json.load(r)['token']
def attempt(username,password):
 req=urllib.request.Request(BASE+'/api/auth/login',data=json.dumps({'username':username,'password':password}).encode(),headers={'Content-Type':'application/json','X-CSRF-TOKEN':token})
 try:
  with opener.open(req) as r:return r.status
 except urllib.error.HTTPError as e:return e.code
check(attempt('nonexistent',os.environ['TEST_OTHER_PASSWORD'])==401)
check(attempt(os.environ['TEST_OTHER_USERNAME'],os.environ['TEST_OTHER_PASSWORD'])==401)
for _ in range(5):check(attempt(os.environ['TEST_LOCKED_USERNAME'],'intentionally-wrong-password')==401)
check(attempt(os.environ['TEST_LOCKED_USERNAME'],os.environ['TEST_LOCKED_PASSWORD'])==401)
# IP throttling is checked last so it cannot contaminate functional login fixtures.
statuses=[attempt('nonexistent','invalid-password') for _ in range(65)]
check(429 in statuses)
for key,value in os.environ.items():
 if key.startswith('TEST_') and key.endswith('_PASSWORD'):
  for log in ['api.log','pos-api.log']:
   if os.path.exists(log):check(value not in open(log).read())
print(f'Security integration passed: {checks} direct authentication, policy, ownership, CSRF, revocation, expiry, disabled-account, lockout, throttle and log checks.')
