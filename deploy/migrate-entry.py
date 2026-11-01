import os,subprocess,sys
args=[sys.executable,'/ops/migrate.py']
if os.environ.get('SEED_DEMO')=='true':args.append('--seed-demo')
subprocess.run(args,check=True);subprocess.run([sys.executable,'/ops/roles.py'],check=True)
