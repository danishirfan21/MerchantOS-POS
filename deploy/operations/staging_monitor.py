"""Prepare a private collector against the actual disposable HTTPS topology, never live alert routing."""
import json,pathlib,subprocess,time,tempfile
import psycopg
from common import atomic_json
from fixture import Fixture
from monitor import collect,Alerts
class StagingMonitor:
 def __init__(self,root,work,run,evidence):
  self.directory=pathlib.Path(tempfile.mkdtemp(prefix='merchantos-monitor-drill-'));self.fixture=Fixture(self.directory/'endpoint');storage=self.fixture.configuration();self.fixture.initialize(storage);secrets=work/'secrets'
  container=run('ps','-q','db').stdout.strip();address=subprocess.check_output(['docker','inspect',container,'--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'],text=True).strip()
  database=self.directory/'database.json';atomic_json(database,{'dsn':psycopg.conninfo.make_conninfo(host=address,port=5432,dbname='merchantos',user='merchant_monitor',password=(secrets/'monitor_db_password').read_text())})
  self.config={'posReadiness':'https://localhost:8443/api/health/ready','adminReadiness':'https://localhost:9443/health/ready','posMetrics':'https://localhost:8443/api/ops/monitor','adminMetrics':'https://localhost:9443/ops/monitor','caBundle':str(secrets/'ca.crt'),'monitorTokenFile':str(secrets/'monitor_token'),'databaseConfiguration':str(database),'backupStateDirectory':str(self.directory/'backup-state'),'storageConfiguration':storage,'capacityPath':str(work),'certificates':{'tls':str(secrets/'tls.crt'),'dp':str(secrets/'dp.crt')},'metricsState':str(self.directory/'metrics.json'),'securityPolicy':str(root/'deploy/security-policy.json'),'releaseGate':str(evidence/'security/release-gate.json'),'restoreVerificationFile':str(self.directory/'restore.json')}
  self.alerts=Alerts(self.directory/'alerts.json',json.loads((root/'deploy/operations/alert-rules.json').read_text()));self.clock=time.time()
 def poll(self,offset):
  values=collect(self.config);self.alerts.evaluate(values,self.clock+offset);self.alerts.deliver(self.fixture.receiver_url,self.fixture.ca,self.fixture.token);return values
 def close(self):self.fixture.close()
