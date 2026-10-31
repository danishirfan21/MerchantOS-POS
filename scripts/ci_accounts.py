"""Provision ephemeral CI identities; never echoes secrets or puts them into artifacts."""
import os,secrets,subprocess
from pathlib import Path
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only account fixture')
exe=os.environ.get('DOTNET_EXE','dotnet');project=Path(__file__).resolve().parent.parent/'services/merchant-api/MerchantOS.Api.csproj'
for name,role in [('ADMIN','Administrator'),('CASHIER','Cashier'),('OTHER','Cashier'),('LOCKED','Cashier')]:
 username='ci-'+name.lower();password=secrets.token_urlsafe(30)
 print('::add-mask::'+password,flush=True)
 with open(os.environ['GITHUB_ENV'],'a') as f:f.write(f'TEST_{name}_USERNAME={username}\nTEST_{name}_PASSWORD={password}\n')
 env={**os.environ,'Bootstrap__Username':username,'Bootstrap__Password':password,'Bootstrap__Role':role}
 subprocess.run([exe,'run','--project',str(project),'-c','Release','--no-build','--','--bootstrap-user'],env=env,check=True,stdout=subprocess.DEVNULL)
print('Ephemeral CI identities provisioned.')
