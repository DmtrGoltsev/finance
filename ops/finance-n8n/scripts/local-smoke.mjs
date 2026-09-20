import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const temp = await mkdtemp(join(tmpdir(), 'finance-n8n-smoke-'));
const envFile = join(temp, '.env');
const project = `finance-n8n-smoke-${process.pid}`;
const externalNetwork = 'finance_backend_internal';
let createdNetwork = false;

const run = (command, args, options = {}) => {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8', stdio: options.capture ? 'pipe' : 'inherit' });
  if (result.status !== 0 && !options.allowFailure) {
    throw new Error(`${command} ${args.join(' ')} failed: ${result.stderr || result.stdout}`);
  }
  return result;
};

const compose = (...args) => run('docker', ['compose', '--env-file', envFile, '-p', project, '-f', join(root, 'compose.yml'), ...args], { capture: true });

await writeFile(envFile, [
  `COMPOSE_PROJECT_NAME=${project}`,
  'FINANCE_N8N_IMAGE=n8nio/n8n:2.39.8',
  'FINANCE_N8N_POSTGRES_DB=finance_n8n',
  'FINANCE_N8N_POSTGRES_USER=finance_n8n',
  'FINANCE_N8N_POSTGRES_PASSWORD=smoke-postgres-password-only',
  'N8N_ENCRYPTION_KEY=smoke-encryption-key-32-bytes-minimum-only',
  'FINANCE_INGRESS_HMAC_SECRET=smoke-ingress-secret-32-bytes-minimum-only',
  'FINANCE_CALLBACK_HMAC_SECRET=smoke-callback-secret-32-bytes-minimum-only',
  'DEEPSEEK_API_KEY=smoke-provider-key-not-real',
  'DEEPSEEK_MODEL=deepseek-v4-pro',
  'FINANCE_BACKEND_INTERNAL_URL=http://finance-backend:8000',
  'FINANCE_N8N_LISTEN_ADDRESS=127.0.0.1',
  'FINANCE_N8N_LISTEN_PORT=0',
  'TZ=Europe/Moscow',
].join('\n'), 'utf8');

try {
  const network = run('docker', ['network', 'inspect', externalNetwork], { capture: true, allowFailure: true });
  if (network.status !== 0) {
    run('docker', ['network', 'create', '--internal', externalNetwork], { capture: true });
    createdNetwork = true;
  }

  const rendered = compose('config').stdout;
  assert.match(rendered, /n8nio\/n8n:2\.39\.8/);
  assert.doesNotMatch(rendered, /replace-with-/);

  compose('up', '-d', '--wait');
  const ps = JSON.parse(compose('ps', '--format', 'json').stdout);
  const rows = Array.isArray(ps) ? ps : [ps];
  assert.equal(rows.length, 2);
  assert.ok(rows.every((row) => row.State === 'running' && row.Health === 'healthy'));

  for (const workflow of ['finance-investment-recommendation-v1.json', 'finance-signed-health-v1.json', 'finance-metadata-retention-v1.json']) {
    compose('exec', '-T', 'n8n', 'n8n', 'import:workflow', `--input=/home/node/.n8n/imports/${workflow}`);
  }

  const event = '11111111-1111-4111-8111-111111111111';
  const job = '22222222-2222-4222-8222-222222222222';
  const hashA = 'a'.repeat(64);
  const hashB = 'b'.repeat(64);
  const sql = [
    `SELECT claimed || ':' || same_payload FROM claim_finance_analysis_run('${event}','${job}',1,'${hashA}');`,
    `SELECT claimed || ':' || same_payload FROM claim_finance_analysis_run('${event}','${job}',1,'${hashA}');`,
    `SELECT claimed || ':' || same_payload FROM claim_finance_analysis_run('${event}','${job}',1,'${hashB}');`,
  ].join(' ');
  const claims = compose('exec', '-T', 'postgres', 'psql', '-U', 'finance_n8n', '-d', 'finance_n8n', '-Atqc', sql).stdout.trim().split(/\r?\n/);
  assert.deepEqual(claims, ['true:true', 'false:true', 'false:false']);

  const retentionSql = "INSERT INTO finance_analysis_runs(event_id,job_id,attempt,payload_hash,state,completed_at) VALUES ('33333333-3333-4333-8333-333333333333','44444444-4444-4444-8444-444444444444',1,repeat('c',64),'ready',now()-interval '8 days'),('55555555-5555-4555-8555-555555555555','66666666-6666-4666-8666-666666666666',1,repeat('d',64),'failed',now()-interval '31 days'); SELECT deleted_success || ':' || deleted_error FROM prune_finance_analysis_runs();";
  const retention = compose('exec', '-T', 'postgres', 'psql', '-U', 'finance_n8n', '-d', 'finance_n8n', '-Atqc', retentionSql).stdout.trim();
  assert.equal(retention, '1:1');

  console.log('Operational smoke PASS: compose, health, workflow import, idempotency and 7/30 retention.');
} finally {
  compose('down', '-v', '--remove-orphans');
  if (createdNetwork) run('docker', ['network', 'rm', externalNetwork], { capture: true, allowFailure: true });
  await rm(temp, { recursive: true, force: true });
}
