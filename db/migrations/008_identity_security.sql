-- Additive identity hardening. Legacy admin sessions have no MFA proof and are rejected.
BEGIN;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS security_version bigint NOT NULL DEFAULT 1;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS mfa_secret bytea;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS mfa_enabled boolean NOT NULL DEFAULT false;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS mfa_failures integer NOT NULL DEFAULT 0;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS mfa_locked_until timestamptz;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS mfa_last_step bigint NOT NULL DEFAULT -1;
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS security_version bigint NOT NULL DEFAULT 1;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS mfa_verified_at timestamptz;
ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS mfa_method varchar(16);
CREATE TABLE IF NOT EXISTS auth_challenges(
 id_hash varchar(64) PRIMARY KEY, user_id uuid NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
 security_version bigint NOT NULL, purpose varchar(16) NOT NULL CHECK(purpose IN ('enroll','verify','password')),
 pending_secret bytea, enrollment_shown boolean NOT NULL DEFAULT false,
 expires_at timestamptz NOT NULL, attempts integer NOT NULL DEFAULT 0, consumed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_auth_challenges_expiry ON auth_challenges(expires_at);
CREATE TABLE IF NOT EXISTS auth_recovery_codes(
 user_id uuid NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE, code_hash varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), consumed_at timestamptz,
 PRIMARY KEY(user_id,code_hash)
);
CREATE TABLE IF NOT EXISTS security_events(
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(), category varchar(64) NOT NULL,
 actor_id uuid, target_id uuid, outcome varchar(32) NOT NULL, correlation_id varchar(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_security_events_time ON security_events(created_at DESC,id);
CREATE INDEX IF NOT EXISTS ix_security_events_target_time ON security_events(target_id,created_at DESC);
-- A restored copy is quarantined per account until explicit identity reconciliation.
CREATE TABLE IF NOT EXISTS auth_restore_blocks(user_id uuid PRIMARY KEY REFERENCES auth_users(id) ON DELETE CASCADE, created_at timestamptz NOT NULL DEFAULT now());

COMMIT;
