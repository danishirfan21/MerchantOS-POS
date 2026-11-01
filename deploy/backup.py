"""Encrypted, bounded-retention PostgreSQL backups. Plaintext dump exists only in private tmpfs."""
import argparse,datetime,hashlib,json,os,pathlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--output',default='/backups');p.add_argument('--public-cert',default='/run/secrets/backup_cert.pem');a=p.parse_args();os.umask(0o077)
out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True);stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');dest=out/(stamp+'.dump.cms')
with tempfile.TemporaryDirectory() as tmp:
 dump=pathlib.Path(tmp)/'data.dump'
 with dump.open('wb') as f:subprocess.run(['pg_dump','-Fc','--no-owner','--no-privileges'],stdout=f,check=True)
 subprocess.run(['pg_restore','--list',str(dump)],stdout=subprocess.DEVNULL,check=True)
 partial=out/(dest.name+'.partial')
 subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-cbc','-in',str(dump),'-outform','DER','-out',str(partial),a.public_cert],check=True)
 partial.rename(dest)
manifest={'ciphertextSha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'createdUtc':stamp,'format':'pg_dump-custom+CMS-AES256','restoreVerified':False}
(dest.with_suffix('.json')).write_text(json.dumps(manifest));cutoff=datetime.datetime.now().timestamp()-7*86400
for old in out.glob('*.dump.cms'):
 if old.stat().st_mtime<cutoff:old.unlink();old.with_suffix('.json').unlink(missing_ok=True)
print('Encrypted backup created; retention 7 days. A restore drill is still required.')
