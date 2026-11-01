"""Transactional outbox exporter. Remote outages leave durable pending events, never bypass MFA."""
import argparse,json,pathlib,subprocess,tempfile
import psycopg
from psycopg.rows import dict_row
from common import atomic_json,canonical,digest,iso,read_config
from storage import Store

def export(config_path,storage_path):
 config=read_config(config_path);store=Store(storage_path)
 with psycopg.connect(config['dsn'],row_factory=dict_row,connect_timeout=3) as db:
  db.execute('SELECT pg_advisory_xact_lock(717029)')
  state=db.execute('SELECT * FROM security_export_state WHERE singleton FOR UPDATE').fetchone()
  if config.get('minimumCheckpoint'):
   verify_checkpoint(storage_path,config['minimumCheckpoint'],config['witnessCertificate']);minimum=json.loads(pathlib.Path(config['minimumCheckpoint']).read_text());verify_chain(store,state['head_key'],state['head_hash'],minimum)
  rows=db.execute('SELECT sequence,payload FROM security_event_outbox WHERE delivered_at IS NULL ORDER BY sequence LIMIT 100').fetchall()
  if not rows:return {'exported':0,'headKey':state['head_key'],'headHash':state['head_hash'],'lastSequence':state['last_sequence']}
  if rows[0]['sequence']<=state['last_sequence']:raise ValueError('Audit cursor rollback detected')
  batch={'schema':1,'previousKey':state['head_key'],'previousHash':state['head_hash'],'firstSequence':rows[0]['sequence'],'lastSequence':rows[-1]['sequence'],'events':rows}
  data=canonical(batch);sha=digest(data);stored=store.put('batches/'+str(batch['lastSequence']).zfill(20)+'-'+sha+'.json',data)
  ids=[r['sequence'] for r in rows]
  db.execute('UPDATE security_event_outbox SET delivered_at=clock_timestamp(),batch_key=%s,batch_hash=%s WHERE sequence=ANY(%s)',(stored['key'],sha,ids))
  db.execute('UPDATE security_export_state SET last_sequence=%s,head_key=%s,head_hash=%s,updated_at=clock_timestamp() WHERE singleton',(batch['lastSequence'],stored['key'],sha))
 return {'exported':len(rows),'headKey':stored['key'],'headHash':sha,'lastSequence':batch['lastSequence'],'verifiedUtc':iso()}

def verify_chain(store,head_key,head_hash,minimum=None):
 seen=set();events=set();batches=0;last=None;count=0;key=head_key;sha=head_hash;minimum_seen=minimum is None
 while key:
  if key in seen:raise ValueError('Audit chain cycle/replay')
  seen.add(key)
  if minimum and key==minimum['headKey'] and sha==minimum['headHash']:minimum_seen=True
  data=store.get(key)
  if digest(data)!=sha:raise ValueError('Modified audit batch')
  batch=json.loads(data);records=batch['events']
  if not records or batch['schema']!=1 or batch['firstSequence']!=records[0]['sequence'] or batch['lastSequence']!=records[-1]['sequence']:raise ValueError('Invalid audit batch contract')
  order=[r['sequence'] for r in records]
  if order!=sorted(set(order)) or (last is not None and order[-1]>=last):raise ValueError('Reordered audit events')
  for row in records:
   event=row['payload']
   if set(event)!={'id','timestamp','category','actorId','targetId','outcome','correlationId'} or event['id'] in events:raise ValueError('Duplicate/private event payload')
   events.add(event['id'])
  count+=len(records);batches+=1;last=order[0];key=batch['previousKey'];sha=batch['previousHash']
  if bool(key)!=bool(sha):raise ValueError('Broken audit parent')
 if not minimum_seen:raise ValueError('Audit rollback/fork does not extend trusted checkpoint')
 return {'batches':batches,'events':count,'headKey':head_key,'headHash':head_hash}

def checkpoint(storage_path,head_key,head_hash,output,certificate,private_key,previous=None):
 # Run by a separate witness/custodian. Exporter never mounts this private key.
 minimum=None
 if previous:
  verify_checkpoint(storage_path,previous,certificate);minimum=json.loads(pathlib.Path(previous).read_text())
 checked=verify_chain(Store(storage_path),head_key,head_hash,minimum);checked.update(schema=1,witnessedUtc=iso());output=pathlib.Path(output)
 if output.exists() or output.with_suffix('.p7s').exists():raise ValueError('Checkpoint output must be new')
 atomic_json(output,checked)
 subprocess.run(['openssl','cms','-sign','-binary','-md','sha256','-in',str(output),'-signer',certificate,'-inkey',private_key,'-outform','DER','-out',str(output.with_suffix('.p7s')),'-nosmimecap','-noattr'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 return checked

def verify_checkpoint(storage_path,path,certificate):
 path=pathlib.Path(path)
 subprocess.run(['openssl','cms','-verify','-binary','-inform','DER','-in',str(path.with_suffix('.p7s')),'-content',str(path),'-nointern','-certfile',certificate,'-noverify','-out','/dev/null'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 trusted=json.loads(path.read_text());result=verify_chain(Store(storage_path),trusted['headKey'],trusted['headHash'])
 if result['events']!=trusted['events'] or result['batches']!=trusted['batches']:raise ValueError('Missing audit records')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['export','checkpoint','verify']);p.add_argument('--storage',required=True);p.add_argument('--database');p.add_argument('--checkpoint');p.add_argument('--certificate');p.add_argument('--private-key');p.add_argument('--head-key');p.add_argument('--head-hash');p.add_argument('--previous');p.add_argument('--status-file');a=p.parse_args()
 try:
  if a.action=='export':result=export(a.database,a.storage)
  elif a.action=='checkpoint':result=checkpoint(a.storage,a.head_key,a.head_hash,a.checkpoint,a.certificate,a.private_key,a.previous)
  else:result=verify_checkpoint(a.storage,a.checkpoint,a.certificate)
  if a.status_file:atomic_json(a.status_file,{'result':'passed','verifiedUtc':iso(),'events':result.get('events',0),'headHash':result.get('headHash')})
  print(json.dumps(result))
 except Exception as error:
  if a.status_file:atomic_json(a.status_file,{'result':'failed','verifiedUtc':iso(),'failureCategory':type(error).__name__})
  raise SystemExit('Audit operation failed: '+type(error).__name__+'; private details omitted; pending events retained')
