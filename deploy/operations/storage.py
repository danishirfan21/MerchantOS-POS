"""Provider-neutral S3 client: conditional writes, exact-version readback and retention verification."""
import base64,datetime,pathlib,time,hashlib,io,os,tempfile
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
 def put(self,name,data):return self._put(name,io.BytesIO(data),digest(data),len(data))
 def put_file(self,name,path):
  path=pathlib.Path(path);sha=hashlib.sha256()
  with path.open('rb') as source:
   for chunk in iter(lambda:source.read(1024*1024),b''):sha.update(chunk)
  with path.open('rb') as source:return self._put(name,source,sha.hexdigest(),path.stat().st_size)
 def download(self,key,version,path,expected_sha):
  path=pathlib.Path(path)
  if path.exists():raise ValueError('Recovery output must be new')
  fd,temp=tempfile.mkstemp(prefix='.download-',dir=path.parent);sha=hashlib.sha256()
  try:
   response=self.client.get_object(Bucket=self.bucket,Key=key,VersionId=version)
   with os.fdopen(fd,'wb') as output,response['Body'] as body:
    for chunk in iter(lambda:body.read(1024*1024),b''):output.write(chunk);sha.update(chunk)
    output.flush();os.fsync(output.fileno())
   if sha.hexdigest()!=expected_sha:raise ValueError('Encrypted backup integrity mismatch')
   os.replace(temp,path)
  finally:
   if os.path.exists(temp):os.unlink(temp)
 def _put(self,name,data,sha,length):
  if length>5*1024**3:raise ValueError('Single-object adapter limit is 5 GiB; reviewed multipart support required above this')
  key=self.key(name);self.policy()
  try:
   result=self.client.put_object(Bucket=self.bucket,Key=key,Body=data,IfNoneMatch='*',ChecksumAlgorithm='SHA256',ChecksumSHA256=base64.b64encode(bytes.fromhex(sha)).decode(),ObjectLockMode='COMPLIANCE',ObjectLockRetainUntilDate=now()+datetime.timedelta(days=self.days),Metadata={'sha256':sha})
   version=result.get('VersionId')
  except ClientError as error:
   if error.response['Error']['Code'] not in ['PreconditionFailed','412']:raise
   existing=self.client.head_object(Bucket=self.bucket,Key=key);version=existing.get('VersionId')
  if not version:raise ValueError('Provider did not return a version ID')
  response=self.client.get_object(Bucket=self.bucket,Key=key,VersionId=version);verified=hashlib.sha256()
  with response['Body'] as body:
   for chunk in iter(lambda:body.read(1024*1024),b''):verified.update(chunk)
  if verified.hexdigest()!=sha:raise ValueError('Stored object readback integrity mismatch or overwrite collision')
  # HEAD exposes the S3 object-lock headers for the exact returned version.
  retention=self.client.head_object(Bucket=self.bucket,Key=key,VersionId=version);until=retention.get('ObjectLockRetainUntilDate')
  if retention.get('ObjectLockMode')!='COMPLIANCE' or until is None or until<=now() or not self.days*86400-2<=(until-retention['LastModified']).total_seconds()<=90*86400+2:raise ValueError('Storage did not confirm required retention')
  return {'key':key,'versionId':version,'sha256':sha,'bytes':length,'verifiedUtc':now().isoformat(),'retentionUntilUtc':until.isoformat(),'retentionMode':'COMPLIANCE'}
