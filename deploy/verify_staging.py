"""Mutating operational drill: fresh isolated local Compose project only. No public deployment."""
import argparse,concurrent.futures,contextlib,hashlib,http.cookiejar,json,os,pathlib,shutil,socket,ssl,statistics,subprocess,tempfile,time,urllib.error,urllib.request,uuid,tarfile
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--admin-context',required=True);a=p.parse_args()
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('This destructive drill is CI-only. Use runbook smoke reads for an existing staging installation.')
root=pathlib.Path(__file__).resolve().parents[1];work=pathlib.Path(a.directory).resolve();assert not work.exists(),'Fresh disposable path required'
subprocess.run(['python3',str(root/'deploy/init-local.py'),'--output',str(work)],check=True)
# init-local writes GITHUB_ENV for later steps; this process reads only its private generated files.
secret=work/'secrets';project='merchantos_ops_'+os.environ['GITHUB_RUN_ID']+'_'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
env={**os.environ,'STAGING_DIR':str(work),'STAGING_UID':str(os.getuid() or 1654),'ADMIN_CONTEXT':str(pathlib.Path(a.admin_context).resolve()),'COMPOSE_PROJECT_NAME':project,'SEED_DEMO':'true'}
base=['docker','compose','--env-file',str(work/'staging.env'),'-f',str(root/'deploy/compose.yml')]
evidence=pathlib.Path('operational-evidence');evidence.mkdir(exist_ok=True);checks=0;timings={}
def run(*args,ok=True,stdin=None):
 r=subprocess.run(base+list(args),env=env,input=stdin,text=True,capture_output=True)
 if ok and r.returncode:raise RuntimeError('Compose operation failed: '+str(args[:2])+'\n'+r.stderr[-3500:])
 return r
def check(x):
 global checks
 assert x,'Staging invariant failed';checks+=1
def sql(statement,database='merchantos'):
 r=run('exec','-T','-e','PGPASSFILE=/run/secrets/pgpass','db','psql','-X','-U','merchantos','-d',database,'-v','ON_ERROR_STOP=1','-Atc',statement,ok=False)
 # db mounts only DB password, so socket-local trust is used for controlled operator exec.
 if r.returncode:raise RuntimeError('Isolated SQL invariant query failed')
 return r.stdout.strip()
def wait_ready():
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  if probe('/api/health/ready')[0]==200 and probe('/health/ready',admin=True)[0]==200:return
  time.sleep(1)
 diagnostic=subprocess.run(['curl','-v','--max-time','5','--cacert',str(secret/'ca.crt'),'https://localhost:8443/api/health/ready'],text=True,capture_output=True)
 raise RuntimeError('Staging readiness did not recover within 90s; TLS-only diagnostic: '+diagnostic.stderr[-2500:])
ctx=ssl.create_default_context(cafile=str(secret/'ca.crt'))
def opener(jar=None):return urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(jar if jar is not None else http.cookiejar.CookieJar()))
def probe(path,payload=None,admin=False,client=None,headers=None):
 url=('https://localhost:9443' if admin else 'https://localhost:8443')+path
 req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
 try:
  with (client or opener()).open(req,timeout=12) as r:return r.status,r.read(),r.headers
 except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
 except (urllib.error.URLError,TimeoutError,ConnectionError):return 0,b'',{}
class Client:
 def __init__(self,role):self.jar=http.cookiejar.CookieJar();self.http=opener(self.jar);self.token='';self.role=role
 def csrf(self):
  s,b,_=probe('/api/auth/csrf',client=self.http);check(s==200);self.token=json.loads(b)['token']
 def login(self):
  self.csrf();s,b,h=probe('/api/auth/login',{'username':(secret/(self.role+'_username')).read_text(),'password':(secret/(self.role+'_password')).read_text()},client=self.http,headers={'X-CSRF-TOKEN':self.token});check(s==200);self.csrf();return self
 def call(self,path,data=None):
  s,b,h=probe(path,data,client=self.http,headers={'X-CSRF-TOKEN':self.token} if data is not None else {});
  try:value=json.loads(b) if b else None
  except ValueError:value=b.decode()
  return s,value,h
 def mvc_login(self):
  import re,urllib.parse
  with self.http.open('https://localhost:9443/Account/Login') as r:html=r.read().decode()
  token=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',html)[1]
  data=urllib.parse.urlencode({'Username':(secret/(self.role+'_username')).read_text(),'Password':(secret/(self.role+'_password')).read_text(),'ReturnUrl':'/','__RequestVerificationToken':token}).encode()
  with self.http.open(urllib.request.Request('https://localhost:9443/Account/Login',data=data)) as r:check(r.status==200)
  return self
 def mvc(self,path):return probe(path,admin=True,client=self.http)
def operator(op,role='admin',targetrole=None):
 args=['run','--rm','--no-deps','-v',str(secret)+':/operator:ro','-e','Operations__AllowAccountCommand=true','-e','Account__Operation='+op,'-e','Account__UsernameFile=/operator/'+role+'_username']
 if op in ['create','password']:args+=['-e','Account__PasswordFile=/operator/'+role+'_password']
 if targetrole:args+=['-e','Account__Role='+targetrole]
 return run(*args,'pos-api','--account')
def snapshot(database='merchantos'):
 # Canonical hashes cover every persisted field, including encrypted ticket blobs and expiry.
 tables=['products','inventory_levels','orders','order_items','payments','checkout_idempotency','auth_users','auth_sessions','admin_audit','inventory_adjustments','admin_ticket_sessions']
 return {t:sql("SELECT md5(coalesce(string_agg(row_to_json(x)::text,E'\\n' ORDER BY row_to_json(x)::text),'')) FROM "+t+' x',database) for t in tables}
def measure(name,fn,n=3):
 values=[]
 for _ in range(n):
  start=time.perf_counter();result=fn();values.append((time.perf_counter()-start)*1000);check(result[0]==200)
 timings[name]={'samples':n,'p50Ms':round(statistics.median(values),2),'maxMs':round(max(values),2),'operationsPerSecond':round(n/(sum(values)/1000),2)}
try:
 run('build',ok=True);run('up','-d','db');run('run','--rm','migrate');run('up','-d','pos-api','admin','web');wait_ready()
 # Configuration and port boundary, no public listener or privileged normal app.
 config=json.loads(run('config','--format','json').stdout)
 for service in ['pos-api','admin','web']:
  c=config['services'][service];check(c['read_only']);check('ALL' in c['cap_drop']);check(c.get('user') not in ['0','root','0:0']);check(not c.get('privileged',False))
 for service in ['pos-api','admin','db']:check(not config['services'][service].get('ports'))
 for port in config['services']['web']['ports']:check(port['host_ip']=='127.0.0.1')
 check(probe('/')[0]==200);check(probe('/api/products')[0]==401);check(probe('/api/health/live')[0]==200);check(probe('/health/live',admin=True)[0]==200)
 # Spoofed forwarded headers at the TLS edge cannot alter external scheme or source identity.
 check(probe('/api/products',headers={'X-Forwarded-For':'203.0.113.8','X-Forwarded-Proto':'http'})[0]==401)
 direct="import urllib.request,urllib.error,ssl; r=urllib.request.Request('https://pos-api:8443/api/health/live',headers={'X-Forwarded-For':'203.0.113.8'}); ctx=ssl.create_default_context(cafile='/run/secrets/ca.crt');\ntry: urllib.request.urlopen(r,context=ctx)\nexcept urllib.error.HTTPError as e: print(e.code)"
 check(run('run','--rm','--no-deps','migrate','-c',direct).stdout.strip()=='400')
 invalid=run('run','--rm','--no-deps','-e','Operations__CertificatePath=/missing.pfx','pos-api','--rotate-keys',ok=False);check(invalid.returncode!=0)
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args):return None
 redirect=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 try:redirect.open('http://localhost:8080/')
 except urllib.error.HTTPError as e:check(e.code==308);check(e.headers['Location']=='https://localhost:8443/')
 for role,target in [('admin','Administrator'),('cashier','Cashier'),('other','Administrator')]:operator('create',role,target)
 admin=Client('admin').login();cashier=Client('cashier').login();mvc=Client('admin').mvc_login();other=Client('other').mvc_login()
 check(admin.call('/api/orders')[0]==200);check(cashier.call('/api/admin/reports/sales')[0]==403);check(cashier.call('/api/checkout',{})[0]==400)
 cookie=next(c for c in cashier.jar if c.name=='MerchantOS.Pos.Session');check(cookie.secure);check(cookie.has_nonstandard_attr('HttpOnly'));check(cookie.get_nonstandard_attr('SameSite')=='Strict')
 # Each BFF request forwards only its own server-held identity, including under concurrency.
 with concurrent.futures.ThreadPoolExecutor() as pool:responses=list(pool.map(lambda c:c.mvc('/'),[mvc,other]*5))
 for i,(status,body,_) in enumerate(responses):check(status==200);check((secret/('admin_username' if i%2==0 else 'other_username')).read_text().encode() in body)
 check(not any(c.name=='MerchantOS.Pos.Session' for c in mvc.jar));check(sql('SELECT count(*) FROM admin_ticket_sessions')=='2')
 def managed():return admin.call('/api/admin/products/p17')[1]
 def stock(q,operation='restock',key=None):
  p=managed();return {'operation':operation,'quantity':q,'reason':'Isolated staging drill','stockVersion':p['stockVersion'],'idempotencyKey':key or str(uuid.uuid4())}
 def product():
  p=managed();return admin.call('/api/admin/products/p17',{k:p[k] for k in ['name','nameAr','category','priceHalalas','version']})
 measure('authentication',lambda:Client('other').login().call('/api/auth/me'))
 measure('catalog',lambda:cashier.call('/api/products'));measure('product-edit',product)
 adjustment=stock(5);before=managed()['stock'];check(admin.call('/api/admin/inventory/p17/adjustments',adjustment)[0]==200);check(managed()['stock']==before+5);check(admin.call('/api/admin/inventory/p17/adjustments',adjustment)[0]==200);check(managed()['stock']==before+5)
 measure('inventory-adjustment',lambda:admin.call('/api/admin/inventory/p17/adjustments',stock(1)))
 check(admin.call('/api/admin/audit?entityId=p17')[1]['items']);check(mvc.mvc('/Admin/Orders')[0]==200)
 checkout={'items':[{'productId':'p17','quantity':1}],'discountPercent':0,'paymentMethod':'cash','cashTenderedHalalas':10000000,'idempotencyKey':str(uuid.uuid4())}
 t=time.perf_counter();first=cashier.call('/api/checkout',checkout);check(first[0]==200);timings['checkout']={'samples':1,'elapsedMs':round((time.perf_counter()-t)*1000,2)};order=first[1]['id']
 measure('reporting',lambda:admin.call('/api/admin/reports/sales'));measure('pagination',lambda:admin.call('/api/admin/reports/orders'));measure('csv-export',lambda:admin.call('/api/admin/reports/orders.csv'))
 # Crash/restart and persisted absolute expiry. No renewals occur on reads or restarts.
 expiries=sql('SELECT string_agg(expires_at::text,\',\' ORDER BY id_hash) FROM admin_ticket_sessions');baseline=snapshot()
 for service in ['admin','pos-api','web','db']:
  run('restart',service);wait_ready();check(mvc.mvc('/Admin/Orders')[0]==200);check(cashier.call('/api/auth/me')[0]==200);check(snapshot()==baseline)
 run('restart');wait_ready();check(mvc.mvc('/')[0]==200);check(snapshot()==baseline);check(sql('SELECT string_agg(expires_at::text,\',\' ORDER BY id_hash) FROM admin_ticket_sessions')==expiries)
 # Old cookie still works after a newly activated encryption key; XML keys are encrypted at rest.
 for service in ['pos-api','admin']:
  run('run','--rm','--no-deps','-e','Operations__AllowKeyCommand=true',service,'--rotate-keys');run('restart',service)
 wait_ready();check(mvc.mvc('/')[0]==200);check(cashier.call('/api/auth/me')[0]==200)
 for directory in ['pos-keys','admin-keys']:
  for file in (work/directory).glob('*.xml'):
   raw=file.read_text();check('<encryptedSecret' in raw);check('<masterKey' not in raw)
 # A forced process kill with an active checkout may produce no reply. Retrying the same key must be exact-once.
 checkout['idempotencyKey']=str(uuid.uuid4());prior=managed()['stock']
 with concurrent.futures.ThreadPoolExecutor() as pool:
  active=pool.submit(cashier.call,'/api/checkout',checkout);run('kill','-s','SIGKILL','pos-api');result=active.result();check(result[0] in [0,200,502,503])
 run('up','-d','pos-api');wait_ready();replay=cashier.call('/api/checkout',checkout);check(replay[0]==200);check(managed()['stock']==prior-1);check(cashier.call('/api/checkout',checkout)[1]['id']==replay[1]['id'])
 # DB loss: liveness persists, readiness fails, safe errors omit credentials and recover without login loss.
 run('stop','db');check(probe('/api/health/live')[0]==200);check(probe('/health/live',admin=True)[0]==200);check(probe('/api/health/ready')[0]==503);check(probe('/health/ready',admin=True)[0]==503)
 failure=mvc.mvc('/Admin/Orders');check(failure[0] in [500,503]);check(b'Password=' not in failure[1]);run('start','db');wait_ready();check(mvc.mvc('/Admin/Orders')[0]==200)
 check(cashier.call('/api/checkout',checkout)[1]['id']==replay[1]['id']);check(admin.call('/api/admin/inventory/p17/adjustments',adjustment)[1]['newQuantity']==before+5)
 # Migration replay and concurrent runners retain all business/auth/audit data.
 before_restore=snapshot()
 with concurrent.futures.ThreadPoolExecutor() as pool:list(pool.map(lambda _:run('run','--rm','migrate'),range(2)))
 check(snapshot()==before_restore)
 bad=work/'bad';bad.mkdir();(bad/'008_fail.sql').write_text('CREATE TABLE should_rollback(id integer); SELECT 1/0;')
 failed=run('run','--rm','-v',str(bad)+':/bad:ro','migrate','/ops/migrate.py','--directory','/bad',ok=False);check(failed.returncode!=0);check(sql("SELECT to_regclass('should_rollback') IS NULL")=='t');check(sql("SELECT count(*) FROM merchant_migrations WHERE version='008_fail.sql'")=='0');check(snapshot()==before_restore)
 # Encryption backup, real isolated restore, then application/session recovery against the restored DB.
 run('run','--rm','--no-deps','backup');backup=sorted((work/'backups').glob('*.dump.cms'))[-1]
 run('run','--rm','--no-deps','restore','/ops/restore.py','/backups/'+backup.name,'--target','merchant_restore_drill','--confirm-isolated')
 check(snapshot('merchant_restore_drill')==before_restore)
 # Keys are a separate recovery dependency: restore a private snapshot, not a DB table.
 keybackup=work/'protected-keys.tar'
 with tarfile.open(keybackup,'w') as archive:
  for directory in ['pos-keys','admin-keys']:archive.add(work/directory,arcname=directory)
 # Encrypt key archive before storing; offline backup private key is not mounted by the backup service.
 subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-cbc','-in',str(keybackup),'-outform','DER','-out',str(work/'protected-keys.cms'),str(secret/'backup_cert.pem')],check=True);keybackup.unlink()
 run('stop','pos-api','admin')
 for name in ['pos_connection','admin_connection']:
  path=secret/name;path.write_text(path.read_text().replace('Database=merchantos;','Database=merchant_restore_drill;'))
 run('run','--rm','--no-deps','-e','PGDATABASE=merchant_restore_drill','migrate','/ops/roles.py')
 # Decrypt/restore the protected key directory separately and restart the consumers.
 restored=work/'keys-recovered.tar';subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(work/'protected-keys.cms'),'-inkey',str(secret/'backup_key.pem'),'-out',str(restored)],check=True)
 for directory in ['pos-keys','admin-keys']:shutil.rmtree(work/directory)
 with tarfile.open(restored) as archive:archive.extractall(work,filter='data')
 restored.unlink();run('up','-d','pos-api','admin');wait_ready();check(mvc.mvc('/Admin/Orders')[0]==200);check(cashier.call('/api/orders/'+order)[0]==200);check(snapshot('merchant_restore_drill')==before_restore)
 # Correlation and safe operational signals.
 cid=uuid.uuid4().hex;s,b,h=probe('/api/products',client=admin.http,headers={'X-Correlation-ID':cid});check(h.get('X-Correlation-ID')==cid);check(admin.call('/api/ops/metrics')[0]==200)
 cid=uuid.uuid4().hex;check(probe('/Admin/Orders',admin=True,client=mvc.http,headers={'X-Correlation-ID':cid})[0]==200)
 lines=run('logs','--no-color','admin','pos-api').stdout.splitlines();check(any('-admin ' in line and cid in line for line in lines));check(any('-pos-api ' in line and cid in line for line in lines))
 # Expired POS sessions immediately block their BFF session; restart cannot renew expiry.
 sql("UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE user_id=(SELECT id FROM auth_users WHERE username='staging-other')",'merchant_restore_drill')
 check(b'Sign In' in other.mvc('/Admin/Orders')[1]);other=Client('other').mvc_login()
 sql("UPDATE admin_ticket_sessions SET expires_at=now()-interval '1 second' WHERE user_id=(SELECT id FROM auth_users WHERE username='staging-other')",'merchant_restore_drill')
 check(b'Sign In' in other.mvc('/Admin/Orders')[1]);other=Client('other').mvc_login()
 # Browser logout revokes backend and durable local ticket, including after restart.
 import re,urllib.parse
 page=other.mvc('/')[1].decode();token=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',page)[1]
 request=urllib.request.Request('https://localhost:9443/Account/Logout',data=urllib.parse.urlencode({'__RequestVerificationToken':token}).encode())
 with other.http.open(request) as response:check(response.status==200)
 run('restart','admin');wait_ready();check(b'Sign In' in other.mvc('/Admin/Orders')[1]);other=Client('other').mvc_login()
 # Expiry and authoritative operator revocation, role changes and password changes remain effective.
 operator('role','other','Cashier');check(other.mvc('/Admin/Orders')[0]==200) # Follows the safe redirect to login.
 check(b'Sign In' in other.mvc('/Admin/Orders')[1]);operator('role','other','Administrator');other=Client('other').mvc_login();operator('disable','other');check(b'Sign In' in other.mvc('/Admin/Orders')[1]);operator('password','cashier');check(cashier.call('/api/auth/me')[0]==401)
 check(admin.call('/api/auth/logout',{})[0]==204);check(admin.call('/api/auth/me')[0]==401)
 # Login throttling cannot be evaded by forged XFF at the public edge. Run last.
 anon=Client('admin');anon.csrf();statuses=[]
 for i in range(65):statuses.append(probe('/api/auth/login',{'username':'nonexistent','password':'invalid'},client=anon.http,headers={'X-CSRF-TOKEN':anon.token,'X-Forwarded-For':'203.0.113.'+str(i%255)})[0])
 check(429 in statuses)
 (evidence/'staging-results.json').write_text(json.dumps({'checks':checks,'result':'passed','capacity':timings,'scope':'isolated single-instance HTTPS Compose; not a production SLA','restoredTables':list(before_restore)},indent=2))
 print(f'Staging operational drill passed: {checks} assertions; real TLS, durable sessions, restarts, outage, exact-once retries, migration concurrency and encrypted restore.')
finally:
 # Only safe, bounded evidence. No dumps, secret mounts, key files, cookies or HTTP bodies are uploaded.
 logs=run('logs','--no-color',ok=False).stdout;(evidence/'staging.log').write_text(logs)
 run('down','--volumes','--remove-orphans',ok=False)
