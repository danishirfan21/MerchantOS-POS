"""Public certificate inventory only. Never copies/exports a recovery private key."""
import argparse,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--certificate',action='append',required=True,help='purpose=/path/to/public-certificate.pem');p.add_argument('--output',required=True);a=p.parse_args();records=[]
for value in a.certificate:
 role,path=value.split('=',1)
 if role not in ['backup-encryption','data-protection','audit-witness','tls']:raise SystemExit('Known certificate purpose required')
 data=subprocess.check_output(['openssl','x509','-in',path,'-fingerprint','-sha256','-serial','-dates','-noout'],text=True,stderr=subprocess.DEVNULL)
 records.append({'purpose':role,'publicCertificateMetadata':data.splitlines(),'custodianRoleDefined':True,'realCustodianAssigned':False,'approvalEvidence':None})
pathlib.Path(a.output).write_text(json.dumps({'schema':1,'certificates':records,'scope':'public inventory; ownership is not assigned by this tool'},indent=2))
