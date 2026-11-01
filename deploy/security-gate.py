"""Fail staging release policy on unreviewed high/critical findings. Never suppress scanner output."""
import argparse,datetime,hashlib,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--evidence',default='security-evidence');p.add_argument('--policy',default=str(pathlib.Path(__file__).with_name('security-policy.json')));a=p.parse_args()
root=pathlib.Path(a.evidence);policy=json.loads(pathlib.Path(a.policy).read_text());summary=json.loads((root/'summary.json').read_text());failures=[];exceptions=[];today=datetime.datetime.now(datetime.timezone.utc).date()
roles=set(summary.get('images',{}))
if roles not in [{'admin'},{'api','web','db','ops'},{'api','admin','web','db','ops'}]:failures.append('Missing or unexpected release image roles')
if summary.get('dependencyAuditsRequired'):
 for name in ['npm-audit.json','nuget-audit.json']:
  if not (root/name).is_file():failures.append('Missing dependency audit: '+name)
config=pathlib.Path(__file__).with_name('Caddyfile');config_valid=hashlib.sha256(config.read_bytes()).hexdigest()==policy['caddyConfigSha256']
for role,image in summary.get('images',{}).items():
 if not image['imageId'].startswith('sha256:') or not image.get('rootfsLayerDigests'):failures.append('Missing immutable image identity: '+role)
 report=json.loads((root/image['report']).read_text())
 if report.get('SchemaVersion')!=2 or not isinstance(report.get('Results'),list):failures.append('Incomplete scanner report: '+role)
 for result in report.get('Results',[]):
  for v in result.get('Vulnerabilities',[]):
   if v['Severity'] not in ['HIGH','CRITICAL']:continue
   matched=next((e for e in policy['exceptions'] if e['role']==role and e['vulnerabilityId']==v['VulnerabilityID'] and e['package']==v['PkgName'] and e['installedVersion']==v['InstalledVersion'] and datetime.date.fromisoformat(e['expiresUtc'])>=today and e.get('owner') and e.get('rationale') and (not e.get('requiresNoFixedVersion') or not v.get('FixedVersion')) and config_valid),None)
   if matched:exceptions.append({'role':role,'id':v['VulnerabilityID'],'package':v['PkgName'],'expiresUtc':matched['expiresUtc'],'rationale':matched['rationale']})
   else:failures.append(role+': '+v['VulnerabilityID']+' '+v['PkgName']+' '+v['InstalledVersion']+' fixed='+v.get('FixedVersion','unavailable'))
if (root/'npm-audit.json').exists():
 npm=json.loads((root/'npm-audit.json').read_text());counts=npm.get('metadata',{}).get('vulnerabilities',{})
 if not counts or 'error' in npm:failures.append('Incomplete npm advisory evidence')
 if counts.get('high',0) or counts.get('critical',0):failures.append('npm high/critical advisories')
if (root/'nuget-audit.json').exists():
 nuget=json.loads((root/'nuget-audit.json').read_text())
 if not isinstance(nuget.get('projects'),list) or not nuget['projects']:failures.append('Incomplete NuGet advisory evidence')
 def walk(value):
  if isinstance(value,dict):
   for vulnerability in value.get('vulnerabilities',[]):
    if str(vulnerability.get('severity','')).lower() in ['2','3','high','critical']:failures.append('NuGet high/critical advisory')
   for child in value.values():walk(child)
  elif isinstance(value,list):
   for child in value:walk(child)
 walk(nuget)
result={'stagingPolicyPassed':not failures,'scope':policy['scope'],'publicProductionApproved':False,'reviewedExceptionsUsed':exceptions,'failures':failures}
(root/'release-gate.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if failures:raise SystemExit('Staging vulnerability release gate failed; reports retained without suppression')
