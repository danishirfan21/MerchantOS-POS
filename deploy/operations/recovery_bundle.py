"""Controlled protected-key/wrapping-dependency recovery. No plaintext archive is written."""
import argparse,hashlib,json,pathlib,re,subprocess,tarfile
from common import read_config
from witness import verify

def create(config_path,output):
 c=read_config(config_path);output=pathlib.Path(output)
 if output.exists():raise ValueError('Encrypted recovery bundle must be new')
 inspected=subprocess.run(['openssl','pkcs12','-in',c['wrappingPfx'],'-passin','file:'+c['wrappingPasswordFile'],'-info','-noout'],capture_output=True,check=True)
 if not re.search(rb'key\s*bag',inspected.stderr,re.I):raise ValueError('Wrapping PFX must contain a private key')
 public=subprocess.check_output(['openssl','pkcs12','-in',c['wrappingPfx'],'-passin','file:'+c['wrappingPasswordFile'],'-clcerts','-nokeys'],stderr=subprocess.DEVNULL)
 actual=subprocess.check_output(['openssl','x509','-fingerprint','-sha256','-noout'],input=public,stderr=subprocess.DEVNULL)
 expected=subprocess.check_output(['openssl','x509','-in',c['wrappingPublicCertificate'],'-fingerprint','-sha256','-noout'],stderr=subprocess.DEVNULL)
 if actual!=expected:raise ValueError('Public wrapping certificate does not match PFX')
 output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with output.open('xb') as encrypted:
  output.chmod(0o600);process=subprocess.Popen(['openssl','cms','-encrypt','-binary','-aes-256-cbc','-outform','DER',c['encryptionCertificate']],stdin=subprocess.PIPE,stdout=encrypted,stderr=subprocess.DEVNULL)
  try:
   with tarfile.open(fileobj=process.stdin,mode='w|') as archive:
    for role,key in [('pos-keys','posKeys'),('admin-keys','adminKeys')]:
     files=sorted(pathlib.Path(c[key]).glob('key-*.xml'))
     if not files:raise ValueError('Protected key ring required for each application')
     for file in files:
      raw=file.read_bytes()
      if not file.is_file() or file.is_symlink() or b'<encryptedSecret' not in raw or b'<masterKey' in raw:raise ValueError('Unprotected/symlinked key material rejected')
      archive.add(file,arcname=role+'/'+file.name)
    for key,name in [('wrappingPfx','dp.pfx'),('wrappingPasswordFile','dp_password'),('wrappingPublicCertificate','dp.crt')]:
     file=pathlib.Path(c[key])
     if not file.is_file() or file.is_symlink():raise ValueError('Controlled wrapping dependency file required')
     archive.add(file,arcname='recovered-material/'+name)
   process.stdin.close()
   if process.wait(timeout=30)!=0:raise ValueError('Recovery envelope encryption failed')
  except Exception:
   process.kill();process.wait();output.unlink(missing_ok=True);raise
 return {'format':'CMS-AES256 streaming protected-dependency archive','privateRecoveryKeyIncluded':False}

def extract(bundle,private_key,output,receipt,witness_certificate):
 verify(receipt,witness_certificate);bundle=pathlib.Path(bundle);obj=json.loads(pathlib.Path(receipt).read_text())['objects'].get(bundle.name)
 if obj is None or hashlib.sha256(bundle.read_bytes()).hexdigest()!=obj['sha256']:raise ValueError('Recovery bundle does not match signed receipt')
 output=pathlib.Path(output)
 if output.exists():raise ValueError('Recovery directory must be new')
 output.mkdir(mode=0o700,parents=True);process=subprocess.Popen(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(bundle),'-inkey',str(private_key)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);count=0;total=0
 try:
  with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
   for member in archive:
    total+=member.size
    allowed=re.fullmatch(r'(pos-keys|admin-keys)/key-[0-9a-f-]+\.xml',member.name) is not None or member.name in ['recovered-material/dp.pfx','recovered-material/dp_password','recovered-material/dp.crt']
    if not member.isfile() or not allowed or member.size>1024*1024 or total>64*1024*1024:raise ValueError('Unexpected recovery archive entry')
    archive.extract(member,output,filter='data');(output/member.name).chmod(0o600);count+=1
  if process.wait(timeout=30)!=0:raise ValueError('Recovery envelope decryption failed')
 except Exception:
  process.kill();process.wait();raise
 for role in ['pos-keys','admin-keys']:
  (output/role).chmod(0o700)
  if not list((output/role).glob('*.xml')):raise ValueError('Incomplete protected ring recovery')
 for name in ['dp.pfx','dp_password','dp.crt']:
  if not (output/'recovered-material'/name).is_file():raise ValueError('Incomplete wrapping dependency recovery')
 return {'verifiedEntries':count,'privateRecoveryKeyCopied':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['create','extract']);p.add_argument('--config');p.add_argument('--bundle');p.add_argument('--output',required=True);p.add_argument('--private-key');p.add_argument('--receipt');p.add_argument('--witness-certificate');a=p.parse_args()
 try:result=create(a.config,a.output) if a.action=='create' else extract(a.bundle,a.private_key,a.output,a.receipt,a.witness_certificate);print(json.dumps(result))
 except Exception as error:raise SystemExit('Protected dependency operation failed: '+type(error).__name__+'; no private material logged')
