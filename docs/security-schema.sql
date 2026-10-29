CREATE TABLE IF NOT EXISTS capstone.auth_sessions (
	token_hash VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES capstone.users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_capstone_auth_sessions_user_id ON capstone.auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_capstone_auth_sessions_expires_at ON capstone.auth_sessions (expires_at);
ALTER TABLE capstone.auth_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.auth_sessions;
CREATE POLICY backend_access ON capstone.auth_sessions FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.auth_sessions TO capstone_api;

CREATE TABLE IF NOT EXISTS capstone.auth_throttles (
	key VARCHAR(64) NOT NULL,
	window_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	attempts INTEGER NOT NULL,
	PRIMARY KEY (key)
)

;
ALTER TABLE capstone.auth_throttles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.auth_throttles;
CREATE POLICY backend_access ON capstone.auth_throttles FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.auth_throttles TO capstone_api;

CREATE TABLE IF NOT EXISTS capstone.sensitive_grants (
	token_hash VARCHAR(64) NOT NULL,
	session_hash VARCHAR(64) NOT NULL,
	scope VARCHAR(100) NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(session_hash) REFERENCES capstone.auth_sessions (token_hash) ON DELETE CASCADE
)

;
CREATE INDEX IF NOT EXISTS ix_capstone_sensitive_grants_session_hash ON capstone.sensitive_grants (session_hash);
ALTER TABLE capstone.sensitive_grants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.sensitive_grants;
CREATE POLICY backend_access ON capstone.sensitive_grants FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.sensitive_grants TO capstone_api;

CREATE TABLE IF NOT EXISTS capstone.library_admins (
	user_id INTEGER NOT NULL,
	PRIMARY KEY (user_id),
	FOREIGN KEY(user_id) REFERENCES capstone.users (id)
)

;
ALTER TABLE capstone.library_admins ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.library_admins;
CREATE POLICY backend_access ON capstone.library_admins FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.library_admins TO capstone_api;

CREATE TABLE IF NOT EXISTS capstone.mfa_credentials (
	user_id INTEGER NOT NULL,
	secret TEXT NOT NULL,
	enabled INTEGER NOT NULL,
	last_step INTEGER NOT NULL,
	pending_session VARCHAR(64) NOT NULL,
	pending_expires TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (user_id),
	FOREIGN KEY(user_id) REFERENCES capstone.users (id)
)

;
ALTER TABLE capstone.mfa_credentials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.mfa_credentials;
CREATE POLICY backend_access ON capstone.mfa_credentials FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.mfa_credentials TO capstone_api;

CREATE TABLE IF NOT EXISTS capstone.mfa_challenges (
	token_hash VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES capstone.users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_capstone_mfa_challenges_expires_at ON capstone.mfa_challenges (expires_at);
CREATE INDEX IF NOT EXISTS ix_capstone_mfa_challenges_user_id ON capstone.mfa_challenges (user_id);
ALTER TABLE capstone.mfa_challenges ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.mfa_challenges;
CREATE POLICY backend_access ON capstone.mfa_challenges FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.mfa_challenges TO capstone_api;

CREATE TABLE IF NOT EXISTS capstone.mfa_recovery (
	code_hash VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	PRIMARY KEY (code_hash),
	FOREIGN KEY(user_id) REFERENCES capstone.users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_capstone_mfa_recovery_user_id ON capstone.mfa_recovery (user_id);
ALTER TABLE capstone.mfa_recovery ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS backend_access ON capstone.mfa_recovery;
CREATE POLICY backend_access ON capstone.mfa_recovery FOR ALL TO capstone_api USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.mfa_recovery TO capstone_api;
ALTER TABLE capstone.audit_logs ALTER COLUMN detail TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN company_name TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN representative TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN business_number TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN address TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN phone TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN email TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN manager_name TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN business_type TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN business_item TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN bank_name TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN account_number TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN account_holder TYPE TEXT;
ALTER TABLE capstone.companies ALTER COLUMN seal_image TYPE TEXT;
ALTER TABLE capstone.contracts ALTER COLUMN contract_title TYPE TEXT;
ALTER TABLE capstone.contracts ALTER COLUMN client_name TYPE TEXT;
ALTER TABLE capstone.contracts ALTER COLUMN description TYPE TEXT;
ALTER TABLE capstone.mfa_credentials ALTER COLUMN secret TYPE TEXT;
ALTER TABLE capstone.templates ALTER COLUMN name TYPE TEXT;
ALTER TABLE capstone.templates ALTER COLUMN description TYPE TEXT;
ALTER TABLE capstone.documents ALTER COLUMN title TYPE TEXT;
