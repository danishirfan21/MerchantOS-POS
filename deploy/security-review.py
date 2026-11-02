"""Collect unsuppressed audit evidence and immutable local image identities; gate separately."""
import argparse,json,os,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--project');p.add_argument('--images-only',action='store_true');p.add_argument('--output',default='security-evidence');p.add_argument('--image',action='append',default=[]);a=p.parse_args()
out=pathlib.Path(a.output);out.mkdir(exist_ok=True,parents=True)
summary={'mode':'evidence collection; security-gate.py evaluates policy','sourceRevision':os.environ.get('GITHUB_SHA','local'),'dependencyAuditsRequired':not a.images_only,'images':{}}
if not a.images_only:
 if not a.project:raise SystemExit('A project is required for dependency audits')
 r=subprocess.run(['npm','audit','--json'],text=True,capture_output=True)
 try:npm=json.loads(r.stdout)
 except ValueError:raise SystemExit('npm advisory service failed; scan unverified')
 if 'error' in npm:raise SystemExit('npm advisory service failed; scan unverified')
 (out/'npm-audit.json').write_text(json.dumps(npm,indent=2));summary['npm']=npm.get('metadata',{}).get('vulnerabilities',{})
 r=subprocess.run(['dotnet','list',a.project,'package','--vulnerable','--include-transitive','--format','json'],text=True,capture_output=True)
 if r.returncode:raise SystemExit('NuGet advisory scan failed; scan unverified')
 try:nuget=json.loads(r.stdout)
 except ValueError:raise SystemExit('Invalid NuGet evidence')
 (out/'nuget-audit.json').write_text(json.dumps(nuget,indent=2))
for i,argument in enumerate(a.image):
 if '=' in argument:role,image=argument.split('=',1)
 else:
  image=argument;role='db' if image.startswith('postgres:') else image.rsplit('-',1)[-1]
 path=out/f'image-{i}.json'
 inspected=json.loads(subprocess.check_output(['docker','image','inspect',image],text=True))[0]
 # Scan by immutable image ID, not a mutable tag that could move between inspection and scan.
 image_id=inspected['Id'];subprocess.run([os.environ['TRIVY_PATH'],'image','--scanners','vuln','--list-all-pkgs','--format','json','--output',str(path),'--timeout','10m',image_id],check=True)
 subprocess.run([os.environ['TRIVY_PATH'],'convert','--format','cyclonedx','--output',str(out/f'image-{i}.cdx.json'),str(path)],check=True)
 report=json.loads(path.read_text());v=[v for r in report.get('Results',[]) for v in r.get('Vulnerabilities',[])];summary['images'][role]={'image':image,'imageId':image_id,'rootfsLayerDigests':inspected.get('RootFS',{}).get('Layers',[]),'report':path.name,'severity':{severity:sum(vv['Severity']==severity for vv in v) for severity in ['CRITICAL','HIGH','MEDIUM','LOW','UNKNOWN']}}
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
