"""Evidence collection: findings remain visible; successful scan is not a clean bill of health."""
import argparse,json,os,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',default='security-evidence');p.add_argument('--image',action='append',default=[]);a=p.parse_args()
out=pathlib.Path(a.output);out.mkdir(exist_ok=True,parents=True)
r=subprocess.run(['npm','audit','--json'],text=True,capture_output=True)
try:npm=json.loads(r.stdout)
except ValueError:raise SystemExit('npm advisory service failed; scan unverified')
if 'error' in npm:raise SystemExit('npm advisory service failed; scan unverified')
(out/'npm-audit.json').write_text(json.dumps(npm,indent=2))
r=subprocess.run(['dotnet','list',a.project,'package','--vulnerable','--include-transitive','--format','json'],text=True,capture_output=True)
if r.returncode:raise SystemExit('NuGet advisory scan failed; scan unverified')
try:nuget=json.loads(r.stdout)
except ValueError:raise SystemExit('NuGet advisory scan returned invalid evidence')
(out/'nuget-audit.json').write_text(json.dumps(nuget,indent=2))
summary={'mode':'findings reported, not suppressed; review before deployment','npm':npm.get('metadata',{}).get('vulnerabilities',{}),'images':{}}
for i,image in enumerate(a.image):
 path=out/f'image-{i}.json'
 subprocess.run([os.environ['TRIVY_PATH'],'image','--scanners','vuln','--format','json','--output',str(path),'--timeout','10m',image],check=True)
 report=json.loads(path.read_text());v=[v for r in report.get('Results',[]) for v in r.get('Vulnerabilities',[])];summary['images'][image]={severity:sum(vv['Severity']==severity for vv in v) for severity in ['CRITICAL','HIGH','MEDIUM','LOW','UNKNOWN']}
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
