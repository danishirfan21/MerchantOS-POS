"""Isolated real-PostgreSQL / TLS S3 / HTTP alert integration. No merchant data or live notifications."""
import concurrent.futures,copy,datetime,fcntl,json,os,pathlib,shutil,subprocess,sys,tempfile,time,uuid
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from common import atomic_json,canonical,digest,iso
from fixture import Fixture
from storage import Store
from audit import export,checkpoint,verify_checkpoint,verify_chain
from backup_job import run as backup_run,retrieve
from monitor import Alerts,request
from readiness import assess
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Disposable CI-only operations drill')
# Disposable plaintext dump/key fixtures stay on the runner's RAM-backed temporary filesystem.
os.environ['TMPDIR']='/dev/shm';tempfile.tempdir=None
root=pathlib.Path(__file__).resolve().parents[2];private=pathlib.Path(tempfile.mkdtemp(prefix='merchant-m9-'));private.chmod(0o700);checks=0
owner=psycopg.conninfo.make_conninfo(host='127.0.0.1',port=5433,dbname='merchantos',user='merchantos',password=os.environ['PGPASSWORD'])
def check(value,label):
 global checks
 assert value,label;checks+=1
def secret():
 import secrets
 value=secrets.token_urlsafe(36);print('::add-mask::'+value,flush=True)
 with open(os.environ['GITHUB_ENV'],'a') as output:output.write('TEST_M9_'+uuid.uuid4().hex+'_PASSWORD='+value+'\n')
 return value
def expect_failure(fn,label):
 try:fn()
 except Exception:check(True,label);return
 raise AssertionError(label)
def db(query,args=()):
 with psycopg.connect(owner,row_factory=dict_row) as connection:
  result=connection.execute(query,args)
  return result.fetchall() if result.description else []
# Use PostgreSQL 17 tools from the actual disposable server container, not an older runner client.
tools=private/'bin';tools.mkdir()
for name in ['pg_dump','pg_restore']:
 file=tools/name;file.write_text('''#!/usr/bin/env python3
import os,sys
name=os.path.basename(sys.argv[0]);args=sys.argv[1:];env=dict(os.environ)
if env.get('PGPASSFILE'):env['PGPASSWORD']=open(env['PGPASSFILE']).read().strip().split(':')[-1]
env['PGPORT']='5432';env['PGHOST']='127.0.0.1'
if name=='pg_restore' and args and not args[-1].startswith('-') and os.path.isfile(args[-1]):
 fd=os.open(args.pop(),os.O_RDONLY);os.dup2(fd,0)
command=['docker','exec','-i']
for key in ['PGPASSWORD','PGUSER','PGHOST','PGPORT','PGDATABASE']:
 if key in env:command+=['-e',key]
command+=['merchantos-ci-'+env['GITHUB_RUN_ID'],name]+args
os.execvpe('docker',command,env)
''');file.chmod(0o700)
os.environ['PATH']=str(tools)+os.pathsep+os.environ['PATH'];os.environ['PGCONNECT_TIMEOUT']='2'
secrets_path=private/'roles';secrets_path.mkdir(mode=0o700)
passwords={}
for name in ['pos','admin','backup','export','monitor','operator','audit_read']:
 value=secret();passwords[name]=value;atomic_json(private/(name+'-secret.json'),{'unused':True});path=secrets_path/({'pos':'pos_db_password','admin':'admin_db_password','backup':'backup_db_password','export':'export_db_password','monitor':'monitor_db_password','operator':'operator_db_password','audit_read':'audit_read_db_password'}[name]);path.write_text(value);path.chmod(0o600)
env={**os.environ,'MERCHANT_SECRETS':str(secrets_path),'PGHOST':'127.0.0.1','PGPORT':'5433','PGUSER':'merchantos','PGDATABASE':'merchantos'}
subprocess.run(['python3',str(root/'deploy/roles.py')],env=env,check=True,capture_output=True)
export_config=private/'export.json';atomic_json(export_config,{'dsn':psycopg.conninfo.make_conninfo(host='127.0.0.1',port=5433,dbname='merchantos',user='merchant_security_exporter',password=passwords['export'])})
fixture=Fixture(private/'endpoint');storage=fixture.configuration('audit');fixture.initialize(storage);store=Store(storage)
timings={};capabilities={}
try:
 # Transactional delivery: rolled-back business/security events never enter the outbox.
 before=db('SELECT count(*) AS n FROM security_event_outbox')[0]['n']
 with psycopg.connect(owner) as connection:
  try:
   with connection.transaction():connection.execute("INSERT INTO security_events(id,category,outcome,correlation_id) VALUES(%s,'operator_revoke','success',%s)",(uuid.uuid4(),uuid.uuid4().hex));raise RuntimeError('isolated rollback')
  except RuntimeError:pass
 check(db('SELECT count(*) AS n FROM security_event_outbox')[0]['n']==before,'Event and outbox rollback together')
 for i in range(3):db("INSERT INTO security_events(id,category,outcome,correlation_id) VALUES(%s,'operator_revoke','success',%s)",(uuid.uuid4(),uuid.uuid4().hex))
 fixture.control['down']=True;expect_failure(lambda:export(export_config,storage),'Destination outage retains events');check(db('SELECT count(*) AS n FROM security_event_outbox WHERE delivered_at IS NULL')[0]['n']>=3,'Pending events durable')
 fixture.control['down']=False;fixture.control['failPut']=1;first=export(export_config,storage);check(first['exported']>=3 and fixture.control['failedPuts']>=1,'Bounded SDK upload retry succeeds')
 check(export(export_config,storage)['exported']==0,'Duplicate export has no duplicate logical records')
 db("INSERT INTO security_events(id,category,outcome,correlation_id) VALUES(%s,'mfa_verification','failed',%s)",(uuid.uuid4(),uuid.uuid4().hex));second=export(export_config,storage);chain=verify_chain(store,second['headKey'],second['headHash']);check(chain['batches']==2,'Ordered retained audit batches')
 # New exporter process resumes the committed cursor after restart.
 response=subprocess.run([sys.executable,str(root/'deploy/operations/audit.py'),'export','--database',str(export_config),'--storage',storage],capture_output=True,text=True);check(response.returncode==0 and json.loads(response.stdout)['exported']==0,'Exporter restart retains cursor')
 witness_key=private/'witness.key';witness_cert=private/'witness.crt';subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(witness_key),'-out',str(witness_cert),'-days','2','-subj','/CN=Independent CI Witness'],check=True,capture_output=True)
 anchor=private/'checkpoint.json';checkpoint(storage,second['headKey'],second['headHash'],anchor,str(witness_cert),str(witness_key));check(verify_checkpoint(storage,anchor,str(witness_cert))['events']==chain['events'],'Independent signed checkpoint verifies retained chain')
 expect_failure(lambda:verify_chain(store,first['headKey'],first['headHash'],json.loads(anchor.read_text())),'Rollback to an earlier valid batch rejected by independent checkpoint')
 bad_anchor=private/'modified-checkpoint.json';atomic_json(bad_anchor,{**json.loads(anchor.read_text()),'events':0});shutil.copyfile(anchor.with_suffix('.p7s'),bad_anchor.with_suffix('.p7s'));expect_failure(lambda:verify_checkpoint(storage,bad_anchor,str(witness_cert)),'Modified checkpoint fails pinned-certificate signature')
 # Without changing the independent anchor, malicious new object versions cannot replace history.
 original=store.get(first['headKey']);client=store.client
 client.put_object(Bucket=store.bucket,Key=first['headKey'],Body=b'{}');expect_failure(lambda:verify_checkpoint(storage,anchor,str(witness_cert)),'Modified retained batch detected')
 client.put_object(Bucket=store.bucket,Key=first['headKey'],Body=original);client.delete_object(Bucket=store.bucket,Key=first['headKey']);expect_failure(lambda:verify_checkpoint(storage,anchor,str(witness_cert)),'Missing audit batch detected')
 client.put_object(Bucket=store.bucket,Key=first['headKey'],Body=original);check(verify_checkpoint(storage,anchor,str(witness_cert))['batches']==2,'Recovery preserves trusted audit anchor')
 # Replay and reordering are rejected even when an attacker recomputes an unsigned batch hash.
 bad=json.loads(store.get(first['headKey']));bad['events']=list(reversed(bad['events']));bad['firstSequence']=bad['events'][0]['sequence'];bad['lastSequence']=bad['events'][-1]['sequence'];bad_obj=store.put('bad-order',canonical(bad));expect_failure(lambda:verify_chain(store,bad_obj['key'],bad_obj['sha256']),'Reordered batch rejected')
 bad=json.loads(store.get(first['headKey']));bad['events'][1]['payload']=bad['events'][0]['payload'];bad_obj=store.put('bad-replay',canonical(bad));expect_failure(lambda:verify_chain(store,bad_obj['key'],bad_obj['sha256']),'Repeated logical event rejected')
 # A restored/rewound exporter cursor is blocked by the independently retained minimum checkpoint.
 protected=private/'protected-export.json';atomic_json(protected,{'dsn':json.loads(export_config.read_text())['dsn'],'minimumCheckpoint':str(anchor),'witnessCertificate':str(witness_cert)})
 db('UPDATE security_export_state SET last_sequence=%s,head_key=%s,head_hash=%s WHERE singleton',(first['lastSequence'],first['headKey'],first['headHash']))
 expect_failure(lambda:export(protected,storage),'Exporter rejects database cursor rollback behind trusted checkpoint')
 db('UPDATE security_export_state SET last_sequence=%s,head_key=%s,head_hash=%s WHERE singleton',(second['lastSequence'],second['headKey'],second['headHash']))
 # Storage conditional write and enforced version retention in the isolated service.
 held=store.put('retained-test',b'private encrypted test marker');check(store.put('retained-test',b'private encrypted test marker')['sha256']==held['sha256'],'Duplicate upload readback idempotent');expect_failure(lambda:store.put('retained-test',b'different'),'Overwrite collision rejected')
 try:client.delete_object(Bucket=store.bucket,Key=held['key'],VersionId=held['versionId']);capabilities['localRetentionDeleteDenied']=False
 except Exception:capabilities['localRetentionDeleteDenied']=True
 check(capabilities['localRetentionDeleteDenied'],'Isolated backing service denies deleting compliance-retained version')
 # Real pg_dump + public-only CMS encryption + verified S3 upload and failure state.
 public=private/'backup.crt';recovery_key=private/'custodian.key';subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(recovery_key),'-out',str(public),'-days','2','-subj','/CN=CI Recovery Custodian'],check=True,capture_output=True)
 passfile=private/'backup.pgpass';passfile.write_text('127.0.0.1:5433:*:merchant_backup:'+passwords['backup']+'\n');passfile.chmod(0o600)
 backup_storage=fixture.configuration('database-backups','backup-store.json');config=private/'backup.json';state=private/'state';atomic_json(config,{'stateDirectory':str(state),'spoolDirectory':str(private/'spool'),'encryptionCertificate':str(public),'storageConfiguration':backup_storage,'databaseEnvironment':{'PGHOST':'127.0.0.1','PGPORT':'5433','PGUSER':'merchant_backup','PGDATABASE':'merchantos','PGPASSFILE':str(passfile)}})
 started=time.monotonic();backup=backup_run(config);timings.update(backupSeconds=backup['backupSeconds'],uploadSeconds=backup['uploadSeconds']);check(backup['status']=='success','Scheduled backup cycle uploads and verifies encrypted data')
 with (state/'backup.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);check(backup_run(config)['overlapPrevented'],'Actual file lock prevents concurrent backup');fcntl.flock(lock,fcntl.LOCK_UN)
 receipt=state/'latest-backup-receipt.json'
 from witness import backup_checkpoint
 backup_checkpoint(backup_storage,receipt,str(witness_cert),str(witness_key))
 download=private/'recovered';check(retrieve(backup_storage,receipt,download,str(witness_cert))['retrievedObjects']==2,'Retrieve exact encrypted backup versions')
 for obj in json.loads(receipt.read_text())['objects'].values():check(not Store(backup_storage).get(obj['key'],obj['versionId']).startswith(b'PGDMP'),'No plaintext dump sent to storage')
 altered=json.loads(receipt.read_text());next(iter(altered['objects'].values()))['sha256']='0'*64;atomic_json(private/'corrupt-receipt.json',altered);shutil.copyfile(receipt.with_suffix('.p7s'),(private/'corrupt-receipt.json').with_suffix('.p7s'));expect_failure(lambda:retrieve(backup_storage,private/'corrupt-receipt.json',private/'corrupt-output',str(witness_cert)),'Corrupt backup receipt rejected')
 encrypted=next(download.glob('*.dump.cms'));missing=subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(encrypted),'-inkey',str(private/'missing.key'),'-out','/dev/null'],capture_output=True);check(missing.returncode!=0,'Missing recovery private key fails closed')
 bad_config=read_config_for_test=json.loads(config.read_text());bad_config=copy.deepcopy(bad_config);bad_config['databaseEnvironment']['PGUSER']='missing-account';atomic_json(private/'bad-backup.json',bad_config);expect_failure(lambda:backup_run(private/'bad-backup.json'),'Failed backup is detected');check(json.loads((state/'backup-status.json').read_text())['status']=='failed','Backup failure state observable')
 old_cipher=next((private/'spool').glob('*.dump.cms'));os.utime(old_cipher,(time.time()-8*86400,time.time()-8*86400));unverified=private/'spool/unverified.dump.cms';unverified.write_bytes(b'unverified ciphertext fixture');os.utime(unverified,(time.time()-8*86400,time.time()-8*86400));check(backup_run(config)['status']=='success','Scheduled retry recovers after backup failure');check(not old_cipher.exists() and unverified.exists(),'Local retention prunes only verified uploads and preserves unuploaded backups')
 # Preserve real table contents and enforce post-restore quarantine in a fresh database.
 tables=['products','inventory_levels','orders','order_items','payments','checkout_idempotency','auth_users','auth_recovery_codes','admin_audit','inventory_adjustments']
 def snapshot(dsn):
  with psycopg.connect(dsn) as c:return {t:c.execute(sql.SQL("SELECT md5(coalesce(string_agg(row_to_json(x)::text,E'\\n' ORDER BY row_to_json(x)::text),'')) FROM {} x").format(sql.Identifier(t))).fetchone()[0] for t in tables}
 check(db('SELECT count(*) AS n FROM auth_users WHERE mfa_enabled')[0]['n']>0,'Recovery fixture contains native enrolled MFA identities')
 baseline=snapshot(owner);target='merchant_restore_m9_'+uuid.uuid4().hex[:8];restore_start=time.monotonic()
 restore_env={**os.environ,'PGHOST':'127.0.0.1','PGPORT':'5433','PGUSER':'merchantos','PGDATABASE':'merchantos'};restore_env.pop('PGPASSFILE',None)
 restored=subprocess.run([sys.executable,str(root/'deploy/restore.py'),str(encrypted),'--private-key',str(recovery_key),'--target',target,'--confirm-isolated'],env=restore_env,capture_output=True,text=True);check(restored.returncode==0,'Actual encrypted restore/migration succeeds');timings['restoreSeconds']=round(time.monotonic()-restore_start,3)
 restored_dsn=psycopg.conninfo.make_conninfo(owner,dbname=target);check(snapshot(restored_dsn)==baseline,'Restored business/identity/MFA/audit records match deterministic hashes')
 with psycopg.connect(restored_dsn) as c:check(c.execute('SELECT (SELECT count(*) FROM auth_restore_blocks)=(SELECT count(*) FROM auth_users)').fetchone()[0],'Every restored identity remains quarantined')
 # Least-privilege roles are exercised, not inferred from configuration text.
 for role,statement in [('merchant_pos','UPDATE auth_users SET mfa_enabled=false,mfa_secret=NULL WHERE mfa_enabled'),('merchant_pos','UPDATE auth_users SET enabled=false'),('merchant_pos','DELETE FROM security_events'),('merchant_pos','DELETE FROM auth_restore_blocks'),('merchant_admin_session','SELECT * FROM security_event_outbox'),('merchant_security_exporter','DELETE FROM security_event_outbox'),('merchant_monitor','SELECT password_hash FROM auth_users'),('merchant_backup','UPDATE auth_users SET enabled=true')]:
  def forbidden():
   with psycopg.connect(owner) as c:c.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)));c.execute(statement)
  expect_failure(forbidden,'Unauthorized operational DB action denied')
 # Rule windows, durable retry/restart, real TLS test receiver and resolution.
 rules=json.loads((root/'deploy/operations/alert-rules.json').read_text());alert_state=private/'alerts.json';engine=Alerts(alert_state,rules)
 scenarios={'pos_unavailable':1,'admin_unavailable':1,'database_unavailable':1,'backup_age_seconds':100000,'backup_failed':1,'audit_oldest_seconds':300,'privileged_events':1,'mfa_failures':6,'tls_certificate_days':1,'dp_certificate_days':1,'storage_used_percent':99,'storage_unavailable':1,'release_vulnerability_blocked':1,'security_exception_days':1}
 engine.evaluate(scenarios,1000);engine.evaluate(scenarios,1200);fixture.alert_down=True;check(engine.deliver(fixture.receiver_url,fixture.ca,fixture.token)>0,'Receiver outage keeps durable alerts');engine=Alerts(alert_state,rules);fixture.alert_down=False;check(engine.deliver(fixture.receiver_url,fixture.ca,fixture.token)==0,'Restart retries pending alerts')
 check(len(fixture.received)>=len(scenarios),'Controlled failure alerts arrive at isolated receiver');before=len(fixture.received);engine.deliver(fixture.receiver_url,fixture.ca,fixture.token);check(len(fixture.received)==before,'Delivery logical duplicates suppressed')
 engine.evaluate({},1300);engine.deliver(fixture.receiver_url,fixture.ca,fixture.token);check(sum(e['state']=='resolved' for e in fixture.received.values())==before,'Alerts resolve after recovery')
 # Owner-only retention deletes delivered history after the configured age, never old pending rows.
 delivered_id=uuid.uuid4();db("INSERT INTO security_events(id,category,outcome,correlation_id) VALUES(%s,'retention_fixture','success',%s)",(delivered_id,uuid.uuid4().hex));export(export_config,storage)
 db("UPDATE security_event_outbox SET delivered_at=clock_timestamp()-interval '100 days' WHERE event_id=%s",(delivered_id,));pending_id=uuid.uuid4();db("INSERT INTO security_events(id,category,outcome,correlation_id) VALUES(%s,'retention_fixture','queued',%s)",(pending_id,uuid.uuid4().hex));db("UPDATE security_event_outbox SET queued_at=clock_timestamp()-interval '100 days' WHERE event_id=%s",(pending_id,))
 maintenance=private/'maintenance.json';atomic_json(maintenance,{'dsn':owner});retention=subprocess.run([sys.executable,str(root/'deploy/operations/outbox_retention.py'),'--database',str(maintenance)],capture_output=True);check(retention.returncode==0,'Bounded owner outbox retention executes')
 check(db('SELECT count(*) AS n FROM security_event_outbox WHERE event_id=%s',(delivered_id,))[0]['n']==0,'Old delivered outbox history pruned');check(db('SELECT count(*) AS n FROM security_event_outbox WHERE event_id=%s',(pending_id,))[0]['n']==1,'Old pending event never pruned')
 readiness=assess({'operationsIntegration':True});check(readiness['isolatedStaging']=='GO' and readiness['publicProduction']=='NO-GO','Local tests never invent production custody approval')
 result={'result':'passed','assertions':checks,'sourceRevision':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'workflowRevision':os.environ.get('SOURCE_REVISION',os.environ.get('GITHUB_SHA','local')),'timings':timings,'localCapabilities':capabilities,'scope':'TLS S3 simulation and real PostgreSQL; genuine off-host durability/retention/live routing unverified','alertScenarios':sorted({e['alert'] for e in fixture.received.values()}),'alertStatesVerified':['firing','resolved'],'externalVerification':'pending','credentialAudit':'pending'}
 pathlib.Path('operations-results.json').write_text(json.dumps(result,indent=2));print('Operational integration passed: '+str(checks)+' assertions; no private artifacts retained.')
finally:fixture.close()
