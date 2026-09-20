import http from 'node:http';
import { pathToFileURL } from 'node:url';
import { accept, serviceAuth } from './ingress.mjs';
import { Store } from './store.mjs';
import { drain } from './analysis.mjs';
import { GatewayError, fail } from './network.mjs';

export function readConfig(env = process.env) {
  const config = {
    ingressSecret: env.FINANCE_INGRESS_HMAC_SECRET, callbackSecret: env.FINANCE_CALLBACK_HMAC_SECRET,
    gatewayToken: env.FINANCE_GATEWAY_TOKEN, queueKey: env.FINANCE_GATEWAY_QUEUE_KEY,
    providerKey: env.DEEPSEEK_API_KEY, model: env.DEEPSEEK_MODEL,
    apiPrefix: env.FINANCE_BACKEND_API_PREFIX || '/api/v1',
    db: env.FINANCE_GATEWAY_DB, dbUser: env.FINANCE_GATEWAY_DB_USER, dbPassword: env.FINANCE_GATEWAY_DB_PASSWORD,
  };
  if ([config.ingressSecret, config.callbackSecret, config.gatewayToken].some((s) => typeof s !== 'string' || s.length < 32)) fail('SECRET_NOT_CONFIGURED', 503);
  if (new Set([config.ingressSecret, config.callbackSecret, config.gatewayToken]).size !== 3) fail('SECRETS_MUST_DIFFER', 503);
  if ([config.ingressSecret, config.callbackSecret, config.gatewayToken, config.providerKey, config.dbPassword].some((v) => !v || v.startsWith('replace-with')) || /^0+$/.test(config.queueKey || '')) fail('PLACEHOLDER_CONFIGURATION', 503);
  if (!config.providerKey || !/^[A-Za-z0-9._-]{1,80}$/.test(config.model || '') || !/^\/api\/v\d+$/.test(config.apiPrefix)) fail('INVALID_CONFIGURATION', 503);
  return config;
}
async function rawBody(req) {
  if (req.headers['content-encoding']) fail('ENCODING_FORBIDDEN', 415);
  if (Number(req.headers['content-length'] || 0) > 262144) fail('BODY_TOO_LARGE', 413);
  const chunks = []; let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 262144) fail('BODY_TOO_LARGE', 413);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}
export function createServer(config, store, worker = drain) {
  let draining = false;
  const server = http.createServer(async (req, res) => {
    function send(status, body) {
      res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify(body));
    }
    try {
      if (req.method === 'GET' && req.url === '/healthz') { await store.ping(); send(200, { status: 'ok' }); return; }
      if (req.method !== 'POST') fail('NOT_FOUND', 404);
      serviceAuth(req.headers, config.gatewayToken);
      if (req.url === '/accept' || req.url === '/signed-health') {
        const result = await accept(await rawBody(req), req.headers, config, store, { health: req.url === '/signed-health' });
        send(result.status, result.body); return;
      }
      if (req.url === '/drain') {
        if (draining) { send(200, { processed: 0, busy: true }); return; }
        draining = true;
        try { send(200, await worker(store, config)); }
        finally { draining = false; }
        return;
      }
      if (req.url === '/prune') { await store.prune(); send(200, { pruned: true }); return; }
      fail('NOT_FOUND', 404);
    } catch (error) {
      // Never serialize exceptions, payloads, model output, request headers or URLs.
      send(error instanceof GatewayError ? error.status : 503,
        { error: error instanceof GatewayError ? error.code : 'GATEWAY_UNAVAILABLE' });
    }
  });
  server.requestTimeout = 15000;
  server.headersTimeout = 10000;
  server.keepAliveTimeout = 5000;
  return server;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const config = readConfig();
    const store = new Store(config);
    await store.ping();
    const server = createServer(config, store).listen(8080, '0.0.0.0');
    const stop = () => server.close(() => store.close().then(() => process.exit(0)));
    process.on('SIGTERM', stop); process.on('SIGINT', stop);
  } catch {
    process.stderr.write('GATEWAY_START_FAILED\n'); process.exitCode = 1;
  }
}
