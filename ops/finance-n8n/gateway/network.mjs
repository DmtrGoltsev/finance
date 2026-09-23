import dns from 'node:dns/promises';
import https from 'node:https';
import http from 'node:http';
import tls from 'node:tls';
import ipaddr from 'ipaddr.js';

export class GatewayError extends Error {
  constructor(code, status = 422, retryable = false) {
    super(code); this.code = code; this.status = status; this.retryable = retryable;
  }
}
export const fail = (code, status = 422) => { throw new GatewayError(code, status); };
const officialPaths = {
  'www.cbr.ru': ['/hd_base/KeyRate/'],
  'minfin.gov.ru': ['/ru/perfomance/public_debt/internal/'],
  'www.nalog.gov.ru': ['/rn77/taxation/taxes/ndfl/nalog_vichet/inv_vichet/'],
};

export function allowedUrl(raw, provider = false) {
  let url;
  try { url = new URL(raw); } catch { fail('UNSAFE_URL'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.port || url.hash) fail('UNSAFE_URL');
  const allowed = provider
    ? url.hostname === 'api.deepseek.com' && url.pathname === '/responses' && !url.search
    : (url.hostname === 'iss.moex.com' && /^\/iss\/(engines\/stock\/markets\/(shares|bonds)\/boards\/(TQBR|TQTF|TQOB)\/securities(?:\/[A-Z0-9._-]{1,32})?\.json|securities\/[A-Z0-9._-]{1,32}\.json)$/.test(url.pathname)) ||
      (officialPaths[url.hostname]?.includes(url.pathname) && !url.search);
  if (!allowed) fail('SOURCE_NOT_ALLOWED');
  return url;
}

export function publicAddress(address) {
  try {
    const parsed = ipaddr.parse(address);
    // Reject mapped IPv4 and transition networks as well as local/reserved ranges.
    return parsed.range() === 'unicast';
  } catch { return false; }
}

export async function pinnedOptions(url, resolve = dns.lookup) {
  let timer;
  let addresses;
  try {
    addresses = await Promise.race([
      resolve(url.hostname, { all: true, verbatim: true }),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new GatewayError('DNS_TIMEOUT', 504, true)), 10000); }),
    ]);
  } finally { clearTimeout(timer); }
  if (!addresses.length || addresses.some(({ address }) => !publicAddress(address))) fail('DNS_NOT_PUBLIC');
  const pin = addresses[0];
  return {
    hostname: url.hostname, port: 443, path: url.pathname + url.search,
    servername: url.hostname, rejectUnauthorized: true, agent: false,
    checkServerIdentity: tls.checkServerIdentity,
    lookup: (_host, options, callback) => {
      if (typeof options === 'function') { callback = options; options = {}; }
      // No second DNS resolution: connection and TLS use this validated address.
      callback(null, options?.all ? [pin] : pin.address, pin.family);
    },
  };
}

export async function retry3(operation, sleep = (ms) => new Promise((r) => setTimeout(r, ms))) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try { return await operation(attempt); }
    catch (error) {
      if (!error.retryable || attempt === 3) throw error;
      await sleep(attempt * 250);
    }
  }
}

export function requestBytes(options, body = null, { request = https.request, timeout = 10000, maxBytes = 1048576 } = {}) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    const req = request(options, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400) {
        res.destroy(); reject(new GatewayError('REDIRECT_FORBIDDEN')); return;
      }
      if (res.statusCode < 200 || res.statusCode >= 300) {
        res.destroy(); reject(new GatewayError('UPSTREAM_HTTP', 502, res.statusCode === 429 || res.statusCode >= 500)); return;
      }
      if (Number(res.headers['content-length'] || 0) > maxBytes) {
        res.destroy(); reject(new GatewayError('RESPONSE_TOO_LARGE')); return;
      }
      res.on('data', (chunk) => {
        size += chunk.length;
        if (size > maxBytes) { res.destroy(); reject(new GatewayError('RESPONSE_TOO_LARGE')); }
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new GatewayError('NETWORK_ERROR', 502, true)));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    });
    const timer = setTimeout(() => req.destroy(new GatewayError('UPSTREAM_TIMEOUT', 504, true)), timeout);
    req.on('close', () => clearTimeout(timer));
    req.on('error', (error) => reject(error instanceof GatewayError ? error : new GatewayError('NETWORK_ERROR', 502, true)));
    req.end(body);
  });
}

export async function externalRequest(raw, { provider = false, body = null, key = null, resolve, transport = requestBytes } = {}) {
  const url = allowedUrl(raw, provider);
  return retry3(async () => {
    const options = await pinnedOptions(url, resolve);
    options.method = body === null ? 'GET' : 'POST';
    options.headers = { accept: 'application/json', 'user-agent': 'FinanceAnalysisGateway/1' };
    if (body !== null) options.headers['content-type'] = 'application/json';
    if (key) options.headers.authorization = `Bearer ${key}`;
    return transport(options, body, { timeout: provider ? 90000 : 10000 });
  });
}

export async function internalCallback(path, body, headers, transport = requestBytes) {
  if (!/^\/api\/v[0-9]+\/investments\/internal\/recommendation-jobs\/[0-9a-f-]{36}\/callback$/.test(path)) fail('INVALID_CALLBACK_PATH');
  // The sole deliberate private destination is configuration-fixed, never model-selected.
  const native = process.env.FINANCE_GATEWAY_HOST_MODE === 'native';
  const port = native ? 8081 : Number(process.env.FINANCE_CALLBACK_PROXY_PORT);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) fail('CALLBACK_PROXY_PORT_INVALID', 503);
  return transport({ hostname: native ? '127.0.0.1' : 'finance-host-callback', port, path, method: 'POST', agent: false, headers }, body, { request: http.request });
}
