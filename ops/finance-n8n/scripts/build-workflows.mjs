import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const runtime = async (name) => {
  const core = await readFile(join(root, 'runtime', 'security-core.n8n.js'), 'utf8');
  const body = await readFile(join(root, 'runtime', name), 'utf8');
  return `${core.trim()}\n\n${body.trim()}\n`;
};

const codeNode = (name, id, position, jsCode) => ({
  parameters: { mode: 'runOnceForAllItems', jsCode },
  id,
  name,
  type: 'n8n-nodes-base.code',
  typeVersion: 2,
  position,
});

const postgresCredentials = { postgres: { name: 'Finance n8n PostgreSQL' } };

const main = {
  name: 'Finance Investment Recommendation v1',
  nodes: [
    {
      parameters: {
        httpMethod: 'POST',
        path: 'internal/finance/investments/recommendations/v1',
        responseMode: 'onReceived',
        options: { responseCode: 202, rawBody: true },
      },
      id: 'd6f7d654-fba7-4cdf-8f50-135d62a59001',
      name: 'Приём задания Finance',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 2.1,
      position: [-620, 0],
      webhookId: 'finance-investment-recommendation-v1',
    },
    codeNode('Проверить HMAC и контракт', 'd6f7d654-fba7-4cdf-8f50-135d62a59002', [-380, 0], await runtime('verify-ingress.n8n.js')),
    {
      parameters: {
        operation: 'executeQuery',
        query: 'SELECT claimed, same_payload, current_state, $5::text AS event_id, $6::text AS job_json FROM claim_finance_analysis_run($1::uuid, $2::uuid, $3::smallint, $4::char(64));',
        options: {
          queryReplacement: '={{ [$json.event_id, $json.job_id, $json.attempt, $json.payload_hash, $json.event_id, $json.job_json] }}',
        },
      },
      id: 'd6f7d654-fba7-4cdf-8f50-135d62a59003',
      name: 'Захватить идемпотентное задание',
      type: 'n8n-nodes-base.postgres',
      typeVersion: 2.6,
      position: [-120, 0],
      credentials: postgresCredentials,
    },
    codeNode('Собрать данные и получить рекомендацию', 'd6f7d654-fba7-4cdf-8f50-135d62a59004', [140, 0], await runtime('orchestrate.n8n.js')),
    {
      parameters: {
        operation: 'executeQuery',
        query: "UPDATE finance_analysis_runs SET state = $2::text, error_code = NULLIF($3::text, ''), completed_at = now(), last_seen_at = now(), lease_until = NULL WHERE event_id = $1::uuid AND $2::text IN ('ready', 'failed') RETURNING event_id, state, error_code;",
        options: { queryReplacement: "={{ [$json.event_id, $json.state, $json.error_code || ''] }}" },
      },
      id: 'd6f7d654-fba7-4cdf-8f50-135d62a59005',
      name: 'Зафиксировать безопасный результат',
      type: 'n8n-nodes-base.postgres',
      typeVersion: 2.6,
      position: [420, 0],
      credentials: postgresCredentials,
    },
  ],
  connections: {
    'Приём задания Finance': { main: [[{ node: 'Проверить HMAC и контракт', type: 'main', index: 0 }]] },
    'Проверить HMAC и контракт': { main: [[{ node: 'Захватить идемпотентное задание', type: 'main', index: 0 }]] },
    'Захватить идемпотентное задание': { main: [[{ node: 'Собрать данные и получить рекомендацию', type: 'main', index: 0 }]] },
    'Собрать данные и получить рекомендацию': { main: [[{ node: 'Зафиксировать безопасный результат', type: 'main', index: 0 }]] },
  },
  active: false,
  settings: {
    executionOrder: 'v1',
    saveDataSuccessExecution: 'none',
    saveDataErrorExecution: 'none',
    saveManualExecutions: false,
    callerPolicy: 'workflowsFromSameOwner',
    timezone: 'Europe/Moscow',
  },
  versionId: 'd6f7d654-fba7-4cdf-8f50-135d62a59999',
  meta: { templateCredsSetupCompleted: false, financeContractVersion: 1 },
  tags: [{ name: 'finance' }, { name: 'investments' }],
};

const health = {
  name: 'Finance n8n Signed Health v1',
  nodes: [
    {
      parameters: { httpMethod: 'POST', path: 'internal/finance/health/v1', responseMode: 'lastNode', options: { rawBody: true } },
      id: 'a178598a-17ee-4aa6-a5c0-727275080001',
      name: 'Подписанная проверка готовности',
      type: 'n8n-nodes-base.webhook', typeVersion: 2.1, position: [-260, 0], webhookId: 'finance-n8n-health-v1',
    },
    codeNode('Проверить подпись готовности', 'a178598a-17ee-4aa6-a5c0-727275080002', [0, 0], await runtime('verify-health.n8n.js')),
  ],
  connections: { 'Подписанная проверка готовности': { main: [[{ node: 'Проверить подпись готовности', type: 'main', index: 0 }]] } },
  active: false,
  settings: { executionOrder: 'v1', saveDataSuccessExecution: 'none', saveDataErrorExecution: 'none', saveManualExecutions: false, timezone: 'Europe/Moscow' },
  versionId: 'a178598a-17ee-4aa6-a5c0-727275089999',
  meta: { templateCredsSetupCompleted: false, financeContractVersion: 1 },
  tags: [{ name: 'finance' }, { name: 'health' }],
};

const retention = {
  name: 'Finance n8n Metadata Retention v1',
  nodes: [
    {
      parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 6 }] } },
      id: 'cb4243b4-39d8-45ea-a78f-11661b110001', name: 'Каждые шесть часов', type: 'n8n-nodes-base.scheduleTrigger', typeVersion: 1.2, position: [-220, 0],
    },
    {
      parameters: { operation: 'executeQuery', query: 'SELECT deleted_success, deleted_error FROM prune_finance_analysis_runs();', options: {} },
      id: 'cb4243b4-39d8-45ea-a78f-11661b110002', name: 'Удалить истёкшие метаданные', type: 'n8n-nodes-base.postgres', typeVersion: 2.6, position: [40, 0], credentials: postgresCredentials,
    },
  ],
  connections: { 'Каждые шесть часов': { main: [[{ node: 'Удалить истёкшие метаданные', type: 'main', index: 0 }]] } },
  active: false,
  settings: { executionOrder: 'v1', saveDataSuccessExecution: 'none', saveDataErrorExecution: 'none', saveManualExecutions: false, timezone: 'Europe/Moscow' },
  versionId: 'cb4243b4-39d8-45ea-a78f-11661b119999',
  meta: { templateCredsSetupCompleted: false, financeContractVersion: 1 },
  tags: [{ name: 'finance' }, { name: 'retention' }],
};

await mkdir(join(root, 'workflows'), { recursive: true });
for (const [file, workflow] of [['finance-investment-recommendation-v1.json', main], ['finance-signed-health-v1.json', health], ['finance-metadata-retention-v1.json', retention]]) {
  await writeFile(join(root, 'workflows', file), `${JSON.stringify(workflow, null, 2)}\n`, 'utf8');
}
