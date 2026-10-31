BEGIN;
CREATE TABLE IF NOT EXISTS auth_users (
 id uuid PRIMARY KEY, username varchar(80) NOT NULL UNIQUE,
 password_hash text NOT NULL, role varchar(32) NOT NULL CHECK(role IN ('Administrator','Cashier')),
 enabled boolean NOT NULL DEFAULT true, failures integer NOT NULL DEFAULT 0,
 locked_until timestamptz, created_at timestamptz NOT NULL DEFAULT now(), last_login_at timestamptz
);
CREATE TABLE IF NOT EXISTS auth_sessions (
 id varchar(64) PRIMARY KEY, user_id uuid NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expiry ON auth_sessions(expires_at);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES auth_users(id);
CREATE INDEX IF NOT EXISTS ix_orders_created_by ON orders(created_by,created_at DESC);
COMMIT;
