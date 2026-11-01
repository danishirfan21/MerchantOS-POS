"""Policy regression: an evidence collection success must not become a false approval."""
import unittest,tempfile,pathlib,json,subprocess,datetime,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
class PolicyTests(unittest.TestCase):
 def evaluate(self,change=None):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);policy=json.loads((ROOT/'security-policy.json').read_text());summary={'images':{role:{'imageId':'sha256:'+'a'*64,'rootfsLayerDigests':['sha256:'+'b'*64],'report':role+'.json'} for role in ['api','web','db','ops']}}
   reports={role:{'SchemaVersion':2,'Results':[{'Vulnerabilities':[]}]} for role in summary['images']}
   if change:change(policy,summary,reports)
   (root/'policy.json').write_text(json.dumps(policy));(root/'summary.json').write_text(json.dumps(summary))
   for role,report in reports.items():(root/(role+'.json')).write_text(json.dumps(report))
   result=subprocess.run(['python3',str(ROOT/'security-gate.py'),'--evidence',str(root),'--policy',str(root/'policy.json')],capture_output=True)
   return result.returncode==0
 def advisory(self,policy,summary,reports):
  e=policy['exceptions'][0];e['expiresUtc']=(datetime.date.today()+datetime.timedelta(days=1)).isoformat();reports['web']['Results'][0]['Vulnerabilities']=[{'Severity':'HIGH','VulnerabilityID':e['vulnerabilityId'],'PkgName':e['package'],'InstalledVersion':e['installedVersion']}]
 def test_clean_evidence(self):self.assertTrue(self.evaluate())
 def test_unknown_high_rejected(self):
  def change(p,s,r):self.advisory(p,s,r);r['web']['Results'][0]['Vulnerabilities'][0]['VulnerabilityID']='CVE-UNREVIEWED'
  self.assertFalse(self.evaluate(change))
 def test_exact_unfixed_exception(self):self.assertTrue(self.evaluate(self.advisory))
 def test_available_fix_rejected(self):
  def change(p,s,r):self.advisory(p,s,r);r['web']['Results'][0]['Vulnerabilities'][0]['FixedVersion']='new-patched-version'
  self.assertFalse(self.evaluate(change))
 def test_expired_exception_rejected(self):
  def change(p,s,r):self.advisory(p,s,r);p['exceptions'][0]['expiresUtc']='2000-01-01'
  self.assertFalse(self.evaluate(change))
 def test_changed_surface_rejected(self):
  def change(p,s,r):self.advisory(p,s,r);p['caddyConfigSha256']='changed'
  self.assertFalse(self.evaluate(change))
 def test_missing_image_rejected(self):self.assertFalse(self.evaluate(lambda p,s,r:s['images'].pop('db')))
 def test_required_dependency_evidence_rejected(self):self.assertFalse(self.evaluate(lambda p,s,r:s.update(dependencyAuditsRequired=True)))
 def test_empty_report_rejected(self):self.assertFalse(self.evaluate(lambda p,s,r:r['db'].clear()))
if __name__=='__main__':unittest.main()
