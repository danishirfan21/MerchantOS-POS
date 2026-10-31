"""One PostgreSQL session, advisory lock, checksum ledger and atomic per-file migrations."""
import argparse,hashlib,pathlib,re,subprocess,os
p=argparse.ArgumentParser();p.add_argument('--directory',default='/migrations');p.add_argument('--schema',default='/schema/001_schema.sql');p.add_argument('--seed-demo',action='store_true');a=p.parse_args()
files=sorted(pathlib.Path(a.directory).glob('*.sql'));assert files,'No migrations found'
commands=[r'\set ON_ERROR_STOP on',"SET statement_timeout='60s'; SELECT pg_advisory_lock(717007);",'CREATE TABLE IF NOT EXISTS merchant_migrations(version text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now());',"SELECT to_regclass('products') IS NULL AS fresh \\gset",r'\if :fresh','BEGIN;',pathlib.Path(a.schema).read_text(),'COMMIT;',r'\endif']
for file in files:
 assert re.fullmatch(r'\d{3}_[a-z_]+\.sql',file.name),'Invalid migration filename'
 raw=file.read_text();sha=hashlib.sha256(raw.encode()).hexdigest();body=re.sub(r'(?im)^\s*(BEGIN|COMMIT);\s*$','',raw)
 commands += [f"DO $$ BEGIN IF EXISTS(SELECT 1 FROM merchant_migrations WHERE version='{file.name}' AND sha256<>'{sha}') THEN RAISE EXCEPTION 'Migration checksum mismatch'; END IF; END $$;",f"SELECT NOT EXISTS(SELECT 1 FROM merchant_migrations WHERE version='{file.name}') AS apply \\gset",r'\if :apply','BEGIN;',body,f"INSERT INTO merchant_migrations(version,sha256) VALUES('{file.name}','{sha}');",'COMMIT;',r'\endif']
if a.seed_demo:commands += [r'\if :fresh',pathlib.Path('/schema/002_seed.sql').read_text(),r'\endif']
commands += ['SELECT pg_advisory_unlock(717007);']
r=subprocess.run(['psql','-X','-q'],input='\n'.join(commands),text=True,capture_output=True)
if r.returncode:raise SystemExit('Migration failed; no partially applied current migration committed. Inspect migration files/ledger with operator credentials.')
print('Migrations verified/applied with advisory lock and checksum ledger; existing records preserved.')
