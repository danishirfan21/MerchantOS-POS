"""Authenticated loopback test client. Credentials are environment-only; never print session material."""
import http.cookiejar,json,os,urllib.request,urllib.error
BASE='http://127.0.0.1:5080'
class Client:
 def __init__(self,role):
  self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar));self.token=''
  self.csrf();status,_=self.request('/api/auth/login',{'username':os.environ['TEST_'+role+'_USERNAME'],'password':os.environ['TEST_'+role+'_PASSWORD']});assert status==200,'Test sign-in failed';self.csrf()
 def csrf(self):
  with self.opener.open(BASE+'/api/auth/csrf',timeout=15) as r:self.token=json.load(r)['token']
 def request(self,path,payload=None,csrf=True):
  headers={'Content-Type':'application/json'} if payload is not None else {}
  if payload is not None and csrf:headers['X-CSRF-TOKEN']=self.token
  req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
  try:
   with self.opener.open(req,timeout=20) as r:
    raw=r.read();return r.status,json.loads(raw) if raw else None
  except urllib.error.HTTPError as e:
   raw=e.read()
   try:data=json.loads(raw)
   except ValueError:data=None
   return e.code,data
