"""Fail closed before upload; inspect decoded archives, not random encoded ZIP bytes."""
import base64,io,os,re,sys,zipfile
from pathlib import Path
secrets=[v.encode() for k,v in os.environ.items() if k.startswith(('TEST_','STAGING_')) and k.endswith('_PASSWORD') and len(v)>=14]
findings=[];count=0
embedded=re.compile(rb'data:application/zip;base64,([A-Za-z0-9+/=]+)')
def inspect(data,label):
 global count
 count+=1
 if data.startswith(b'PK\x03\x04'):
  with zipfile.ZipFile(io.BytesIO(data)) as archive:
   for name in archive.namelist():
    if not name.endswith('/'):inspect(archive.read(name),label+' (embedded '+Path(name).suffix+' entry)')
  return
 # Encoded compressed bytes can randomly resemble a cookie. Scan every decoded entry,
 # then remove only that already-inspected encoding from the surrounding HTML scan.
 for match in embedded.finditer(data):inspect(base64.b64decode(match.group(1),validate=True),label+' (embedded report)')
 data=embedded.sub(b'[decoded and inspected ZIP]',data)
 reasons=[]
 if any(s in data for s in secrets):reasons.append('ephemeral password')
 if re.search(rb'CfDJ[A-Za-z0-9_-]{60,}',data):reasons.append('protected cookie/CSRF value')
 if re.search(rb'-----BEGIN (?:ENCRYPTED |RSA |EC )?PRIVATE KEY-----',data):reasons.append('private key')
 if b'<encryptedSecret' in data:reasons.append('protected key XML')
 if data.startswith(b'PGDMP'):reasons.append('database dump')
 if reasons:findings.append(label+' ['+', '.join(reasons)+']')
for arg in sys.argv[1:]:
 root=Path(arg)
 for p in ([root] if root.is_file() else root.rglob('*') if root.exists() else []):
  if p.is_file():inspect(p.read_bytes(),str(p))
if findings:raise SystemExit('Artifact upload blocked: sensitive material detected in '+', '.join(sorted(set(findings))))
print(f'Artifact credential audit passed: {count} files/embedded entries; no ephemeral passwords or protected session/CSRF values detected.')
