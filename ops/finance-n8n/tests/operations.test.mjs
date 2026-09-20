import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const text = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');
test('restore commands use configured DB user and isolated generated databases', async () => {
  const source = await text('scripts/restore-drill.ps1');
  assert.doesNotMatch(source, /-U\s+finance_n8n/);
  for (const command of ['createdb', 'pg_restore', 'psql', 'dropdb']) assert.ok(source.includes(`${command} -U "$POSTGRES_USER"`));
  assert.match(source, /finance_restore_/);
  assert.match(source, /RESTORE_TO_ISOLATED_DATABASE/);
  assert.match(source, /@\("n8n", "gateway"\)/);
});
test('backup includes both databases and avoids text pipeline for dump', async () => {
  const source = await text('scripts/backup.ps1');
  assert.match(source, /\$FINANCE_GATEWAY_DB/);
  assert.match(source, /\$POSTGRES_DB/);
  assert.match(source, /"cp", "postgres:\$containerFile"/);
  assert.doesNotMatch(source, /Get-Content.*dump|pg_dump.* > /);
});
test('DB constraints enforce idempotency and max3; retention clears success/error separately', async () => {
  const schema = await text('postgres/gateway-schema.sql');
  assert.match(schema, /UNIQUE\(job_id, attempt\)/);
  assert.match(schema, /attempt BETWEEN 1 AND 3/);
  assert.match(schema, /callback_attempts BETWEEN 0 AND 3/);
  const store = await text('gateway/store.mjs');
  assert.match(store, /FOR UPDATE SKIP LOCKED/);
  assert.match(store, /interval '7 days'/);
  assert.match(store, /interval '30 days'/);
  assert.match(store, /payload=NULL,callback=NULL/);
});
test('gateway has no published port; n8n contains no provider/HMAC/queue key', async () => {
  const compose = await text('compose.yml');
  const n8n = compose.split('  n8n:')[1].split('  analysis-gateway:')[0];
  const gateway = compose.split('  analysis-gateway:')[1].split('\nnetworks:')[0];
  assert.doesNotMatch(gateway, /\n\s+ports:/);
  assert.doesNotMatch(n8n, /DEEPSEEK_API_KEY|FINANCE_CALLBACK_HMAC_SECRET|FINANCE_GATEWAY_QUEUE_KEY|FINANCE_INGRESS_HMAC_SECRET/);
  assert.match(n8n, /N8N_BLOCK_ENV_ACCESS_IN_NODE: "true"/);
  assert.match(n8n, /n8n-nodes-base.code/);
});
