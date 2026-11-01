"""Bounded, non-overlapping encrypted backup/upload cycle for a systemd timer."""
import argparse,fcntl,json,os,pathlib,subprocess,sys,tarfile,tempfile,time
from common import atomic_json,digest,iso,now,read_config
from storage import Store

def retrieve(storage_path,receipt_path,output,witness_certificate=None):
 if not witness_certificate:raise ValueError("Pinned independent witness certificate required before recovery")
 from witness import verify
 verify(receipt_path,witness_certificate)
 store=Store(storage_path);receipt=json.loads(pathlib.Path(receipt_path).read_text());output=pathlib.Path(output)
 if output.exists():raise ValueError('Recovery output must be a fresh directory')
 output.mkdir(mode=0o700,parents=True)
 for name,obj in receipt['objects'].items():
  if pathlib.Path(name).name!=name:raise ValueError('Invalid recovery filename')
  store.download(obj['key'],obj['versionId'],output/name,obj['sha256'])
 return {'retrievedObjects':len(receipt['objects']),'verifiedUtc':iso()}

def run(config_path):
 config=read_config(config_path);state=pathlib.Path(config['stateDirectory']);state.mkdir(mode=0o700,parents=True,exist_ok=True)
 with (state/'backup.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy','overlapPrevented':True}
  started=time.monotonic();result={'status':'running','startedUtc':iso(),'lastSuccessfulUtc':None}
  previous=state/'backup-status.json'
  if previous.exists():result['lastSuccessfulUtc']=json.loads(previous.read_text()).get('lastSuccessfulUtc')
  atomic_json(previous,result)
  try:
   spool=pathlib.Path(config['spoolDirectory']);spool.mkdir(mode=0o700,parents=True,exist_ok=True);existing=set(spool.glob('*.dump.cms'))
   env={**os.environ,**{k:v for k,v in config.get('databaseEnvironment',{}).items() if k in ['PGHOST','PGPORT','PGUSER','PGDATABASE','PGPASSFILE']}}
   command=[sys.executable,str(pathlib.Path(__file__).resolve().parents[1]/'backup.py'),'--output',str(spool),'--public-cert',config['encryptionCertificate'],'--retain-all-local']
   subprocess.run(['openssl','x509','-in',config['encryptionCertificate'],'-checkend','0','-noout'],check=True,capture_output=True,timeout=10)
   subprocess.run(command,env=env,check=True,capture_output=True,timeout=300)
   new=set(spool.glob('*.dump.cms'))-existing
   if len(new)!=1:raise ValueError('Exactly one completed encrypted backup required')
   backup=new.pop();files=[backup,backup.with_suffix('.json')];backup_seconds=time.monotonic()-started
   if config.get('protectedKeyDirectories'):
    # Archive only encrypted DP XML, never its private wrapping certificate or backup key.
    with tempfile.TemporaryDirectory() as tmp:
     archive=pathlib.Path(tmp)/'keys.tar'
     with tarfile.open(archive,'w') as tar:
      for role,directory in config['protectedKeyDirectories'].items():
       if role not in ['pos-keys','admin-keys']:raise ValueError('Unknown protected key scope')
       for file in sorted(pathlib.Path(directory).glob('*.xml')):
        data=file.read_text()
        if '<encryptedSecret' not in data or '<masterKey' in data:raise ValueError('Key archive must contain protected XML only')
        tar.add(file,arcname=role+'/'+file.name)
     encrypted=spool/(backup.name+'.keys.cms');subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-cbc','-in',str(archive),'-outform','DER','-out',str(encrypted),config['encryptionCertificate']],check=True,capture_output=True,timeout=60);files.append(encrypted)
   upload_started=time.monotonic();store=Store(config['storageConfiguration']);objects={}
   for file in files:objects[file.name]=store.put_file('backups/'+backup.name+'/'+file.name,file)
   receipt={'schema':1,'createdUtc':iso(),'objects':objects,'retention':store.policy(),'restoreVerified':False}
   receipt_data=__import__('common').canonical(receipt);receipt_object=store.put('receipts/'+backup.name+'.json',receipt_data)
   atomic_json(state/'latest-backup-receipt.json',receipt)
   index_file=state/'uploaded-index.json';index=json.loads(index_file.read_text()) if index_file.exists() else {};index.update(objects)
   for name,obj in list(index.items()):
    file=spool/name
    if file.exists() and file.stat().st_mtime<time.time()-7*86400:
     head=store.client.head_object(Bucket=store.bucket,Key=obj['key'],VersionId=obj['versionId'])
     if head.get('ObjectLockMode')=='COMPLIANCE' and head['ObjectLockRetainUntilDate']>now() and head.get('Metadata',{}).get('sha256')==obj['sha256']:file.unlink();del index[name]
   atomic_json(index_file,index)
   result.update(status='success',lastSuccessfulUtc=iso(),backupSeconds=round(backup_seconds,3),uploadSeconds=round(time.monotonic()-upload_started,3),totalSeconds=round(time.monotonic()-started,3),receipt=receipt_object)
   atomic_json(previous,result)
   return result
  except Exception as error:
   result.update(status='failed',finishedUtc=iso(),failureCategory=type(error).__name__);atomic_json(previous,result)
   raise RuntimeError('Backup cycle failed; inspect private operator configuration; no credentials logged') from None

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['run','retrieve']);p.add_argument('--config');p.add_argument('--storage');p.add_argument('--receipt');p.add_argument('--output');p.add_argument('--witness-certificate');a=p.parse_args()
 try:print(json.dumps(run(a.config) if a.action=='run' else retrieve(a.storage,a.receipt,a.output,a.witness_certificate)))
 except Exception as error:raise SystemExit('Backup operation failed: '+type(error).__name__+'; private details omitted')
