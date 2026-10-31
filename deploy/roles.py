"""Run only as migration owner after schema application. Passwords enter psql stdin, never argv/logs."""
import pathlib,subprocess,os
secrets=pathlib.Path(os.environ.get('MERCHANT_SECRETS','/run/secrets'))
def literal(s):return "'"+s.replace("'","''")+"'"
commands=["SELECT pg_advisory_lock(717007);"]
for role,file in [('merchant_pos','pos_db_password'),('merchant_admin_session','admin_db_password')]:
 password=(secrets/file).read_text().strip();assert len(password)>=30
 commands += [f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role} LOGIN; END IF; END $$;",f"ALTER ROLE {role} PASSWORD {literal(password)};"]
commands += ["REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO merchant_pos,merchant_admin_session;", "GRANT SELECT,INSERT,UPDATE,DELETE ON products,inventory_levels,orders,order_items,payments,checkout_idempotency,auth_users,auth_sessions TO merchant_pos;", "GRANT SELECT,INSERT ON admin_audit,inventory_adjustments TO merchant_pos; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO merchant_pos;", "GRANT SELECT,INSERT,DELETE ON admin_ticket_sessions TO merchant_admin_session;"]
commands.append("SELECT pg_advisory_unlock(717007);")
r=subprocess.run(['psql','-X','-q','-v','ON_ERROR_STOP=1'],input='\n'.join(commands),text=True,capture_output=True)
if r.returncode:raise SystemExit('Runtime role provisioning failed. No credentials logged; inspect database role policy.')
print('Separate least-privilege runtime roles provisioned; migration ownership retained by operator.')
