BEGIN;
CREATE TABLE IF NOT EXISTS admin_ticket_sessions (
 id_hash varchar(64) PRIMARY KEY, user_id uuid NOT NULL REFERENCES auth_users(id),
 protected_ticket bytea NOT NULL, expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_admin_ticket_expiry ON admin_ticket_sessions(expires_at);
COMMIT;
