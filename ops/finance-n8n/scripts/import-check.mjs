import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const profile = await mkdtemp(join(tmpdir(), 'finance-n8n-import-'));
const env = { ...process.env, N8N_USER_FOLDER: profile, DB_TYPE: 'sqlite',
  N8N_ENCRYPTION_KEY: 'isolated-import-test-key-not-a-production-secret',
  N8N_DIAGNOSTICS_ENABLED: 'false', N8N_VERSION_NOTIFICATIONS_ENABLED: 'false',
  N8N_LOG_LEVEL: 'error', N8N_RUNNERS_ENABLED: 'false' };
delete env.DB_POSTGRESDB_HOST;
function cli(args) {
  const result = spawnSync(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['--yes', '--package=n8n@2.39.8', 'n8n', ...args],
    { cwd: root, env, encoding: 'utf8', timeout: 120000, shell: process.platform === 'win32' });
  assert.equal(result.status, 0, `n8n ${args[0]} failed: ${(result.stderr || result.stdout || result.error || '').toString().slice(-2000)}`);
  return result.stdout;
}
try {
  assert.equal(cli(['--version']).trim(), '2.39.8');
  const credentialFile = join(profile, 'credential.json');
  await writeFile(credentialFile, JSON.stringify([{ id: 'finance-gateway-token', name: 'Finance Gateway Internal Token',
    type: 'httpHeaderAuth', data: { name: 'X-Finance-Gateway-Token', value: 'ci-only-gateway-token' } }]));
  cli(['import:credentials', `--input="${credentialFile}"`]);
  cli(['import:credentials', `--input="${credentialFile}"`]);
  const credentialExport = join(profile, 'credential-export.json');
  cli(['export:credentials', '--all', `--output="${credentialExport}"`]);
  const importedCredentials = JSON.parse(await readFile(credentialExport, 'utf8'));
  assert.deepEqual(importedCredentials.map(({ id, type }) => ({ id, type })),
    [{ id: 'finance-gateway-token', type: 'httpHeaderAuth' }]);
  for (const file of (await readdir(join(root, 'workflows'))).filter((f) => f.endsWith('.json'))) {
    cli(['import:workflow', `--input="${resolve(root, 'workflows', file)}"`]);
    cli(['import:workflow', `--input="${resolve(root, 'workflows', file)}"`]);
  }
  const exported = join(profile, 'export.json');
  cli(['export:workflow', '--all', `--output="${exported}"`]);
  const workflows = JSON.parse(await readFile(exported, 'utf8'));
  assert.equal(workflows.length, 3);
  assert.equal(new Set(workflows.map((w) => w.id)).size, 3);
  assert.ok(workflows.every((w) => w.active === false));
  for (const workflow of workflows) {
    cli(['publish:workflow', `--id=${workflow.id}`]);
    cli(['publish:workflow', `--id=${workflow.id}`]);
  }
  console.log('n8n@2.39.8 credential import and three workflow import/publish PASS in isolated SQLite profile.');
} finally {
  if (!profile.startsWith(join(tmpdir(), 'finance-n8n-import-'))) throw new Error('Unsafe cleanup path');
  await rm(profile, { recursive: true, force: true });
}
