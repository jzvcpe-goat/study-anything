CREATE TABLE IF NOT EXISTS study_anything_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_anything_sessions (
    session_id TEXT PRIMARY KEY,
    user_hash TEXT NOT NULL,
    user_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS study_anything_sessions_updated_at_idx
ON study_anything_sessions (updated_at DESC);

CREATE INDEX IF NOT EXISTS study_anything_sessions_user_hash_idx
ON study_anything_sessions (user_hash);

INSERT INTO study_anything_metadata (key, value)
VALUES ('schema_version', '0.2.2-alpha')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
