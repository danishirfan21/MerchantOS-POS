"""Private CI-only factor fixture. No authentication bypass; each code is redeemed by POS."""
import os,pathlib,fcntl,base64,hmac,hashlib,time,struct,secrets,subprocess,tempfile
if os.environ.get('GITHUB_ACTIONS')!='true':raise RuntimeError('CI-only private factor fixture')
def totp(secret,offset=0):
 key=base64.b32decode(secret+'='*((8-len(secret)%8)%8));counter=int(time.time())//30+offset
 digest=hmac.new(key,struct.pack('>Q',counter),hashlib.sha1).digest();index=digest[-1]&15
 return str((int.from_bytes(digest[index:index+4],'big')&0x7fffffff)%1000000).zfill(6)
def take(path):
 with open(path,'r+') as f:
  fcntl.flock(f,fcntl.LOCK_EX);lines=f.read().splitlines()
  if not lines:raise RuntimeError('Private factor fixture exhausted')
  code=lines.pop(0);f.seek(0);f.write('\n'.join(lines)+'\n');f.truncate();return code
if __name__=='__main__':
 import sys
 if len(sys.argv)==3 and sys.argv[1]=='--take':sys.stdout.write(take(sys.argv[2]))
 else:raise SystemExit('Private pipe interface only')
