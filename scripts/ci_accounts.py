"""Provision disposable identities and real second factors; stdout never contains material."""
import os,secrets,subprocess,tempfile,pathlib,base64
from mfa_fixture import totp
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only account fixture')
exe=os.environ.get('DOTNET_EXE','dotnet');project=pathlib.Path(__file__).resolve().parent.parent/'services/merchant-api/MerchantOS.Api.csproj'
private=pathlib.Path(tempfile.mkdtemp(prefix='merchant-mfa-'));private.chmod(0o700)
def export(name,value,secret=False):
 if secret:print('::add-mask::'+value,flush=True)
 with open(os.environ['GITHUB_ENV'],'a') as f:f.write(name+'='+value+'\n')
for name,role in [('ADMIN','Administrator'),('CASHIER','Cashier'),('OTHER','Cashier'),('LOCKED','Cashier')]:
 username='ci-'+name.lower();password=secrets.token_urlsafe(30);export('TEST_'+name+'_USERNAME',username);export('TEST_'+name+'_PASSWORD',password,True)
 env={**os.environ,'Operations__AllowAccountCommand':'true','Account__Operation':'create','Account__Username':username,'Account__Password':password,'Account__Role':role}
 subprocess.run([exe,'run','--project',str(project),'-c','Release','--no-build','--','--account'],env=env,check=True,stdout=subprocess.DEVNULL)
 if role=='Administrator':
  secret=base64.b32encode(secrets.token_bytes(32)).decode().rstrip('=');code=totp(secret)
  for file,value in [('secret',secret),('confirmation',code)]:
   path=private/file;path.touch(mode=0o600);path.write_text(value)
  env.update({'Account__Operation':'mfa-seed','Operations__AllowMfaEnrollment':'true','Account__MfaSecretFile':str(private/'secret'),'Account__CodeFile':str(private/'confirmation'),'Account__RecoveryFile':str(private/'codes'),'Account__RecoveryCount':'100'})
  subprocess.run([exe,'run','--project',str(project),'-c','Release','--no-build','--','--account'],env=env,check=True,stdout=subprocess.DEVNULL)
  export('TEST_ADMIN_RECOVERY_FILE',str(private/'codes'));export('TEST_ADMIN_MFA_SECRET',secret,True)
print('Ephemeral CI identities and real one-time second factors provisioned.')
