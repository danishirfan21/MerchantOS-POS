"""Real PostgreSQL reporting, financial snapshots, pagination, export and performance verification."""
import os,json,urllib.parse,urllib.request,urllib.error,csv,io,time,subprocess,pathlib
from auth_client import Client,BASE
from report_fixture import seed,sql
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only reporting verification')
seed();admin=Client('ADMIN');cash=Client('CASHIER');checks=0
root='/api/admin/reports/'
def check(x):
 global checks
 assert x,'Reporting assertion failed';checks+=1
def get(path):
 status,data=admin.request(root+path);check(status==200);return data
def raw(client,path):
 try:
  with client.opener.open(BASE+root+path,timeout=20) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
for path in ['orders','sales','orders.csv']:
 try:urllib.request.urlopen(BASE+root+path);check(False)
 except urllib.error.HTTPError as e:check(e.code==401)
 check(cash.request(root+path)[0]==403)
q='range=custom&from=2020-01-02&to=2020-01-02'
start=time.monotonic();sales=get('sales?'+q);elapsed=time.monotonic()-start
# 2399 rows: g=1..2399 are in local Jan2; g=2400 is exactly next midnight.
n=2399;s=sales['summary'];check(s['completedOrders']==n);check(s['grossHalalas']==3000*n);check(s['discountsHalalas']==300*n);check(s['netBeforeVatHalalas']==2700*n);check(s['vatHalalas']==405*n);check(s['revenueHalalas']==3105*n);check(s['averageOrderHalalas']==3105)
check(len(sales['trend'])==24);check(sum(b['revenueHalalas'] for b in sales['trend'])==3105*n);check(sales['period']['startUtc'].startswith('2020-01-01T21:00:00'));check(sales['period']['endUtc'].startswith('2020-01-02T21:00:00'))
check(sum(p['completedOrders'] for p in sales['paymentMethods'])==n);check(sum(p['revenueHalalas'] for p in sales['paymentMethods'])==3105*n)
check(sales['topProducts'][0]['productId']=='p01');check(sales['topProducts'][0]['unitsSold']==2*n);check(sales['topProducts'][0]['grossHalalas']==2000*n);check(sales['topProducts'][0]['name']=='Historical Phone')
# Changing current prices cannot change historical report snapshots.
old=sql("SELECT price_halalas FROM products WHERE id='p01'")
sql("UPDATE products SET price_halalas=1 WHERE id='p01'")
try:check(get('sales?'+q)==sales)
finally:sql("UPDATE products SET price_halalas="+old+" WHERE id='p01'")
empty=get('sales?range=custom&from=2001-01-01&to=2001-01-01');check(empty['summary']['completedOrders']==0);check(empty['summary']['averageOrderHalalas']==0);check(all(b['revenueHalalas']==0 for b in empty['trend']))
check(get('sales?range=custom&from=2020-01-01&to=2020-02-10')['granularity']=='month')
check(get('sales?range=week')['granularity']=='day');check(get('sales?range=month')['granularity']=='day')
for bad in ['page=0','pageSize=101','page=100001','range=custom&from=bad&to=2020-01-01','range=custom&from=2020-02-01&to=2020-01-01','range=custom&from=2020-01-01&to=2022-01-01','range=custom&from=2099-01-01&to=2099-01-01','paymentMethod=wire','status=other','search='+('x'*121),'role=Administrator','page=1&page=2']:
 check(admin.request(root+'orders?'+bad)[0]==400)
check(admin.request(root+'sales?range=all')[0]==400);check(admin.request(root+'sales?search=x')[0]==400)
# Fetch all 10000 historical rows in bounded pages; many identical timestamps test tie ordering.
ids=[];keys=[]
for page in range(1,101):
 r=get(f'orders?search=HIST-&pageSize=100&page={page}');check(r['total']==10000);check(len(r['items'])==100);ids.extend(x['id'] for x in r['items']);keys.extend((x['createdAt'],x['id']) for x in r['items'])
check(len(set(ids))==10000);check(keys==sorted(keys,reverse=True));check(not r['hasMore']);check(get('orders?search=HIST-&page=101&pageSize=100')['items']==[])
check(get('orders?search=HIST-00100')['total']==1);check(get('orders?search='+urllib.parse.quote("' OR 1=1 --"))['total']==0)
cashpage=get('orders?'+q+'&search=HIST-&paymentMethod=cash&status=completed');check(cashpage['total']==1199);check(all(x['paymentMethod']=='cash' for x in cashpage['items']))
status,blob=raw(admin,'orders.csv?'+q+'&search=HIST-&paymentMethod=cash&status=completed');check(status==200);check(blob.startswith(b'\xef\xbb\xbf'));rows=list(csv.reader(io.StringIO(blob.decode('utf-8-sig'))));check(len(rows)==1200);check(len(rows[0])==10);check(all(r[3]=='cash' for r in rows[1:]));check(rows[1][8]=='31.05')
check(raw(admin,'orders.csv')[0]==413);check(raw(admin,'orders.csv?page=1')[0]==400)
# Formula, delimiter, quote and embedded newline must survive as one safe CSV cell.
sql("UPDATE orders SET order_number=E'=SUM(1,2)\"\\nline' WHERE id='00000000-0000-0000-0000-000000000001'")
status,blob=raw(admin,'orders.csv?search='+urllib.parse.quote('=SUM'));check(status==200);rows=list(csv.reader(io.StringIO(blob.decode('utf-8-sig'))));check(len(rows)==2);check(rows[1][0].startswith("'=SUM(1,2)\"\nline"))
sql("UPDATE orders SET order_number='BOUND-BEFORE' WHERE id='00000000-0000-0000-0000-000000000001'")
# Read-only results leave all persisted counts/balances unchanged; migration replay preserves populated data.
snapshot=lambda:sql("SELECT (SELECT sum(quantity_on_hand) FROM inventory_levels),(SELECT count(*) FROM orders),(SELECT sum(payable_halalas) FROM orders),(SELECT count(*) FROM admin_audit),(SELECT count(*) FROM auth_users),(SELECT count(*) FROM auth_sessions)")
before=snapshot();get('sales?'+q);get('orders?'+q);check(snapshot()==before)
subprocess.run(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-v','ON_ERROR_STOP=1','-f',str(pathlib.Path(__file__).resolve().parents[1]/'db/migrations/006_reporting_indexes.sql')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);check(snapshot()==before)
plan=sql("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT id,created_at FROM orders ORDER BY created_at DESC,id DESC LIMIT 20")
check('ix_orders_chronological' in plan);pathlib.Path('report-query-plan.json').write_text(plan)
check(elapsed<10);print(f'Reporting integration passed: {checks} assertions; 10000 historical orders; single-day aggregation {elapsed:.3f}s; chronological index verified. Query plan saved.')
# Independent session rejection for all new reporting surfaces.
probe=Client('ADMIN');sql("UPDATE auth_users SET enabled=false WHERE username='ci-admin'");check(probe.request(root+'sales')[0]==401);sql("UPDATE auth_users SET enabled=true WHERE username='ci-admin'")
probe=Client('ADMIN');sql("UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE user_id=(SELECT id FROM auth_users WHERE username='ci-admin')");check(probe.request(root+'orders')[0]==401)
probe=Client('ADMIN');check(probe.request('/api/auth/logout',{})[0]==204);check(probe.request(root+'orders.csv')[0]==401)
print(f'Reporting security completed: {checks} total assertions.')
