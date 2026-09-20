import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const files = (await readdir(join(root, 'workflows'))).filter((name) => name.endsWith('.json'));
assert.deepEqual(files.sort(), [
  'finance-investment-recommendation-v1.json',
  'finance-metadata-retention-v1.json',
  'finance-signed-health-v1.json',
]);

for (const file of files) {
  const workflow = JSON.parse(await readFile(join(root, 'workflows', file), 'utf8'));
  assert.equal(workflow.active, false, `${file}: import must not activate workflow`);
  assert.equal(workflow.settings.saveDataSuccessExecution, 'none');
  assert.equal(workflow.settings.saveDataErrorExecution, 'none');
  assert.equal(workflow.settings.saveManualExecutions, false);
  assert.ok(workflow.nodes.length >= 2);
  const names = new Set(workflow.nodes.map((node) => node.name));
  assert.equal(names.size, workflow.nodes.length, `${file}: duplicate node names`);
  for (const [source, outputs] of Object.entries(workflow.connections)) {
    assert.ok(names.has(source), `${file}: missing source node ${source}`);
    for (const branch of outputs.main || []) {
      for (const target of branch) assert.ok(names.has(target.node), `${file}: missing target node ${target.node}`);
    }
  }
}

const main = JSON.parse(await readFile(join(root, 'workflows', 'finance-investment-recommendation-v1.json'), 'utf8'));
const code = main.nodes.filter((node) => node.type === 'n8n-nodes-base.code').map((node) => node.parameters.jsCode).join('\n');
for (const token of [
  "https://api.deepseek.com/responses",
  "https://iss.moex.com/iss/",
  "https://www.cbr.ru/hd_base/KeyRate/",
  "redirect: 'manual'",
  'validateModelRecommendation',
  'FINANCE_CALLBACK_HMAC_SECRET',
]) assert.ok(code.includes(token), `main workflow lacks ${token}`);
for (const forbidden of ['openclaw', 'telegram', 'poruchik', 'docker.sock']) assert.ok(!code.toLowerCase().includes(forbidden));
assert.equal(code.includes('www.rbc.ru'), true, 'licensed news allowlist must be explicit');
assert.ok(code.includes('NEWS_REQUIRES_LICENSE'), 'news must fail closed');

const compose = await readFile(join(root, 'compose.yml'), 'utf8');
assert.match(compose, /FINANCE_N8N_IMAGE:-n8nio\/n8n:2\.39\.8/);
assert.match(compose, /EXECUTIONS_DATA_SAVE_ON_SUCCESS: none/);
assert.match(compose, /EXECUTIONS_DATA_SAVE_ON_ERROR: none/);
assert.match(compose, /NEWS_SOURCES_ENABLED: "false"/);
assert.doesNotMatch(compose, /docker\.sock/);

console.log(`Validated ${files.length} Finance workflows and isolated compose contract.`);
