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
print('Isolated restore completed. Verify invariants and protected key recovery before any application cutover.')
