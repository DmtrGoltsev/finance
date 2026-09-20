import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
const run = (args) => spawnSync('docker', args, { cwd: root, encoding: 'utf8', timeout: 300000 });
const daemon = run(['info', '--format', '{{.ServerVersion}}']);
if (daemon.status !== 0) {
  console.error(`DOCKER_SMOKE_BLOCKED: ${daemon.stderr.trim()}`);
  process.exitCode = 2;
} else {
  const temp = await mkdtemp(join(tmpdir(), 'finance-gateway-smoke-'));
  const envFile = join(temp, '.env');
  const project = `finance-gateway-smoke-${process.pid}`;
  const network = `${project}-backend`;
  // A new isolated backend network, never the real Finance network.
  const override = join(temp, 'override.json');
  await writeFile(override, JSON.stringify({ networks: { finance_backend_bridge: { external: true, name: network } } }));
  await writeFile(envFile, [
    'FINANCE_N8N_POSTGRES_DB=finance_n8n', 'FINANCE_N8N_POSTGRES_USER=finance_smoke_admin',
    'FINANCE_N8N_POSTGRES_PASSWORD=smoke-only-db-password', 'N8N_ENCRYPTION_KEY=smoke-only-encryption-key-32-bytes',
    'FINANCE_GATEWAY_DB=finance_analysis', 'FINANCE_GATEWAY_DB_USER=finance_smoke_gateway',
    'FINANCE_GATEWAY_DB_PASSWORD=smoke-gateway-password', `FINANCE_GATEWAY_TOKEN=${'c'.repeat(64)}`,
    `FINANCE_GATEWAY_QUEUE_KEY=${'d'.repeat(64)}`, `FINANCE_INGRESS_HMAC_SECRET=${'a'.repeat(64)}`,
    `FINANCE_CALLBACK_HMAC_SECRET=${'b'.repeat(64)}`, 'DEEPSEEK_API_KEY=smoke-not-provider-key',
    'DEEPSEEK_MODEL=smoke-no-provider-calls', 'FINANCE_N8N_LISTEN_PORT=0',
  ].join('\n'));
  const compose = (...args) => {
    const result = run(['compose', '--env-file', envFile, '-p', project, '-f', join(root, 'compose.yml'), '-f', override, ...args]);
    assert.equal(result.status, 0, result.stderr);
    return result.stdout;
  };
  let networkCreated = false;
  try {
    assert.equal(run(['network', 'create', '--internal', network]).status, 0); networkCreated = true;
    compose('config', '--quiet');
    compose('up', '-d', '--build', '--wait', '--wait-timeout', '180');
    const rows = compose('ps', '--format', 'json').trim().split(/\r?\n/).map((line) => JSON.parse(line)).flat();
    assert.equal(rows.length, 3);
    assert.ok(rows.every((row) => row.Health === 'healthy'));
    for (const id of ['finance-investment-recommendation-v1', 'finance-signed-health-v1', 'finance-metadata-retention-v1']) {
      compose('exec', '-T', 'n8n', 'n8n', 'import:workflow', `--input=/home/node/.n8n/imports/${id}.json`);
    }
    const check = `import {Store} from './gateway/store.mjs'; import {readConfig} from './gateway/server.mjs'; import {accept,HEALTH_PATH} from './gateway/ingress.mjs'; import {hmacSignature} from './gateway/core.mjs';
      const config=readConfig(),store=new Store(config),body=Buffer.from('{}'),timestamp=Math.floor(Date.now()/1000),nonce='smoke-health-123456789';
      const signature=hmacSignature({secret:config.ingressSecret,method:'POST',path:HEALTH_PATH,timestamp,nonce,body});
      const r=await accept(body,{'x-finance-gateway-token':config.gatewayToken,'x-finance-timestamp':String(timestamp),'x-finance-nonce':nonce,'x-finance-signature':signature},config,store,{health:true});
      if(r.status!==200)throw Error('health'); await store.prune(); await store.close();`;
    compose('exec', '-T', 'analysis-gateway', 'node', '--input-type=module', '-e', check);
    console.log('Docker smoke PASS: 3 healthy services, isolated DB, actual n8n import, signed gateway health, retention query. No provider calls.');
  } finally {
    compose('down', '-v', '--remove-orphans');
    if (networkCreated) run(['network', 'rm', network]);
    if (!temp.startsWith(join(tmpdir(), 'finance-gateway-smoke-'))) throw Error('Unsafe cleanup');
    await rm(temp, { recursive: true, force: true });
  }
}
