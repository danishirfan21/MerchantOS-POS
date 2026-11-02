"""CI-only lifecycle for the real browser-test API; no arbitrary process targeting."""
import json,os,pathlib,signal,subprocess,sys
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Disposable CI only')
root=pathlib.Path(__file__).resolve().parent.parent;state=root/'.retail-api.json';dll=root/'services/merchant-api/bin/Release/net10.0/MerchantOS.Api.dll'
if sys.argv[1]=='start':
 with open(root/'api.log','ab') as log:child=subprocess.Popen(['dotnet',str(dll)],cwd=dll.parents[3],stdout=log,stderr=log,start_new_session=True)
 state.touch(mode=0o600);state.write_text(json.dumps({'pid':child.pid,'assembly':str(dll)}));print('Disposable retail API started.')
elif sys.argv[1]=='stop':
 record=json.loads(state.read_text());pid=record['pid'];command=pathlib.Path('/proc')/str(pid)/'cmdline'
 if record['assembly']!=str(dll) or not command.exists() or str(dll).encode() not in command.read_bytes().split(b'\0'):raise SystemExit('Refusing to signal an unrelated process')
 os.killpg(pid,signal.SIGTERM);print('Disposable retail API stopped.')
else:raise SystemExit('Use start or stop')
