"""CI-only TLS S3 and alert-receiver fixtures. Neither represents genuine off-host durability."""
import os,uuid,http.server,json,pathlib,secrets,ssl,subprocess,threading
from werkzeug.serving import make_server,WSGIRequestHandler
from moto.server import DomainDispatcherApplication,create_backend_app
from common import atomic_json
class Quiet(WSGIRequestHandler):
 def log(self,*args,**kwargs):pass
class Fixture:
 def __init__(self,directory,certificate=None,key=None,ca=None):
  self.root=pathlib.Path(directory);self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.control={'down':False,'failPut':0,'failedPuts':0};self.received={};self.alert_down=False;self.token=secrets.token_urlsafe(36)
  if os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_ENV'):
   print('::add-mask::'+self.token,flush=True)
   with open(os.environ['GITHUB_ENV'],'a') as output:output.write('TEST_M9_'+uuid.uuid4().hex+'_TOKEN='+self.token+'\n')
  if certificate is None:
   certificate=str(self.root/'fixture.crt');key=str(self.root/'fixture.key')
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',certificate,'-days','2','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);ca=certificate
  self.ca=ca or certificate;app=DomainDispatcherApplication(create_backend_app)
  def gateway(environ,start):
   if self.control['down'] or (environ['REQUEST_METHOD']=='PUT' and self.control['failPut']>0):
    self.control['failPut']=max(0,self.control['failPut']-1);self.control['failedPuts']+=1;start('503 Service Unavailable',[('Content-Type','application/xml')]);return [b'<Error><Code>ServiceUnavailable</Code></Error>']
   return app(environ,start)
  self.s3=make_server('127.0.0.1',0,gateway,threaded=True,ssl_context=(certificate,key),request_handler=Quiet);threading.Thread(target=self.s3.serve_forever,daemon=True).start();self.endpoint='https://localhost:'+str(self.s3.server_port)
  outer=self
  class Receiver(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    if outer.alert_down:self.send_response(503);self.end_headers();return
    if self.headers.get('Authorization')!='Bearer '+outer.token:self.send_response(401);self.end_headers();return
    data=self.rfile.read(min(int(self.headers.get('Content-Length','0')),8192));event=json.loads(data)
    if set(event)!={'schema','alert','severity','state','startedAtEpoch','runbook','value','deliveryId','deliverySequence'}:self.send_response(400);self.end_headers();return
    outer.received[event['deliveryId']]=event;self.send_response(204);self.end_headers()
  self.receiver=http.server.ThreadingHTTPServer(('127.0.0.1',0),Receiver);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certificate,key);self.receiver.socket=context.wrap_socket(self.receiver.socket,server_side=True);threading.Thread(target=self.receiver.serve_forever,daemon=True).start();self.receiver_url='https://localhost:'+str(self.receiver.server_port)+'/alerts'
 def configuration(self,prefix='',name='store.json'):
  path=self.root/name;atomic_json(path,{'endpoint':self.endpoint,'bucket':'merchantos-operations','prefix':prefix,'region':'us-east-1','accessKeyId':'isolated-fixture','secretAccessKey':'isolated-fixture-only','caBundle':self.ca,'retentionDays':30});return str(path)
 def initialize(self,config):
  from storage import Store
  client=Store(config).client;client.create_bucket(Bucket='merchantos-operations',ObjectLockEnabledForBucket=True);client.put_bucket_versioning(Bucket='merchantos-operations',VersioningConfiguration={'Status':'Enabled'});client.put_object_lock_configuration(Bucket='merchantos-operations',ObjectLockConfiguration={'ObjectLockEnabled':'Enabled','Rule':{'DefaultRetention':{'Mode':'COMPLIANCE','Days':30}}})
 def close(self):self.s3.shutdown();self.receiver.shutdown()
