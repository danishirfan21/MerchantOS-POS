"""Evidence-based staging gate; local test success never invents operational approval."""
import argparse,json,pathlib,os
from common import iso
STATUSES={'verified','partially_verified','not_implemented','requires_external_configuration','requires_organizational_approval','blocked'}
def assess(technical,external=None):
 controls={name:{'status':'verified' if value else 'blocked','evidence':'executed isolated integration'} for name,value in technical.items()}
 required=['realOffHostStorage','independentKeyCustodians','externalImmutableAudit','liveAlertRouting','onCallOwnership','approvedRestoreCadence','testedEscalation','productionInfrastructureReview','privacyComplianceReview','noUnresolvedProductionVulnerabilities']
 external=external or {}
 for name in required:
  record=external.get(name,{'status':'requires_organizational_approval' if name in ['independentKeyCustodians','onCallOwnership','approvedRestoreCadence','testedEscalation','privacyComplianceReview','noUnresolvedProductionVulnerabilities'] else 'requires_external_configuration','evidence':None})
  if name=='noUnresolvedProductionVulnerabilities' and name not in external:record={'status':'blocked','evidence':'staging-only vulnerability exception remains; review exact-image release reports'}
  if record['status'] not in STATUSES:raise ValueError('Invalid readiness status')
  # External claims require dated, independently reviewable evidence, not a bare boolean.
  if record['status']=='verified' and not all(record.get(k) for k in ['evidence','reviewerRole','reviewedUtc']):raise ValueError('Unsubstantiated external readiness claim')
  controls[name]=record
 staging=bool(technical) and all(technical.values());production=staging and all(controls[n]['status']=='verified' for n in required)
 return {'schema':1,'observedUtc':iso(),'sourceRevision':os.environ.get('SOURCE_REVISION',os.environ.get('GITHUB_SHA','local')),'isolatedStaging':'GO' if staging else 'NO-GO','publicProduction':'GO' if production else 'NO-GO','controls':controls,'scope':'assessment of evidence; no deployment action; human approval remains separate'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--operations-results',required=True);p.add_argument('--staging-results',required=True);p.add_argument('--output',required=True);a=p.parse_args();ops=json.loads(pathlib.Path(a.operations_results).read_text());stage=json.loads(pathlib.Path(a.staging_results).read_text());result=assess({'operationsIntegration':ops.get('result')=='passed','httpsMfaRecovery':stage.get('result')=='passed' and stage.get('checks',0)>=283,'credentialAudit':ops.get('credentialAudit')=='passed'});pathlib.Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 if result['isolatedStaging']!='GO':raise SystemExit('Isolated staging readiness gate failed')
