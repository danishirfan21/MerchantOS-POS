BEGIN;
CREATE TABLE IF NOT EXISTS security_event_outbox(
 sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 event_id uuid NOT NULL UNIQUE,
 payload jsonb NOT NULL,
 queued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 delivered_at timestamptz,
 batch_key text,
 batch_hash varchar(64)
);
CREATE INDEX IF NOT EXISTS ix_security_outbox_pending ON security_event_outbox(sequence) WHERE delivered_at IS NULL;
CREATE TABLE IF NOT EXISTS security_export_state(singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),last_sequence bigint NOT NULL DEFAULT 0,head_key text NOT NULL DEFAULT '',head_hash varchar(64) NOT NULL DEFAULT '',updated_at timestamptz);
INSERT INTO security_export_state(singleton) VALUES(true) ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION queue_security_event() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(717019);
 INSERT INTO public.security_event_outbox(event_id,payload) VALUES(NEW.id,jsonb_build_object('id',NEW.id,'timestamp',NEW.created_at,'category',NEW.category,'actorId',NEW.actor_id,'targetId',NEW.target_id,'outcome',NEW.outcome,'correlationId',NEW.correlation_id));
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION queue_security_event() FROM PUBLIC;
DROP TRIGGER IF EXISTS security_event_outbox_insert ON security_events;
CREATE TRIGGER security_event_outbox_insert AFTER INSERT ON security_events FOR EACH ROW EXECUTE FUNCTION queue_security_event();
-- Backfill once in deterministic order; replay never duplicates logical events.
INSERT INTO security_event_outbox(event_id,payload) SELECT id,jsonb_build_object('id',id,'timestamp',created_at,'category',category,'actorId',actor_id,'targetId',target_id,'outcome',outcome,'correlationId',correlation_id) FROM security_events ORDER BY created_at,id ON CONFLICT(event_id) DO NOTHING;
CREATE OR REPLACE VIEW ops_security_signals AS SELECT
 (SELECT count(*) FROM security_event_outbox WHERE delivered_at IS NULL) AS audit_backlog,
 (SELECT coalesce(extract(epoch FROM clock_timestamp()-min(queued_at)),0) FROM security_event_outbox WHERE delivered_at IS NULL) AS audit_oldest_seconds,
 (SELECT count(*) FROM security_events WHERE category='mfa_verification' AND outcome='failed' AND created_at>clock_timestamp()-interval '5 minutes') AS mfa_failures,
 (SELECT count(*) FROM security_events WHERE category='primary_authentication' AND outcome='failed' AND created_at>clock_timestamp()-interval '5 minutes') AS authentication_failures,
 (SELECT count(*) FROM auth_users WHERE greatest(locked_until,mfa_locked_until)>clock_timestamp()) AS locked_accounts,
 (SELECT count(*) FROM security_events WHERE category IN ('operator_recover','operator_password','operator_mfa_reset','operator_restore_recover','operator_role','operator_disable','operator_revoke') AND created_at>clock_timestamp()-interval '5 minutes') AS privileged_events;
-- Runtime may enroll/verify factors but cannot perform privileged role/disable/MFA-reset transitions.
CREATE OR REPLACE FUNCTION guard_runtime_identity_changes() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
 IF current_user='merchant_pos' AND (OLD.role IS DISTINCT FROM NEW.role OR OLD.enabled IS DISTINCT FROM NEW.enabled OR (OLD.mfa_enabled AND (NOT NEW.mfa_enabled OR OLD.mfa_secret IS DISTINCT FROM NEW.mfa_secret))) THEN
  RAISE EXCEPTION 'Privileged identity operator role required' USING ERRCODE='42501';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS guard_runtime_identity_update ON auth_users;
CREATE TRIGGER guard_runtime_identity_update BEFORE UPDATE ON auth_users FOR EACH ROW EXECUTE FUNCTION guard_runtime_identity_changes();
COMMIT;
