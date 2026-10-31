"""CI-only transaction tests against isolated PostgreSQL and the real authenticated API."""
import os,json,uuid,subprocess,urllib.request,urllib.error,concurrent.futures,pathlib
from auth_client import Client,BASE
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only isolated database verification')
count=0
def check(value):
 global count
 assert value,'Management integration assertion failed';count+=1
def sql(s,fail=False):
 r=subprocess.run(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-v','ON_ERROR_STOP=1','-Atc',s],capture_output=True,text=True)
 if fail:check(r.returncode!=0)
 else:assert r.returncode==0,r.stderr
 return r.stdout.strip()
def anonymous(path,payload=None):
 try:
  with urllib.request.urlopen(urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})) as r:return r.status
 except urllib.error.HTTPError as e:return e.code
admin=Client('ADMIN');cash=Client('CASHIER');pid='p30';product='/api/admin/products/'+pid;adjust='/api/admin/inventory/'+pid+'/adjustments'
def current():return admin.request(product)[1]
def update(p,**kw):return {**{k:p[k] for k in ['name','nameAr','category','priceHalalas','version']},**kw}
def stock(operation,q,version=None,reason='CI physical count',key=None):return dict(operation=operation,quantity=q,stockVersion=current()['stockVersion'] if version is None else version,reason=reason,idempotencyKey=key or str(uuid.uuid4()))
def history():return admin.request('/api/admin/audit?entityId='+pid+'&pageSize=50')[1]['items']
for path in [product,'/api/admin/audit']:
 check(anonymous(path)==401);check(cash.request(path)[0]==403)
for path in [product,adjust]:
 check(anonymous(path,{})==401);check(cash.request(path,{})[0]==403);check(admin.request(path,{},csrf=False)[0]==400)
original=current();orders_before=sql("SELECT coalesce(jsonb_agg(to_jsonb(x))::text,'[]') FROM (SELECT * FROM order_items ORDER BY id) x")
r=admin.request(product,update(original,name='CI updated product',priceHalalas=12345));check(r[0]==200);check(r[1]['version']==original['version']+1)
check(admin.request('/api/products/'+pid)[1]['priceHalalas']==12345)
check(admin.request(product,update(original))[0]==409)
for kw in [dict(priceHalalas=-1),dict(priceHalalas=100000001),dict(name=' '),dict(name='x'*241),dict(category='Unknown'),dict(sku='attempt'),dict(actorId=str(uuid.uuid4())),dict(priceHalalas=1.5)]:
 check(admin.request(product,update(current(),**kw))[0]==400)
check(admin.request('/api/admin/products/missing',update(current()))[0]==404)
check(sql("SELECT coalesce(jsonb_agg(to_jsonb(x))::text,'[]') FROM (SELECT * FROM order_items ORDER BY id) x")==orders_before)
actor=admin.request('/api/auth/me')[1]['id'];check(history()[0]['actorId']==actor)
# Audit insertion failure must roll back both types of business writes.
sql("CREATE FUNCTION ci_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'CI forced audit failure'; END $$; CREATE TRIGGER ci_fail_audit BEFORE INSERT ON admin_audit FOR EACH ROW EXECUTE FUNCTION ci_fail_audit()")
try:
 before=current();n=len(history());check(admin.request(product,update(before,name='Must roll back'))[0]==500);check(current()==before)
 check(admin.request(adjust,stock('restock',2))[0]==500);check(current()==before);check(len(history())==n)
finally:sql('DROP TRIGGER ci_fail_audit ON admin_audit; DROP FUNCTION ci_fail_audit()')
# Immutable application history, including TRUNCATE.
for statement in ['UPDATE admin_audit SET reason=reason','DELETE FROM admin_audit','TRUNCATE admin_audit','UPDATE inventory_adjustments SET request_hash=request_hash','DELETE FROM inventory_adjustments']:
 sql(statement,fail=True)
for op,q in [('restock',5),('damage',2),('correction',20)]:
 b=current();n=len(history());status,r=admin.request(adjust,stock(op,q));check(status==200);check(r['previousQuantity']==b['stock']);check(r['newQuantity']==(b['stock']+q if op=='restock' else b['stock']-q if op=='damage' else q));check(len(history())==n+1);check(r['stockVersion']>b['stockVersion'])
req=stock('restock',2);a=admin.request(adjust,req);b=admin.request(adjust,req);check(a==b);check(admin.request(adjust,{**req,'quantity':3})[0]==409)
for bad in [stock('damage',2147483647),stock('restock',2147483647),stock('restock',0),stock('correction',-1),stock('restock',1,reason=' '),stock('other',1),{**stock('restock',1),'quantity':2147483648},{**stock('restock',1),'userId':actor}]:
 n=len(history());check(admin.request(adjust,bad)[0]==400);check(len(history())==n)
# Same key concurrently: exactly one stock change and audit record.
b=current();same=stock('restock',3);n=len(history());admins=[Client('ADMIN'),Client('ADMIN')]
with concurrent.futures.ThreadPoolExecutor() as pool:rs=list(pool.map(lambda c:c.request(adjust,same),admins))
check(all(s==200 for s,_ in rs));check(rs[0][1]['id']==rs[1][1]['id']);check(current()['stock']==b['stock']+3);check(len(history())==n+1)
# Two unique adjustments based on one snapshot cannot overwrite one another.
v=current()['stockVersion'];reqs=[stock('restock',1,v),stock('damage',1,v)]
with concurrent.futures.ThreadPoolExecutor() as pool:rs=list(pool.map(lambda x:x[0].request(adjust,x[1]),zip(admins,reqs)))
check(sorted(s for s,_ in rs)==[200,409])
# A completed sale changes stockVersion; stale absolute correction must reject.
admin.request(adjust,stock('correction',20));stale=current();checkout=lambda key:cash.request('/api/checkout',dict(items=[dict(productId=pid,quantity=1)],discountPercent=0,paymentMethod='card',cardScenario='success',cashTenderedHalalas=None,idempotencyKey=key))
check(checkout(str(uuid.uuid4()))[0]==200);check(admin.request(adjust,stock('correction',20,stale['stockVersion']))[0]==409)
# Race a correction with a real sale: sale always deducted; correction succeeds first or conflicts.
b=current();correction=stock('correction',25,b['stockVersion'])
with concurrent.futures.ThreadPoolExecutor() as pool:
 f=pool.submit(checkout,str(uuid.uuid4()));g=pool.submit(admin.request,adjust,correction);sale=f.result();cor=g.result()
check(sale[0]==200);check(cor[0] in [200,409]);check(current()['stock']==(24 if cor[0]==200 else b['stock']-1))
# Product updates are independently optimistic under concurrent administrators.
p=current()
with concurrent.futures.ThreadPoolExecutor() as pool:rs=list(pool.map(lambda x:x[0].request(product,update(p,name=x[1])),zip(admins,['Concurrent A','Concurrent B'])))
check(sorted(s for s,_ in rs)==[200,409])
a=admin.request('/api/admin/audit?entityId='+pid+'&pageSize=1')[1];b=admin.request('/api/admin/audit?entityId='+pid+'&pageSize=1&page=2')[1];check(a['hasMore']);check(a['items'][0]['id']!=b['items'][0]['id']);check(admin.request('/api/admin/audit?pageSize=500')[0]==400)
check(all(x['actorId']==actor for x in history()));check('password' not in json.dumps(history()).lower());check(anonymous('/api/admin/audit',{}) in [401,405])
# Additive migration replay on populated orders, sessions, audit and adjustments.
snapshot=lambda:sql("SELECT (SELECT count(*) FROM products),(SELECT sum(quantity_on_hand) FROM inventory_levels),(SELECT count(*) FROM orders),(SELECT sum(payable_halalas) FROM orders),(SELECT count(*) FROM auth_users),(SELECT count(*) FROM auth_sessions),(SELECT count(*) FROM admin_audit),(SELECT count(*) FROM inventory_adjustments)")
before=snapshot();subprocess.run(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-v','ON_ERROR_STOP=1','-f',str(pathlib.Path(__file__).resolve().parents[1]/'db/migrations/005_management.sql')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);check(snapshot()==before)
# Restore catalog/stock via audited APIs; tests never touch a real developer database.
check(admin.request(product,update(current(),**{k:original[k] for k in ['name','nameAr','category','priceHalalas']}))[0]==200)
check(admin.request(adjust,stock('correction',original['stock']))[0]==200)
print(f'Management integration passed: {count} real authorization, validation, concurrency, idempotency, receipt, migration and audit integrity checks.')
