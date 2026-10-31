"""Disposable loopback PostgreSQL with random masked credentials; never use for deployment."""
import os,secrets,subprocess,time,pathlib,json
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only database fixture')
password=secrets.token_urlsafe(36);print('::add-mask::'+password,flush=True)
image=json.loads((pathlib.Path(__file__).parent/'images.json').read_text())['postgres'];name='merchantos-ci-'+os.environ['GITHUB_RUN_ID']
env={**os.environ,'POSTGRES_PASSWORD':password,'PGPASSWORD':password}
subprocess.run(['docker','run','--rm','-d','--name',name,'-p','127.0.0.1:5433:5432','-e','POSTGRES_DB=merchantos','-e','POSTGRES_USER=merchantos','-e','POSTGRES_PASSWORD',image],env=env,check=True,stdout=subprocess.DEVNULL)
for _ in range(40):
 if subprocess.run(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-Atc','SELECT 1'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
 time.sleep(1)
else:raise SystemExit('Disposable PostgreSQL failed readiness')
with open(os.environ['GITHUB_ENV'],'a') as f:
 f.write('PGPASSWORD='+password+'\nTEST_DB_PASSWORD='+password+'\nConnectionStrings__MerchantDb=Host=127.0.0.1;Port=5433;Database=merchantos;Username=merchantos;Password='+password+'\n')
print('Disposable PostgreSQL ready on loopback; credentials masked.')
