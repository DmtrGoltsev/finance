import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const credentials = { httpHeaderAuth: { id: 'finance-gateway-token', name: 'Finance Gateway Internal Token' } };
const settings = { executionOrder: 'v1', saveDataSuccessExecution: 'none', saveDataErrorExecution: 'none', saveManualExecutions: false, timezone: 'Europe/Moscow', executionTimeout: 1800 };
const httpNode = (name, path, position, ingress = false) => ({
  id: `finance-http-${path.slice(1)}`, name, type: 'n8n-nodes-base.httpRequest', typeVersion: 4.2, position,
  credentials,
  parameters: {
    method: 'POST', url: `http://analysis-gateway:8080${path}`,
    authentication: 'genericCredentialType', genericAuthType: 'httpHeaderAuth',
    ...(ingress ? {
      sendHeaders: true, headerParameters: { parameters: [
        ...['timestamp', 'nonce', 'signature'].map((field) => ({ name: `x-finance-${field}`, value: `={{ $json.headers['x-finance-${field}'] || '' }}` })),
        { name: 'content-type', value: 'application/octet-stream' },
      ] },
      sendBody: true, contentType: 'binaryData', inputDataFieldName: 'data',
    } : {}),
    options: {
      timeout: ingress ? 15000 : 1800000,
      redirect: { redirect: { followRedirects: false } },
      response: { response: { fullResponse: true, neverError: ingress, responseFormat: 'json' } },
    },
  },
});
function ingressWorkflow(id, name, path, target) {
  const webhook = { id: `${id}-webhook`, name: 'Приём подписанного запроса', type: 'n8n-nodes-base.webhook', typeVersion: 2.1,
    position: [0, 0], webhookId: id,
    parameters: { httpMethod: 'POST', path, responseMode: 'responseNode', options: { rawBody: true } } };
  const forward = httpNode('Проверка и приём gateway', target, [260, 0], true);
  const respond = { id: `${id}-respond`, name: 'Ответ после проверки', type: 'n8n-nodes-base.respondToWebhook', typeVersion: 1.4, position: [520, 0],
    parameters: { respondWith: 'json', responseBody: '={{ $json.body }}', options: { responseCode: '={{ $json.statusCode }}' } } };
  return { id, name, active: false, settings, nodes: [webhook, forward, respond], connections: {
    [webhook.name]: { main: [[{ node: forward.name, type: 'main', index: 0 }]] },
    [forward.name]: { main: [[{ node: respond.name, type: 'main', index: 0 }]] },
  } };
}
const main = ingressWorkflow('finance-investment-recommendation-v1', 'Finance Investment Recommendation v1', 'internal/finance/investments/recommendations/v1', '/accept');
const health = ingressWorkflow('finance-signed-health-v1', 'Finance Signed Health v1', 'internal/finance/health/v1', '/signed-health');
const timer = { id: 'finance-maintenance-timer', name: 'Каждую минуту', type: 'n8n-nodes-base.scheduleTrigger', typeVersion: 1.2, position: [0, 0], parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 1 }] } } };
const drain = httpNode('Обработать очередь gateway', '/drain', [260, 0]);
const prune = httpNode('Удалить истёкшие данные', '/prune', [520, 0]);
const maintenance = { id: 'finance-metadata-retention-v1', name: 'Finance Queue and Retention v1', active: false, settings, nodes: [timer, drain, prune], connections: {
  [timer.name]: { main: [[{ node: drain.name, type: 'main', index: 0 }]] },
  [drain.name]: { main: [[{ node: prune.name, type: 'main', index: 0 }]] },
} };
await mkdir(join(root, 'workflows'), { recursive: true });
for (const workflow of [main, health, maintenance]) {
  await writeFile(join(root, 'workflows', `${workflow.id}.json`), `${JSON.stringify(workflow, null, 2)}\n`, 'utf8');
}
