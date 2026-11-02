"""CI-only exercise of the documented launcher, including actual HTTPS and native accounts."""
import argparse,http.cookiejar,json,os,pathlib,ssl,subprocess,sys,tempfile,time,urllib.request,uuid
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Disposable CI only')
p=argparse.ArgumentParser();p.add_argument('--admin',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=pathlib.Path(__file__).resolve().parent.parent;directory=pathlib.Path(tempfile.mkdtemp(prefix='merchantos-demo-'))/'instance';start=time.monotonic()
def launch(action,*extra):subprocess.run([sys.executable,str(root/'deploy/demo.py'),action,'--directory',str(directory),*extra],check=True)
try:
 launch('init','--admin',str(pathlib.Path(a.admin).resolve()));launch('start');launch('status');s=directory/'secrets';ctx=ssl.create_default_context(cafile=str(s/'ca.crt'));jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(jar))
 def api(path,data=None,token=None):
  req=urllib.request.Request('https://localhost:8443'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json',**({'X-CSRF-TOKEN':token} if token else {})})
  with client.open(req,timeout=15) as response:return response.status,json.loads(response.read())
 token=api('/api/auth/csrf')[1]['token'];assert api('/api/auth/login',{'username':(s/'cashier_username').read_text(),'password':(s/'cashier_password').read_text()},token)[0]==200
 token=api('/api/auth/csrf')[1]['token'];products=api('/api/products')[1];assert len(products)==30
 stock=api('/api/inventory/p17')[1]['stock'];body={'items':[{'productId':'p17','quantity':1}],'discountPercent':5,'paymentMethod':'card','cashTenderedHalalas':None,'cardScenario':'success','idempotencyKey':str(uuid.uuid4())}
 sale=api('/api/checkout',body,token)[1];retry=api('/api/checkout',body,token)[1];assert sale['id']==retry['id'];assert api('/api/inventory/p17')[1]['stock']==stock-1;assert api('/api/orders/'+sale['id'])[1]['payableHalalas']==sale['payableHalalas']
 api('/api/auth/logout',{},token);token=api('/api/auth/csrf')[1]['token'];status,pending=api('/api/auth/login',{'username':(s/'admin_username').read_text(),'password':(s/'admin_password').read_text()},token);assert status==202 and pending.get('step')
 # No factor bypass: launcher creates an unenrolled administrator, never a password-only session.
 assert not any(c.name=='MerchantOS.Pos.Session' for c in jar)
 result={'schema':1,'checks':8,'result':'passed','startupAndSmokeMs':round((time.monotonic()-start)*1000,1),'fictionalCatalog':30,'duplicateOrderSuppressed':True,'adminMfaRequired':True,'publicProduction':'NO-GO'}
 pathlib.Path(a.output).write_text(json.dumps(result,indent=2));print('Documented demo launcher passed: 8 HTTPS/native-account checks.')
finally:
 if (directory/'demo.json').exists():launch('reset','--confirm-reset')
