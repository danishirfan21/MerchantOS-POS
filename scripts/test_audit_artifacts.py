import base64,io,os,pathlib,subprocess,sys,tempfile,unittest,zipfile
script=pathlib.Path(__file__).with_name('audit_artifacts.py')
class AuditTests(unittest.TestCase):
 def check_content(self,data,blocked):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'artifact';p.write_bytes(data)
   r=subprocess.run([sys.executable,str(script),str(p)],env={**os.environ,'STAGING_TEST_PASSWORD':'synthetic-audit-password','STAGING_TEST_MFA_CODE':'918273','STAGING_TEST_MFA_SECRET':'SYNTHETICPRIVATEFACTORKEY'},capture_output=True)
   self.assertEqual(r.returncode!=0,blocked,r.stdout.decode()+r.stderr.decode())
 def test_secrets_remain_blocked(self):
  for payload in [b'synthetic-audit-password',b'CfDJ'+b'A'*65,b'-----BEGIN PRIVATE KEY-----\n'+b'A'*64,b'<encrypted'+b'Secret decryptorType="Native">secret</encryptedSecret>',b'PGDMPbinary']:
   with self.subTest(kind=payload[:5]):self.check_content(payload,True)
 def test_mfa_material_is_blocked(self):
  for payload in [b'MRC_'+b'A'*64,b'MCH_'+b'A'*64,b'otpauth'+b'://totp/test?secret='+b'A'*32,b'918273',b'SYNTHETICPRIVATEFACTORKEY']:
   with self.subTest(kind=payload[:5]):self.check_content(payload,True)
 def test_embedded_report_is_decoded_before_audit(self):
  for payload,blocked in [(b'synthetic-audit-password',True),(b'CfDJ'+b'A'*65,True),(b'safe report',False)]:
   z=io.BytesIO()
   with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr('report.json',payload)
   self.check_content(b'<html>data:application/zip;base64,'+base64.b64encode(z.getvalue())+b'</html>',blocked)
 def test_source_markers_are_not_key_material(self):self.check_content(b"assert '<encryptedSecret' in xml; marker='-----BEGIN PRIVATE KEY-----'",False)
 def test_known_otp_inside_unrelated_hex_digest_is_not_a_code(self):self.check_content(b'checksum='+b'a'*30+b'918273'+b'f'*28,False)
 def test_dump_marker_in_source_is_not_a_dump(self):self.check_content(b'const magic="PGDMP"; safe source excerpt',False)
if __name__=='__main__':unittest.main()
