import crypto from 'node:crypto';
import pg from 'pg';
import { fail } from './network.mjs';

export function cipher(keyHex) {
  if (!/^[a-f0-9]{64}$/i.test(keyHex || '')) fail('QUEUE_KEY_NOT_CONFIGURED', 503);
  const key = Buffer.from(keyHex, 'hex');
  return {
    seal(value) {
      const iv = crypto.randomBytes(12);
      const enc = crypto.createCipheriv('aes-256-gcm', key, iv);
      const data = Buffer.concat([enc.update(JSON.stringify(value), 'utf8'), enc.final()]);
      return Buffer.concat([iv, enc.getAuthTag(), data]);
    },
    open(value) {
      const dec = crypto.createDecipheriv('aes-256-gcm', key, value.subarray(0, 12));
      dec.setAuthTag(value.subarray(12, 28));
      return JSON.parse(Buffer.concat([dec.update(value.subarray(28)), dec.final()]).toString('utf8'));
    },
  };
}

export class Store {
  constructor(config) {
    this.pool = new pg.Pool({ host: 'postgres', port: 5432, database: config.db,
      user: config.dbUser, password: config.dbPassword, max: 4,
      connectionTimeoutMillis: 5000, statement_timeout: 10000 });
    this.crypt = cipher(config.queueKey);
  }
  async ping() { await this.pool.query('SELECT 1'); }
  async claim(job, hash, nonce) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      await client.query('SELECT pg_advisory_xact_lock(hashtextextended($1, 0))', [job.jobId]);
      const replay = await client.query('INSERT INTO gateway_nonces(nonce) VALUES($1) ON CONFLICT DO NOTHING RETURNING nonce', [nonce]);
      if (!replay.rowCount) fail('NONCE_REPLAY', 409);
      const existing = await client.query('SELECT * FROM gateway_runs WHERE event_id=$1 OR (job_id=$2 AND attempt=$3)', [job.eventId, job.jobId, job.attempt]);
      if (existing.rowCount) {
        const row = existing.rows[0];
        if (row.event_id !== job.eventId || row.payload_hash !== hash || row.job_id !== job.jobId || row.attempt !== job.attempt) fail('IDEMPOTENCY_CONFLICT', 409);
        await client.query('COMMIT');
        return { duplicate: true };
      }
      const previous = await client.query('SELECT state, attempt FROM gateway_runs WHERE job_id=$1 ORDER BY attempt DESC LIMIT 1', [job.jobId]);
      const prev = previous.rows[0];
      if ((!prev && job.attempt !== 1) || (prev && (prev.state !== 'failed' || job.attempt !== prev.attempt + 1)) || job.attempt > 3) fail('ATTEMPT_CONFLICT', 409);
      await client.query('INSERT INTO gateway_runs(event_id,job_id,attempt,payload_hash,payload,state) VALUES($1,$2,$3,$4,$5,\'queued\')',
        [job.eventId, job.jobId, job.attempt, hash, this.crypt.seal(job)]);
      await client.query('COMMIT');
      return { duplicate: false };
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  }
  async next() {
    // Crashed analyses are not silently re-executed. Their outcome is reported as failure.
    await this.pool.query("UPDATE gateway_runs SET state='interrupted', lease_until=NULL WHERE state='running' AND lease_until<now()");
    const result = await this.pool.query(`WITH candidate AS (
      SELECT event_id, state AS previous FROM gateway_runs
      WHERE state IN ('queued','interrupted','callback') AND (lease_until IS NULL OR lease_until<now())
      ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
    ) UPDATE gateway_runs r SET state=CASE WHEN c.previous='callback' THEN 'callback' ELSE 'running' END,
      lease_until=now()+interval '60 minutes'
      FROM candidate c WHERE r.event_id=c.event_id RETURNING r.*,c.previous`);
    if (!result.rowCount) return null;
    const row = result.rows[0];
    return { eventId: row.event_id, job: this.crypt.open(row.payload), previous: row.previous,
      callback: row.callback ? this.crypt.open(row.callback) : null, callbackAttempts: row.callback_attempts };
  }
  async saveCallback(eventId, callback) {
    await this.pool.query("UPDATE gateway_runs SET callback=$2,state='callback',callback_attempts=0 WHERE event_id=$1", [eventId, this.crypt.seal(callback)]);
  }
  async callbackAttempt(eventId) {
    const result = await this.pool.query('UPDATE gateway_runs SET callback_attempts=callback_attempts+1 WHERE event_id=$1 AND callback_attempts<3 RETURNING callback_attempts', [eventId]);
    return result.rowCount > 0;
  }
  async finish(eventId, state) {
    await this.pool.query('UPDATE gateway_runs SET state=$2,payload=NULL,callback=NULL,lease_until=NULL,completed_at=now() WHERE event_id=$1', [eventId, state]);
  }
  async deadLetter(eventId) {
    // Preserve the encrypted callback for operator reconciliation, never regenerate the report.
    await this.pool.query("UPDATE gateway_runs SET state='delivery_failed',lease_until=NULL,completed_at=now() WHERE event_id=$1", [eventId]);
  }
  async prune() {
    await this.pool.query("DELETE FROM gateway_nonces WHERE created_at<now()-interval '10 minutes'");
    await this.pool.query("DELETE FROM gateway_runs WHERE (state='ready' AND completed_at<now()-interval '7 days') OR (state IN ('failed','delivery_failed') AND completed_at<now()-interval '30 days')");
  }
  async close() { await this.pool.end(); }
}
