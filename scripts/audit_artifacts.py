"""Fail closed before upload if artifacts contain ephemeral passwords or protected cookie/CSRF values."""
import base64,io,os,re,sys,zipfile
from pathlib import Path
secrets=[v.encode() for k,v in os.environ.items() if k.startswith(('TEST_','STAGING_')) and k.endswith('_PASSWORD') and len(v)>=14]
findings=[];count=0
def inspect(data,label):
 global count
 count+=1
 if any(s in data for s in secrets) or re.search(rb'CfDJ[A-Za-z0-9_-]{60,}',data):findings.append(label)
 if data.startswith(b'PK\x03\x04'):
  with zipfile.ZipFile(io.BytesIO(data)) as archive:
   for name in archive.namelist():
    if not name.endswith('/'):inspect(archive.read(name),label+' (embedded archive)')
 for match in re.finditer(rb'data:application/zip;base64,([A-Za-z0-9+/=]+)',data):inspect(base64.b64decode(match.group(1)),label+' (embedded report)')
for arg in sys.argv[1:]:
 root=Path(arg)
 for p in ([root] if root.is_file() else root.rglob('*') if root.exists() else []):
  if p.is_file():inspect(p.read_bytes(),str(p))
if findings:raise SystemExit('Artifact upload blocked: sensitive material detected in '+', '.join(sorted(set(findings))))
print(f'Artifact credential audit passed: {count} files/embedded entries; no ephemeral passwords or protected session/CSRF values detected.')
