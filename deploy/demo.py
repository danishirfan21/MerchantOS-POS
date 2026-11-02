"""Private, disposable portfolio demo. Never deploys public listeners or resets another project."""
import argparse,json,os,pathlib,re,subprocess,sys,time,uuid,urllib.request,ssl
ROOT=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init','start','status','stop','reset']);p.add_argument('--directory',required=True);p.add_argument('--admin');p.add_argument('--confirm-reset',action='store_true');a=p.parse_args()
d=pathlib.Path(a.directory).resolve();marker=d/'demo.json'
def run(args,**kw):return subprocess.run(list(map(str,args)),check=True,**kw)
if a.action=='init':
 if not a.admin:raise SystemExit('--admin must identify the reviewed Admin checkout')
 admin=pathlib.Path(a.admin).resolve()
 if not (admin/'Dockerfile').is_file():raise SystemExit('Admin checkout not found')
 if any(c in str(d)+str(admin) for c in '\n\r'):raise SystemExit('Invalid path')
 run([sys.executable,ROOT/'deploy/init-local.py','--output',d]);project='merchantos_demo_'+uuid.uuid4().hex[:12]
 env=d/'staging.env';env.write_text(env.read_text().replace('COMPOSE_PROJECT_NAME=merchantos_staging','COMPOSE_PROJECT_NAME='+project)+'ADMIN_CONTEXT='+str(admin)+'\n')
 info={'schema':1,'project':project,'directory':str(d),'admin':str(admin),'posRevision':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'adminRevision':subprocess.check_output(['git','-C',str(admin),'rev-parse','HEAD'],text=True).strip(),'fictionalDataOnly':True,'publicProduction':'NO-GO'}
 marker.touch(mode=0o600);marker.write_text(json.dumps(info,indent=2));print('Disposable demo initialized. Credentials remain in private secrets files.');sys.exit()
if not marker.is_file():raise SystemExit('Not a generated MerchantOS demo directory')
info=json.loads(marker.read_text())
if info.get('directory')!=str(d) or not re.fullmatch('merchantos_demo_[a-f0-9]{12}',info.get('project','')):raise SystemExit('Demo marker mismatch')
# Compose environment cannot redirect destructive actions to another installation.
expected={'STAGING_DIR':str(d),'COMPOSE_PROJECT_NAME':info['project'],'ADMIN_CONTEXT':info['admin']}
values=dict(line.split('=',1) for line in (d/'staging.env').read_text().splitlines() if '=' in line)
if any(values.get(k)!=v for k,v in expected.items()):raise SystemExit('Demo configuration changed; refusing operation')
env={**os.environ,**expected,'SEED_DEMO':'true'}
base=['docker','compose','--env-file',str(d/'staging.env'),'-p',info['project'],'-f',str(ROOT/'deploy/compose.yml')]
def compose(*args):run(base+list(args),env=env)
if a.action=='start':
 if (d/'started').exists():raise SystemExit('Already initialized. Use status or docker compose up to resume; reset requires explicit confirmation.')
 compose('config','--quiet');compose('build');compose('up','-d','--wait','db');compose('run','--rm','migrate')
 # Operator capability and exactly three private files are mounted only into each one-shot command.
 for role,authority in [('admin','Administrator'),('cashier','Cashier')]:
  args=['run','--rm','--no-deps']
  for source,target in [('operator_connection','connection'),(role+'_username','username'),(role+'_password','password')]:args+=['-v',str(d/'secrets'/source)+':/operator/'+target+':ro']
  args+=['-e','ConnectionStrings__MerchantDbFile=/operator/connection','-e','Operations__AllowAccountCommand=true','-e','Account__Operation=create','-e','Account__UsernameFile=/operator/username','-e','Account__PasswordFile=/operator/password','-e','Account__Role='+authority,'pos-api','--account'];compose(*args)
 compose('up','-d','--wait','pos-api','admin','web');(d/'started').touch(mode=0o600)
if a.action in ['status','start']:
 context=ssl.create_default_context(cafile=str(d/'secrets/ca.crt'))
 for url in ['https://localhost:8443/api/health/ready','https://localhost:9443/health/ready']:
  with urllib.request.urlopen(url,context=context,timeout=10) as response:
   if response.status!=200:raise SystemExit('Demo readiness failed')
 print('POS https://localhost:8443/ | Admin https://localhost:9443/ | isolated demo only; human acceptance pending')
if a.action=='stop':compose('stop')
if a.action=='reset':
 if not a.confirm_reset:raise SystemExit('Reset deletes only this marked disposable demo database. Supply --confirm-reset.')
 compose('down','--volumes','--remove-orphans');print('Demo containers and database removed. Keep private recovery material until disposal is approved. Initialize a NEW directory for fresh identities and keys.')
