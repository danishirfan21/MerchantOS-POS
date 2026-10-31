-- Additive, replay-safe: never rewrite existing balances, users or receipts.
BEGIN;
ALTER TABLE products ADD COLUMN IF NOT EXISTS version bigint NOT NULL DEFAULT 1 CHECK(version>0);
ALTER TABLE inventory_levels ADD COLUMN IF NOT EXISTS version bigint NOT NULL DEFAULT 1 CHECK(version>0);
CREATE OR REPLACE FUNCTION advance_stock_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.version := OLD.version + 1; RETURN NEW; END $$;
DROP TRIGGER IF EXISTS stock_version ON inventory_levels;
CREATE TRIGGER stock_version BEFORE UPDATE ON inventory_levels FOR EACH ROW EXECUTE FUNCTION advance_stock_version();
CREATE TABLE IF NOT EXISTS admin_audit (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(), actor_id uuid NOT NULL REFERENCES auth_users(id),
 entity_type varchar(30) NOT NULL CHECK(entity_type IN ('product','inventory')), entity_id varchar(32) NOT NULL REFERENCES products(id),
 action varchar(40) NOT NULL, previous_values jsonb NOT NULL, new_values jsonb NOT NULL,
 reason varchar(500), request_id uuid NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_admin_audit_entity_time ON admin_audit(entity_id,created_at DESC,id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_time ON admin_audit(created_at DESC,id);
CREATE TABLE IF NOT EXISTS inventory_adjustments (
 id uuid PRIMARY KEY REFERENCES admin_audit(request_id), actor_id uuid NOT NULL REFERENCES auth_users(id),
 idempotency_key varchar(128) NOT NULL, request_hash varchar(64) NOT NULL,
 result jsonb NOT NULL, UNIQUE(actor_id,idempotency_key)
);
CREATE OR REPLACE FUNCTION prevent_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Administrative history is append-only'; END $$;
DROP TRIGGER IF EXISTS audit_immutable ON admin_audit;
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON admin_audit FOR EACH STATEMENT EXECUTE FUNCTION prevent_history_mutation();
DROP TRIGGER IF EXISTS adjustments_immutable ON inventory_adjustments;
CREATE TRIGGER adjustments_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory_adjustments FOR EACH STATEMENT EXECUTE FUNCTION prevent_history_mutation();
COMMIT;
