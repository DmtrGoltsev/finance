CREATE TABLE IF NOT EXISTS gateway_runs (
  event_id uuid PRIMARY KEY,
  job_id uuid NOT NULL,
  attempt smallint NOT NULL CHECK (attempt BETWEEN 1 AND 3),
  payload_hash char(64) NOT NULL,
  payload bytea,
  callback bytea,
  callback_attempts smallint NOT NULL DEFAULT 0 CHECK (callback_attempts BETWEEN 0 AND 3),
  state text NOT NULL CHECK (state IN ('queued','running','interrupted','callback','ready','failed','delivery_failed')),
  lease_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE(job_id, attempt)
);
CREATE INDEX IF NOT EXISTS gateway_runs_pending ON gateway_runs(state, created_at);
CREATE TABLE IF NOT EXISTS gateway_nonces (
  nonce varchar(128) PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN gateway_runs.payload IS 'AES-256-GCM encrypted, cleared after callback acknowledgement';
