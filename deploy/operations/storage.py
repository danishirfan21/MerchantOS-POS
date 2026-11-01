"""Provider-neutral S3 client: conditional writes, exact-version readback and retention verification."""
import base64,datetime,pathlib,time
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from common import canonical,digest,now,read_config,secure_url
class Store:
 def __init__(self,path):
  self.config=read_config(path);c=self.config;secure_url(c['endpoint'])
  self.bucket=c['bucket'];self.prefix=c.get('prefix','').strip('/')
  self.days=int(c.get('retentionDays',30))
  if not 30<=self.days<=90:raise ValueError('Remote retention must be 30–90 days')
  if not c.get('caBundle'):raise ValueError('Explicit CA bundle required')
  self.client=boto3.client('s3',endpoint_url=c['endpoint'],region_name=c.get('region','us-east-1'),aws_access_key_id=c['accessKeyId'],aws_secret_access_key=c['secretAccessKey'],aws_session_token=c.get('sessionToken'),verify=c['caBundle'],config=Config(signature_version='s3v4',connect_timeout=3,read_timeout=10,retries={'mode':'standard','total_max_attempts':3},s3={'addressing_style':'path'}))
 def key(self,name):
  if name.startswith('/') or '..' in name.split('/'):raise ValueError('Invalid object key')
  return '/'.join(x for x in [self.prefix,name] if x)
 def policy(self):
  version=self.client.get_bucket_versioning(Bucket=self.bucket)
  lock=self.client.get_object_lock_configuration(Bucket=self.bucket)['ObjectLockConfiguration']
  if version.get('Status')!='Enabled' or lock.get('ObjectLockEnabled')!='Enabled':raise ValueError('Versioning and object lock must be enabled independently by storage operator')
  return {'versioning':'Enabled','objectLock':'Enabled','requestedMode':'COMPLIANCE','requestedDays':self.days}
 def get(self,key,version=None):
  args={'Bucket':self.bucket,'Key':key}
  if version:args['VersionId']=version
  response=self.client.get_object(**args)
  with response['Body'] as body:return body.read()
 def put(self,name,data):
  key=self.key(name);sha=digest(data);self.policy()
  try:
   result=self.client.put_object(Bucket=self.bucket,Key=key,Body=data,IfNoneMatch='*',ChecksumSHA256=base64.b64encode(bytes.fromhex(sha)).decode(),ObjectLockMode='COMPLIANCE',ObjectLockRetainUntilDate=now()+datetime.timedelta(days=self.days),Metadata={'sha256':sha})
   version=result.get('VersionId')
  except ClientError as error:
   if error.response['Error']['Code'] not in ['PreconditionFailed','412']:raise
   existing=self.client.head_object(Bucket=self.bucket,Key=key);version=existing.get('VersionId')
  if not version:raise ValueError('Provider did not return a version ID')
  stored=self.get(key,version)
  if digest(stored)!=sha:raise ValueError('Stored object readback integrity mismatch or overwrite collision')
  retention=self.client.get_object_retention(Bucket=self.bucket,Key=key,VersionId=version)['Retention']
  until=retention['RetainUntilDate']
  if retention.get('Mode')!='COMPLIANCE' or until<now()+datetime.timedelta(days=self.days-1) or until>now()+datetime.timedelta(days=91):raise ValueError('Storage did not confirm required retention')
  return {'key':key,'versionId':version,'sha256':sha,'bytes':len(data),'verifiedUtc':now().isoformat(),'retentionUntilUtc':until.isoformat(),'retentionMode':'COMPLIANCE'}
