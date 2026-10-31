"""Generate private local staging material only; no public certificate requests or known passwords."""
import argparse,pathlib,os,secrets,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=pathlib.Path(a.output).resolve()
if out.exists() and any(out.iterdir()):raise SystemExit('Refusing to overwrite existing staging material.')
os.umask(0o077);out.mkdir(parents=True,exist_ok=True);s=out/'secrets';s.mkdir();uid=os.getuid() or 1654
for name in ['pos-keys','admin-keys','backups']:(out/name).mkdir(mode=0o700)
values={name:secrets.token_urlsafe(36) for name in ['db_password','pos_db_password','admin_db_password','pfx_password','dp_password','admin_password','cashier_password','other_password']}
for name,value in values.items():(s/name).write_text(value)
for name,value in [('admin_username','staging-admin'),('cashier_username','staging-cashier'),('other_username','staging-other')]:(s/name).write_text(value)
def run(*args):subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
run('req','-x509','-newkey','rsa:3072','-nodes','-keyout',s/'ca.key','-out',s/'ca.crt','-days','30','-subj','/CN=MerchantOS Local Staging CA')
run('req','-newkey','rsa:3072','-nodes','-keyout',s/'tls.key','-out',s/'tls.csr','-subj','/CN=localhost')
(s/'tls.ext').write_text('subjectAltName=DNS:localhost,DNS:pos-api,DNS:admin,IP:127.0.0.1\nextendedKeyUsage=serverAuth\nkeyUsage=digitalSignature,keyEncipherment\n')
run('x509','-req','-in',s/'tls.csr','-CA',s/'ca.crt','-CAkey',s/'ca.key','-CAcreateserial','-out',s/'tls.crt','-days','14','-extfile',s/'tls.ext')
run('pkcs12','-export','-in',s/'tls.crt','-inkey',s/'tls.key','-out',s/'tls.pfx','-passout','file:'+str(s/'pfx_password'))
run('req','-x509','-newkey','rsa:3072','-nodes','-keyout',s/'dp.key','-out',s/'dp.crt','-days','365','-subj','/CN=MerchantOS Data Protection')
run('pkcs12','-export','-in',s/'dp.crt','-inkey',s/'dp.key','-out',s/'dp.pfx','-passout','file:'+str(s/'dp_password'))
run('req','-x509','-newkey','rsa:3072','-nodes','-keyout',s/'backup_key.pem','-out',s/'backup_cert.pem','-days','365','-subj','/CN=MerchantOS Offline Backup Recovery')
# DB connections are mounted as files, never Compose environment values or Docker build args.
for name,user,password in [('pos_connection','merchant_pos','pos_db_password'),('admin_connection','merchant_admin_session','admin_db_password')]:
 (s/name).write_text('Host=db;Database=merchantos;Username='+user+';Password='+values[password]+';Timeout=3;Command Timeout=10')
(s/'pgpass').write_text('db:5432:*:merchantos:'+values['db_password']+'\n')
(out/'staging.env').write_text(f'STAGING_DIR={out}\nSTAGING_UID={uid}\nADMIN_CONTEXT=../../MerchantOS-Admin\nCOMPOSE_PROJECT_NAME=merchantos_staging\n')
for f in s.iterdir():f.chmod(0o600)
for f in [s/'ca.crt',s/'tls.crt',s/'backup_cert.pem']:f.chmod(0o644)
if os.getuid()==0:
 for folder in [out/'pos-keys',out/'admin-keys',s]:
  for x in [folder,*folder.iterdir()]:os.chown(x,uid,uid)
# Ephemeral test secrets masked and exported only within GitHub Actions; never print them elsewhere.
if os.environ.get('GITHUB_ACTIONS')=='true':
 with open(os.environ['GITHUB_ENV'],'a') as f:
  for name,value in values.items():
   print('::add-mask::'+value);f.write('STAGING_'+name.upper()+'='+value+'\n')
print('Private local staging material created. CA trust is local only; no public services configured.')
