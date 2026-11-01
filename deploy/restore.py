"""Restore only into an explicitly named isolated database, never over an existing operational database."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile,re
p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('--target',required=True);p.add_argument('--confirm-isolated',action='store_true');p.add_argument('--private-key',default='/run/secrets/backup_key.pem');a=p.parse_args()
if not a.confirm_isolated or not re.fullmatch(r'merchant_restore_[a-z0-9_]+',a.target):raise SystemExit('Only explicitly confirmed merchant_restore_* isolated targets are permitted.')
backup=pathlib.Path(a.backup);m=json.loads(backup.with_suffix('.json').read_text());assert hashlib.sha256(backup.read_bytes()).hexdigest()==m['ciphertextSha256'],'Backup checksum failed'
os.umask(0o077)
with tempfile.TemporaryDirectory() as tmp:
 dump=pathlib.Path(tmp)/'restore.dump';subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(backup),'-inkey',a.private_key,'-out',str(dump)],check=True)
 subprocess.run(['createdb',a.target],check=True) # Refuses an existing target.
 subprocess.run(['pg_restore','--exit-on-error','--single-transaction','--no-owner','--no-privileges','-d',a.target,str(dump)],check=True)
migration=pathlib.Path(__file__).with_name('migrate.py');migration_args=['python3',str(migration)]
if not pathlib.Path('/migrations').exists():migration_args+=['--directory',str(migration.parents[1]/'db/migrations'),'--schema',str(migration.parents[1]/'db/init/001_schema.sql')]
subprocess.run(migration_args,env={**os.environ,'PGDATABASE':a.target},check=True)
subprocess.run(['psql','-X','-q','-v','ON_ERROR_STOP=1','-d',a.target],input="BEGIN; INSERT INTO auth_restore_blocks(user_id) SELECT id FROM auth_users ON CONFLICT DO NOTHING; INSERT INTO security_events(id,category,outcome,correlation_id) VALUES(gen_random_uuid(),'restore_quarantined','blocked',replace(gen_random_uuid()::text,'-','')); COMMIT;",text=True,check=True)
print('All restored identities are quarantined pending separately authorized reconciliation. Isolated restore completed. Verify invariants and protected key recovery before any application cutover.')
