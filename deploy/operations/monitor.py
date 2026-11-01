"""Lightweight collector and durable alert delivery. No business data or user session required."""
import argparse,datetime,json,pathlib,shutil,ssl,subprocess,time,urllib.request
import psycopg
from psycopg.rows import dict_row
from common import atomic_json,canonical,digest,iso,now,read_config,secure_url
from storage import Store

def request(url,ca,token=None,payload=None):
 secure_url(url);headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(url,headers=headers,data=canonical(payload) if payload is not None else None)
 with urllib.request.urlopen(req,context=ssl.create_default_context(cafile=ca),timeout=5) as response:return response.read()

def collect(config):
 values={};clock=now()
 for role in ['pos','admin']:
  try:request(config[role+'Readiness'],config['caBundle']);values[role+'_unavailable']=0
  except Exception:values[role+'_unavailable']=1
  try:
   token=pathlib.Path(config['monitorTokenFile']).read_text().strip();metrics=json.loads(request(config[role+'Metrics'],config['caBundle'],token));values[role+'_metrics_unavailable']=0;values[role+'_http_5xx_total']=sum(v for k,v in metrics['requestsByStatus'].items() if k.startswith('5'));values[role+'_checkout_failures_total']=metrics.get('checkoutFailures',0);values[role+'_reporting_max_ms']=metrics.get('reportingMaxMs',0)
  except Exception:values[role+'_metrics_unavailable']=1
 try:
  with psycopg.connect(read_config(config['databaseConfiguration'])['dsn'],connect_timeout=3,row_factory=dict_row) as db:values.update({k:float(v) for k,v in db.execute('SELECT * FROM ops_security_signals').fetchone().items()});values['database_unavailable']=0
 except Exception:values['database_unavailable']=1;values['audit_signal_unavailable']=1
 status=pathlib.Path(config['backupStateDirectory'])/'backup-status.json'
 if status.exists():
  backup=json.loads(status.read_text());last=backup.get('lastSuccessfulUtc');values['backup_age_seconds']=(clock-datetime.datetime.fromisoformat(last)).total_seconds() if last else 1e12;values['backup_failed']=int(backup['status']=='failed' or (backup['status']=='running' and (clock-datetime.datetime.fromisoformat(backup['startedUtc'])).total_seconds()>900))
 else:values.update(backup_age_seconds=1e12,backup_failed=1)
 try:Store(config['storageConfiguration']).policy();values['storage_unavailable']=0
 except Exception:values['storage_unavailable']=1
 usage=shutil.disk_usage(config['capacityPath']);values['storage_used_percent']=100*(usage.total-usage.free)/usage.total
 for name,path in config['certificates'].items():
  try:
   result=subprocess.check_output(['openssl','x509','-in',path,'-enddate','-noout'],text=True,stderr=subprocess.DEVNULL);expiry=datetime.datetime.strptime(result.strip().split('=',1)[1],'%b %d %H:%M:%S %Y %Z').replace(tzinfo=datetime.timezone.utc);values[name+'_certificate_days']=(expiry-clock).total_seconds()/86400
  except Exception:values[name+'_certificate_days']=-1
 verification=pathlib.Path(config.get('restoreVerificationFile','/missing'))
 restore=json.loads(verification.read_text()) if verification.exists() else {};values['restore_verification_failed']=int(restore.get('result')!='passed');values['restore_verification_age_seconds']=(clock-datetime.datetime.fromisoformat(restore['verifiedUtc'])).total_seconds() if restore.get('result')=='passed' else 1e12
 audit_path=pathlib.Path(config.get('auditVerificationFile','/missing'));audit=json.loads(audit_path.read_text()) if audit_path.exists() else {};values['audit_integrity_failed']=int(audit.get('result')=='failed');values['audit_verification_age_seconds']=(clock-datetime.datetime.fromisoformat(audit['verifiedUtc'])).total_seconds() if audit.get('result')=='passed' else 1e12
 policy=json.loads(pathlib.Path(config['securityPolicy']).read_text());dates=[datetime.date.fromisoformat(e['expiresUtc']) for e in policy.get('exceptions',[])];values['security_exception_days']=min((d-clock.date()).days for d in dates) if dates else 99999
 release=pathlib.Path(config['releaseGate']);values['release_vulnerability_blocked']=int(not release.exists() or not json.loads(release.read_text()).get('stagingPolicyPassed',False))
 previous=pathlib.Path(config['metricsState'])
 if previous.exists():
  old=json.loads(previous.read_text());elapsed=max(1,(clock-datetime.datetime.fromisoformat(old['observedUtc'])).total_seconds())
  for role in ['pos','admin']:
   for metric in ['http_5xx','checkout_failures']:
    key=role+'_'+metric+'_total'
    if key in values:values[role+'_'+metric+'_per_minute']=max(0,values[key]-old['signals'].get(key,values[key]))*60/elapsed
 return values

class Alerts:
 def __init__(self,state_path,rules):
  self.path=pathlib.Path(state_path);self.rules=rules;self.state=json.loads(self.path.read_text()) if self.path.exists() else {'active':{},'pending':{}}
 def evaluate(self,values,timestamp):
  for rule in self.rules:
   name=rule['name'];value=values.get(rule['metric']);current=self.state['active'].get(name)
   violation=value is not None and (value>rule['threshold'] if rule['comparison']=='gt' else value<rule['threshold'])
   if violation:
    if current is None:current={'since':timestamp,'fired':False};self.state['active'][name]=current
    if timestamp-current['since']>=rule['forSeconds'] and not current['fired']:
     current['fired']=True;self.enqueue(rule,current,'firing',value)
   elif current is not None:
    if current['fired']:self.enqueue(rule,current,'resolved',value)
    del self.state['active'][name]
  atomic_json(self.path,self.state)
 def enqueue(self,rule,current,status,value):
  event={'schema':1,'alert':rule['name'],'severity':rule['severity'],'state':status,'startedAtEpoch':current['since'],'runbook':rule['runbook'],'value':value};self.state['nextDeliverySequence']=self.state.get('nextDeliverySequence',0)+1;event['deliverySequence']=self.state['nextDeliverySequence'];event['deliveryId']=digest(canonical(event));self.state['pending'][event['deliveryId']]=event
 def deliver(self,receiver,ca,token):
  for key,event in sorted(self.state['pending'].items(),key=lambda pair:pair[1]['deliverySequence']):
   try:request(receiver,ca,token,event)
   except Exception:continue
   del self.state['pending'][key];atomic_json(self.path,self.state)
  return len(self.state['pending'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
 try:
  c=read_config(a.config);values=collect(c);engine=Alerts(c['alertState'],json.loads(pathlib.Path(c['rules']).read_text()));engine.evaluate(values,time.time());pending=engine.deliver(c['alertReceiver'],c['alertCaBundle'],pathlib.Path(c['alertTokenFile']).read_text().strip());atomic_json(c['metricsState'],{'observedUtc':iso(),'signals':values,'alertDeliveryPending':pending});pathlib.Path(c['prometheusTextfile']).write_text(''.join('merchantos_'+key+' '+str(value)+'\n' for key,value in sorted(values.items())));print(json.dumps({'status':'collected','alertDeliveryPending':pending}))
 except Exception as error:raise SystemExit('Monitoring failed: '+type(error).__name__+'; private details omitted')
