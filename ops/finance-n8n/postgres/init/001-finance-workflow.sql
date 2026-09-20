CREATE TABLE IF NOT EXISTS finance_analysis_runs (
    event_id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    attempt smallint NOT NULL CHECK (attempt BETWEEN 1 AND 3),
    payload_hash char(64) NOT NULL,
    state text NOT NULL CHECK (state IN ('queued', 'collecting', 'analyzing', 'ready', 'failed')),
    error_code text,
    lease_until timestamptz,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_finance_analysis_runs_retention
    ON finance_analysis_runs (state, completed_at);

COMMENT ON TABLE finance_analysis_runs IS
    'Sanitized workflow metadata only. Portfolio payloads and model responses are never stored here.';

CREATE OR REPLACE FUNCTION claim_finance_analysis_run(
    p_event_id uuid,
    p_job_id uuid,
    p_attempt smallint,
    p_payload_hash char(64)
)
RETURNS TABLE (claimed boolean, same_payload boolean, current_state text)
LANGUAGE plpgsql
AS $$
DECLARE
    current_row finance_analysis_runs%ROWTYPE;
BEGIN
    INSERT INTO finance_analysis_runs (
        event_id, job_id, attempt, payload_hash, state, lease_until
    ) VALUES (
        p_event_id, p_job_id, p_attempt, p_payload_hash, 'queued', now() + interval '15 minutes'
    )
    ON CONFLICT (event_id) DO NOTHING;

    IF FOUND THEN
        RETURN QUERY SELECT true, true, 'queued'::text;
        RETURN;
    END IF;

    SELECT * INTO current_row
    FROM finance_analysis_runs
    WHERE event_id = p_event_id
    FOR UPDATE;

    IF current_row.payload_hash <> p_payload_hash
       OR current_row.job_id <> p_job_id
       OR current_row.attempt <> p_attempt THEN
        RETURN QUERY SELECT false, false, current_row.state;
        RETURN;
    END IF;

    IF current_row.state IN ('ready', 'failed')
       OR current_row.lease_until >= now() THEN
        UPDATE finance_analysis_runs
        SET last_seen_at = now()
        WHERE event_id = p_event_id;
        RETURN QUERY SELECT false, true, current_row.state;
        RETURN;
    END IF;

    UPDATE finance_analysis_runs
    SET state = 'queued',
        error_code = NULL,
        last_seen_at = now(),
        lease_until = now() + interval '15 minutes'
    WHERE event_id = p_event_id;
    RETURN QUERY SELECT true, true, 'queued'::text;
END;
$$;

CREATE OR REPLACE FUNCTION prune_finance_analysis_runs()
RETURNS TABLE (deleted_success bigint, deleted_error bigint)
LANGUAGE plpgsql
AS $$
DECLARE
    ready_count bigint;
    failed_count bigint;
BEGIN
    DELETE FROM finance_analysis_runs
    WHERE state = 'ready'
      AND completed_at < now() - interval '7 days';
    GET DIAGNOSTICS ready_count = ROW_COUNT;

    DELETE FROM finance_analysis_runs
    WHERE state = 'failed'
      AND completed_at < now() - interval '30 days';
    GET DIAGNOSTICS failed_count = ROW_COUNT;

    RETURN QUERY SELECT ready_count, failed_count;
END;
$$;
