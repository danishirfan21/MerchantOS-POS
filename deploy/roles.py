"""Run only as migration owner after schema application. Passwords enter psql stdin, never argv/logs."""
import pathlib,subprocess,os
secrets=pathlib.Path(os.environ.get('MERCHANT_SECRETS','/run/secrets'))
def literal(s):return "'"+s.replace("'","''")+"'"
commands=["SELECT pg_advisory_lock(717007);"]
for role,file in [('merchant_pos','pos_db_password'),('merchant_admin_session','admin_db_password'),('merchant_backup','backup_db_password'),('merchant_security_exporter','export_db_password'),('merchant_monitor','monitor_db_password')]:
 password=(secrets/file).read_text().strip();assert len(password)>=30
 commands += [f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role} LOGIN; END IF; END $$;",f"ALTER ROLE {role} PASSWORD {literal(password)};"]
commands += ["REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO merchant_pos,merchant_admin_session;", "GRANT SELECT,INSERT,UPDATE,DELETE ON products,inventory_levels,orders,order_items,payments,checkout_idempotency,auth_users,auth_sessions TO merchant_pos;", "GRANT SELECT,INSERT ON admin_audit,inventory_adjustments TO merchant_pos;", "GRANT SELECT,INSERT,DELETE ON admin_ticket_sessions TO merchant_admin_session;", "GRANT SELECT,INSERT,UPDATE,DELETE ON auth_challenges,auth_recovery_codes TO merchant_pos; GRANT SELECT ON auth_restore_blocks TO merchant_pos; GRANT SELECT,INSERT ON security_events TO merchant_pos;"]
commands += ["GRANT USAGE,SELECT ON order_items_id_seq,payments_id_seq TO merchant_pos;", "GRANT pg_read_all_data TO merchant_backup; GRANT USAGE ON SCHEMA public TO merchant_backup,merchant_security_exporter,merchant_monitor; GRANT SELECT ON security_event_outbox,security_export_state TO merchant_security_exporter; GRANT UPDATE(delivered_at,batch_key,batch_hash) ON security_event_outbox TO merchant_security_exporter; GRANT UPDATE(last_sequence,head_key,head_hash,updated_at) ON security_export_state TO merchant_security_exporter; GRANT SELECT ON ops_security_signals TO merchant_monitor; REVOKE ALL ON security_event_outbox,security_export_state FROM merchant_pos,merchant_admin_session;"]
commands.append("SELECT pg_advisory_unlock(717007);")
r=subprocess.run(['psql','-X','-q','-v','ON_ERROR_STOP=1'],input='\n'.join(commands),text=True,capture_output=True)
if r.returncode:raise SystemExit('Runtime role provisioning failed. No credentials logged; inspect database role policy.')
print('Separate least-privilege runtime roles provisioned; migration ownership retained by operator.')
