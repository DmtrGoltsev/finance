import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
const dir = new URL('../workflows/', import.meta.url);
const files = (await readdir(dir)).filter((f) => f.endsWith('.json'));
assert.equal(files.length, 3);
const ids = new Set();
for (const file of files) {
  const raw = await readFile(new URL(file, dir), 'utf8');
  const workflow = JSON.parse(raw);
  assert.ok(workflow.id && !ids.has(workflow.id)); ids.add(workflow.id);
  assert.equal(workflow.active, false);
  assert.equal(workflow.settings.saveDataSuccessExecution, 'none');
  assert.equal(workflow.settings.saveDataErrorExecution, 'none');
  assert.equal(workflow.settings.saveManualExecutions, false);
  assert.doesNotMatch(raw, /\$env|\bfetch\(|\bURL\(|onReceived|n8n-nodes-base.code/);
  const names = new Set(workflow.nodes.map((n) => n.name));
  for (const [name, links] of Object.entries(workflow.connections)) {
    assert.ok(names.has(name));
    for (const link of links.main.flat()) assert.ok(names.has(link.node));
  }
  for (const node of workflow.nodes) {
    if (node.type === 'n8n-nodes-base.httpRequest') {
      assert.match(node.parameters.url, /^http:\/\/(analysis-gateway|127\.0\.0\.1):8080\/(accept|signed-health|drain|prune)$/);
      assert.equal(node.parameters.options.redirect.redirect.followRedirects, false);
    }
    if (node.type === 'n8n-nodes-base.webhook') {
      assert.equal(node.parameters.responseMode, 'responseNode');
      const forward = workflow.nodes.find((n) => n.type === 'n8n-nodes-base.httpRequest');
      const response = workflow.nodes.find((n) => n.type === 'n8n-nodes-base.respondToWebhook');
      assert.equal(forward.parameters.contentType, 'binaryData');
      assert.equal(forward.parameters.inputDataFieldName, 'data');
      assert.equal(response.parameters.options.responseCode, '={{ $json.statusCode }}');
      assert.equal(workflow.connections[node.name].main[0][0].node, forward.name);
      assert.equal(workflow.connections[forward.name].main[0][0].node, response.name);
    }
  }
}
console.log('3 thin workflows PASS: stable IDs, raw bytes, gateway acceptance before response, no Code nodes.');
