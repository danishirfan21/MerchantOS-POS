"""Owner-only bounded retention; normal runtime roles cannot delete security events."""
import subprocess
sql="BEGIN; DELETE FROM security_events WHERE id IN (SELECT id FROM security_events WHERE created_at<now()-interval '90 days' ORDER BY created_at LIMIT 1000); COMMIT;"
r=subprocess.run(['psql','-X','-q','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
if r.returncode:raise SystemExit('Security retention failed; no record material logged')
print('Owner retention completed: at most 1000 security records older than 90 days.')
