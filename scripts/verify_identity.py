"""Real PostgreSQL identity lifecycle/concurrency checks on an isolated API process and users."""
import os,sys,pathlib,subprocess,time,json,uuid,urllib.request,urllib.error,http.cookiejar,concurrent.futures,copy,secrets,base64,tempfile
from mfa_fixture import totp,take
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only identity fixture')
root=pathlib.Path(__file__).resolve().parents[1];project=root/'services/merchant-api/MerchantOS.Api.csproj';base='http://127.0.0.1:5082';checks=0
private=pathlib.Path(tempfile.mkdtemp(prefix='merchant-identity-'));private.chmod(0o700)
def check(value,label):
 global checks
 assert value,label;checks+=1
def sql(query,fail=False):
 r=subprocess.run(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-v','ON_ERROR_STOP=1','-Atc',query],text=True,capture_output=True)
 if fail:return r.returncode!=0
 assert r.returncode==0,'Identity fixture SQL failed';return r.stdout.strip()
def account(name,op='create',password=None,secret=None,role='Administrator',extra=None):
 env={**os.environ,'Operations__AllowAccountCommand':'true','Account__Username':name,'Account__Role':role,'Account__Operation':op,'Operations__OperatorCase':str(uuid.uuid4()),'Operations__AllowRecovery':'true','Operations__AllowMfaReset':'true'}
 if password:env['Account__Password']=password
 if secret:
  path=private/(name+'.secret');path.touch(mode=0o600,exist_ok=True);path.write_text(secret);code=private/(name+'.confirmation');code.touch(mode=0o600,exist_ok=True);code.write_text(totp(secret));env.update({'Operations__AllowMfaEnrollment':'true','Account__MfaSecretFile':str(path),'Account__CodeFile':str(code),'Account__RecoveryFile':str(private/(name+'.codes')),'Account__RecoveryCount':'100'})
 if extra:env.update(extra)
 r=subprocess.run([os.environ.get('DOTNET_EXE','dotnet'),'run','--project',str(project),'-c','Release','--no-build','--no-launch-profile','--','--account'],env=env,capture_output=True,text=True);assert r.returncode==0,'Controlled identity fixture operation failed'
class Client:
 def __init__(self,jar=None):
  self.jar=jar if jar is not None else http.cookiejar.CookieJar();self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar));self.token=''
 def call(self,path,payload=None,csrf=True):
  req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json',**({'X-CSRF-TOKEN':self.token} if csrf and payload is not None else {})})
  try:
   with self.http.open(req,timeout=15) as r:status=r.status;raw=r.read()
  except urllib.error.HTTPError as e:status=e.code;raw=e.read()
  try:data=json.loads(raw) if raw else None
  except ValueError:data=None
  return status,data
 def csrf(self):s,b=self.call('/api/auth/csrf');assert s==200,'CSRF fixture';self.token=b['token'];return self
 def login(self,name,password):self.csrf();return self.call('/api/auth/login',{'username':name,'password':password})
 def clone(self):
  jar=http.cookiejar.CookieJar()
  for c in self.jar:jar.set_cookie(copy.copy(c))
  result=Client(jar);result.token=self.token;return result
 def factor(self,**kw):return self.call('/api/auth/mfa/complete',kw)
 def me(self):return self.call('/api/auth/me')[0]
def fresh(enrolled=False):
 name='m8-'+uuid.uuid4().hex[:12];password=secrets.token_urlsafe(30);print('::add-mask::'+password,flush=True);account(name,password=password)
 secret=base64.b32encode(secrets.token_bytes(32)).decode().rstrip('=')
 if enrolled:account(name,'mfa-seed',secret=secret)
 return name,password,secret
def sign(name,password,recovery):
 c=Client();check(c.login(name,password)[0]==202,'Admin primary login remains restricted');check(c.factor(recoveryCode=recovery)[0]==200,'One-time factor completes login');c.csrf();return c
server=subprocess.Popen([os.environ.get('DOTNET_EXE','dotnet'),'run','--project',str(project),'-c','Release','--no-build','--no-launch-profile'],env={**os.environ,'ASPNETCORE_URLS':base},stdout=open('identity-api.log','w'),stderr=subprocess.STDOUT)
try:
 for _ in range(60):
  try:
   if Client().call('/api/health/ready')[0]==200:break
  except OSError:pass
  time.sleep(1)
 else:raise RuntimeError('Isolated identity API failed readiness')
 name,pw,_=fresh();client=Client();status,challenge=client.login(name,pw);check(status==202 and challenge['step']=='enroll','New administrator must enroll')
 for path in ['/api/admin/reports/sales','/api/admin/products/p01','/api/admin/audit','/api/ops/metrics','/api/admin/reports/orders.csv','/api/admin/security-events']:check(client.call(path)[0]==401,'Password-only admin cannot access '+path)
 check(client.call('/api/auth/mfa/enrollment',{},csrf=False)[0]==400,'Enrollment enforces CSRF')
 status,info=client.call('/api/auth/mfa/enrollment',{});check(status==200 and info['otpAuthUri'].startswith('otpauth://'),'Local enrollment material returned')
 check(client.call('/api/auth/mfa/enrollment',{})[0]==401,'Enrollment material cannot be redisplayed')
 secret=info['secret'];check(client.factor(code='invalid')[0]==401,'Malformed factor rejected');check(client.factor(code=totp(secret,-3))[0]==401,'Expired factor rejected')
 status,complete=client.factor(code=totp(secret));check(status==200,'Valid TOTP confirms enrollment');codes=complete['recoveryCodes'];check(len(codes)==10,'Initial one-time recovery batch');client.csrf();check(client.me()==200,'MFA session authorized')
 check(client.factor(code=totp(secret))[0]==401,'Consumed challenge cannot issue another session')
 replay=Client();check(replay.login(name,pw)[0]==202,'New verification challenge');check(replay.factor(code=totp(secret))[0]==401,'Accepted TOTP step cannot be reused')
 check(replay.factor(recoveryCode=codes[0])[0]==200,'Recovery is a real second factor');replay.csrf()
 again=Client();again.login(name,pw);check(again.factor(recoveryCode=codes[0])[0]==401,'Recovery code cannot be replayed')
 # Concurrent identical redemption uses actual row locks and committed session issuance.
 n,p,s=fresh(True);c=Client();c.login(n,p);candidate=totp(s,1);clones=[c.clone(),c.clone()]
 with concurrent.futures.ThreadPoolExecutor() as pool:results=list(pool.map(lambda x:x.factor(code=candidate)[0],clones))
 check(sorted(results)==[200,401],'Concurrent identical TOTP accepted exactly once')
 recovery=take(private/(n+'.codes'));c=Client();c.login(n,p);clones=[c.clone(),c.clone()]
 with concurrent.futures.ThreadPoolExecutor() as pool:results=list(pool.map(lambda x:x.factor(recoveryCode=recovery)[0],clones))
 check(sorted(results)==[200,401],'Concurrent recovery redemption accepted exactly once')
 # Durable restricted challenge persists across API restart, without lifetime renewal.
 c=Client();c.login(n,p);expiry=sql("SELECT expires_at::text FROM auth_challenges WHERE user_id=(SELECT id FROM auth_users WHERE username='"+n+"')")
 server.terminate();server.wait(timeout=15)
 server=subprocess.Popen([os.environ.get('DOTNET_EXE','dotnet'),'run','--project',str(project),'-c','Release','--no-build','--no-launch-profile'],env={**os.environ,'ASPNETCORE_URLS':base},stdout=open('identity-api.log','a'),stderr=subprocess.STDOUT)
 for _ in range(40):
  try:
   if Client().call('/api/health/ready')[0]==200:break
  except OSError:pass
  time.sleep(1)
 check(sql("SELECT expires_at::text FROM auth_challenges WHERE user_id=(SELECT id FROM auth_users WHERE username='"+n+"')")==expiry,'Restart does not extend pending expiry')
 check(c.factor(recoveryCode=take(private/(n+'.codes')))[0]==200,'Restricted challenge survives restart');c.csrf();check(c.me()==200,'Completed MFA persists in database')
 # Current-password change revokes every session, including the current session.
 second=sign(n,p,take(private/(n+'.codes')));new=secrets.token_urlsafe(30);print('::add-mask::'+new,flush=True)
 check(c.call('/api/auth/password',{'currentPassword':'invalid','newPassword':new})[0]==401,'Current password is required')
 check(c.call('/api/auth/password',{'currentPassword':p,'newPassword':new},csrf=False)[0]==400,'Password change requires CSRF')
 check(c.call('/api/auth/password',{'currentPassword':p,'newPassword':new})[0]==204,'Password changes securely');check(c.me()==401 and second.me()==401,'Password change revokes current and other sessions')
 check(Client().login(n,p)[0]==401,'Old password no longer authenticates')
 # Operator recovery preserves the factor and forces replacement before full access.
 temp=secrets.token_urlsafe(30);replacement=secrets.token_urlsafe(30)
 for value in [temp,replacement]:print('::add-mask::'+value,flush=True)
 account(n,'recover',password=temp);c=Client();status,ch=c.login(n,temp);check(status==202 and ch['step']=='verify' and ch['mustChangePassword'],'Password reset preserves MFA and forces replacement')
 check(c.factor(recoveryCode=take(private/(n+'.codes')))[0]==400,'Temporary password cannot get unrestricted access')
 check(c.factor(recoveryCode=take(private/(n+'.codes')),newPassword=temp)[0]==400,'Temporary credential must actually change')
 check(c.factor(recoveryCode=take(private/(n+'.codes')),newPassword=replacement)[0]==200,'Replacement plus existing MFA completes recovery');c.csrf()
 # Role / disable / MFA reset invalidate authority and pending challenges.
 pending=Client();pending.login(n,replacement);account(n,'mfa-reset');check(c.me()==401,'MFA reset revokes verified sessions');check(pending.factor(code=totp(s))[0]==401,'MFA reset invalidates pending challenges')
 nextlogin=Client();check(nextlogin.login(n,replacement)[1]['step']=='enroll','MFA reset requires new confirmation, not password-only access')
 nextlogin.call('/api/auth/mfa/cancel',{});check(nextlogin.factor(code=totp(s))[0]==401,'Cancellation invalidates restricted challenge')
 enrolled,pwd,sec=fresh(True);active=sign(enrolled,pwd,take(private/(enrolled+'.codes')));pending=Client();pending.login(enrolled,pwd)
 sql("UPDATE auth_challenges SET expires_at=now()-interval '1 second' WHERE user_id=(SELECT id FROM auth_users WHERE username='"+enrolled+"')")
 check(pending.factor(recoveryCode=take(private/(enrolled+'.codes')))[0]==401,'Expired challenge rejected')
 account(enrolled,'role',role='Cashier');check(active.me()==401,'Role change invalidates prior sessions')
 account(enrolled,'disable');check(Client().login(enrolled,pwd)[0]==401,'Disabled account blocked')
 # Persistent MFA lockout cannot be reset by successful primary-password validation.
 locked,pwd,sec=fresh(True);bad=Client();bad.login(locked,pwd)
 for _ in range(5):check(bad.factor(code='000000' if totp(sec)!='000000' else '999999')[0]==401,'Bad factor rejected')
 check(Client().login(locked,pwd)[0]==401,'Factor lockout persists across new primary login')
 # No secret-bearing columns or runtime mutation privilege on security records.
 event=json.loads(sql("SELECT coalesce(json_agg(row_to_json(x)),'[]') FROM (SELECT * FROM security_events LIMIT 1000) x"));allowed={'id','created_at','category','actor_id','target_id','outcome','correlation_id'}
 check(all(set(e)==allowed for e in event),'Security records have only the safe field contract');serialized=json.dumps(event)
 check(secret not in serialized and pw not in serialized and all(code not in serialized for code in codes),'No enrollment/recovery/password values in event records')
 check(sql("SELECT count(*)>0 FROM security_events WHERE category='mfa_enrolled'")=='t','Enrollment audit recorded');check(sql("SELECT count(*)>0 FROM security_events WHERE category='recovery_code_redeemed'")=='t','Recovery audit recorded')
 # Rate test last, so legitimate cases are never bypassed by loosening the policy.
 statuses=[];anon=Client().csrf()
 for _ in range(65):statuses.append(anon.factor(code='000000')[0])
 check(429 in statuses,'Factor endpoint is rate limited')
 pathlib.Path('identity-results.json').write_text(json.dumps({'result':'passed','assertions':checks,'scope':'real PostgreSQL; no credential material'},indent=2));print('Identity lifecycle integration passed: '+str(checks)+' assertions; concurrency, MFA, recovery, revocation and events.')
finally:
 server.terminate()
 try:server.wait(timeout=15)
 except subprocess.TimeoutExpired:server.kill();server.wait()
