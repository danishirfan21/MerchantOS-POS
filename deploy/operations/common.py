"""Small operational primitives; credentials never enter logs or command arguments."""
import datetime,hashlib,json,os,pathlib,tempfile,urllib.parse
UTC=datetime.timezone.utc
def now():return datetime.datetime.now(UTC)
def iso(value=None):return (value or now()).isoformat()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(data):return hashlib.sha256(data).hexdigest()
def read_config(path):
 p=pathlib.Path(path)
 if p.stat().st_mode&0o077:raise ValueError('Operational configuration must be private (0600)')
 return json.loads(p.read_text())
def atomic_json(path,value):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd,name=tempfile.mkstemp(prefix='.state-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(canonical(value));f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
def secure_url(url,test_http=False):
 parsed=urllib.parse.urlsplit(url)
 if parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Credentials/query strings are forbidden in endpoint URLs')
 if parsed.scheme!='https' and not(test_http and os.environ.get('GITHUB_ACTIONS')=='true' and parsed.scheme=='http' and parsed.hostname in ['127.0.0.1','localhost']):raise ValueError('TLS endpoint required')
 return url
