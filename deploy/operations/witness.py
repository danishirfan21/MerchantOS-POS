"""Pinned-certificate CMS signatures, executed only by the independent witness/custodian."""
import argparse,hashlib,json,pathlib,subprocess
from storage import Store

def sign(path,certificate,private_key):
 path=pathlib.Path(path);signature=path.with_suffix('.p7s')
 if signature.exists():raise ValueError('Never overwrite an independently retained signature')
 subprocess.run(['openssl','cms','-sign','-binary','-md','sha256','-in',str(path),'-signer',str(certificate),'-inkey',str(private_key),'-outform','DER','-out',str(signature),'-nosmimecap','-noattr'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def verify(path,certificate):
 path=pathlib.Path(path)
 subprocess.run(['openssl','cms','-verify','-binary','-inform','DER','-in',str(path.with_suffix('.p7s')),'-content',str(path),'-nointern','-certfile',str(certificate),'-noverify','-out','/dev/null'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def backup_checkpoint(storage,path,certificate,private_key):
 store=Store(storage);receipt=json.loads(pathlib.Path(path).read_text())
 for obj in receipt['objects'].values():
  response=store.client.get_object(Bucket=store.bucket,Key=obj['key'],VersionId=obj['versionId']);sha=hashlib.sha256()
  with response['Body'] as body:
   for chunk in iter(lambda:body.read(1024*1024),b''):sha.update(chunk)
  if sha.hexdigest()!=obj['sha256']:raise ValueError('Witness rejected backup object integrity')
 sign(path,certificate,private_key)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['backup-checkpoint','verify']);p.add_argument('--storage');p.add_argument('--document',required=True);p.add_argument('--certificate',required=True);p.add_argument('--private-key');a=p.parse_args()
 try:
  if a.action=='backup-checkpoint':backup_checkpoint(a.storage,a.document,a.certificate,a.private_key)
  else:verify(a.document,a.certificate)
  print('Independent witness operation completed; no private material logged.')
 except Exception as error:raise SystemExit('Witness verification failed: '+type(error).__name__)
