import assert from 'node:assert/strict';
import test from 'node:test';
import { once, EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { hmacSignature, cashFirstAdjustments, validateJobEnvelope } from '../gateway/core.mjs';
import { accept, INGRESS_PATH } from '../gateway/ingress.mjs';
import { createServer } from '../gateway/server.mjs';
import { pinnedOptions, publicAddress, externalRequest, requestBytes, retry3, GatewayError, allowedUrl } from '../gateway/network.mjs';
import { moexTimestamp, collectMarket, drain, providerPayload, analyze } from '../gateway/analysis.mjs';
import { recommendationSchema, validateRecommendation } from '../gateway/schema.mjs';
import { cipher, Store } from '../gateway/store.mjs';
import { validEnvelope } from './helpers.mjs';

const config = { ingressSecret: 'a'.repeat(64), callbackSecret: 'b'.repeat(64), gatewayToken: 'c'.repeat(64),
  queueKey: 'd'.repeat(64), apiPrefix: '/api/v2', model: 'test-model', providerKey: 'test-provider' };
function headers(raw, nonce = 'abcdefghijklmnop1234') {
  const timestamp = Math.floor(Date.now() / 1000);
  return { 'x-finance-gateway-token': config.gatewayToken, 'x-finance-timestamp': String(timestamp),
    'x-finance-nonce': nonce, 'x-finance-signature': hmacSignature({ secret: config.ingressSecret, method: 'POST', path: INGRESS_PATH, timestamp, nonce, body: raw }) };
}
test('raw HMAC parity with backend sign_callback including Unicode and whitespace', () => {
  const raw = Buffer.from('{ "summary": "Тест", "n": 2 }\n');
  const values = { secret: 'test-hmac', method: 'POST', path: '/api/v2/investments/internal/recommendation-jobs/22222222-2222-4222-8222-222222222222/callback', timestamp: 1750000000, nonce: 'nonce-value-1234567890', body: raw };
  const modulePath = process.env.BACKEND_HMAC_MODULE;
  assert.ok(modulePath, 'Set BACKEND_HMAC_MODULE to actual backend investments/hmac_auth.py for parity evidence');
  const script = `import importlib.util,sys,base64,json\np=json.loads(sys.stdin.read())\ns=importlib.util.spec_from_file_location('finance_hmac',p.pop('module'))\nm=importlib.util.module_from_spec(s)\nsys.modules[s.name]=m\ns.loader.exec_module(m)\np['body']=base64.b64decode(p['body'])\nprint(m.sign_callback(**p))`;
  const result = spawnSync(process.env.PYTHON || 'python', ['-c', script], { encoding: 'utf8', input: JSON.stringify({ module: modulePath, secret: values.secret, method: values.method, canonical_path: values.path, timestamp: values.timestamp, nonce: values.nonce, body: raw.toString('base64') }) });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(hmacSignature(values), result.stdout.trim());
});
test('HMAC is checked before JSON parsing and contract before claim', async () => {
  let calls = 0;
  const store = { claim: async () => { calls++; } };
  const raw = Buffer.from('{invalid');
  await assert.rejects(accept(raw, { ...headers(raw), 'x-finance-signature': '0'.repeat(64) }, config, store), /INVALID_SIGNATURE/);
  await assert.rejects(accept(raw, headers(raw), config, store), /INVALID_CONTRACT/);
  assert.equal(calls, 0);
});
test('actual HTTP acknowledgement waits for durable claim commit', async (t) => {
  let finish;
  let entered;
  const enteredPromise = new Promise((r) => { entered = r; });
  const claimPromise = new Promise((r) => { finish = r; });
  const store = { claim: async () => { entered(); await claimPromise; return { duplicate: false }; } };
  const server = createServer(config, store).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  const raw = Buffer.from(JSON.stringify(validEnvelope()));
  let acknowledged = false;
  const pending = fetch(`http://127.0.0.1:${server.address().port}/accept`, { method: 'POST', headers: headers(raw), body: raw }).then((r) => { acknowledged = true; return r; });
  await enteredPromise;
  await new Promise((r) => setTimeout(r, 30));
  assert.equal(acknowledged, false);
  finish();
  const response = await pending;
  assert.equal(response.status, 202);
  assert.equal((await response.json()).accepted, true);
});
test('claim failure never produces success', async () => {
  const raw = Buffer.from(JSON.stringify(validEnvelope()));
  await assert.rejects(accept(raw, headers(raw), config, { claim: async () => { throw new Error('DB DOWN'); } }), /DB DOWN/);
});
test('acceptance rejects modified raw whitespace and expired signatures', async () => {
  const raw = Buffer.from(JSON.stringify(validEnvelope()));
  const store = { claim: async () => ({ duplicate: false }) };
  await assert.rejects(accept(Buffer.concat([raw, Buffer.from(' ')]), headers(raw), config, store), /INVALID_SIGNATURE/);
  await assert.rejects(accept(raw, headers(raw), config, store, { nowEpoch: Math.floor(Date.now() / 1000) + 301 }), /INVALID_SIGNATURE/);
});
function storeWithRows({ existing = [], previous = [], nonce = true } = {}) {
  const queries = [];
  const store = Object.create(Store.prototype); store.crypt = cipher(config.queueKey);
  const query = async (sql, params) => {
    queries.push([sql, params]);
    if (sql.startsWith('INSERT INTO gateway_nonces')) return { rowCount: nonce ? 1 : 0 };
    if (sql.startsWith('SELECT *')) return { rowCount: existing.length, rows: existing };
    if (sql.startsWith('SELECT state')) return { rows: previous };
    return { rowCount: 1, rows: [] };
  };
  store.pool = { connect: async () => ({ query, release() {} }) };
  return { store, queries };
}
test('DB claim commits before success; duplicate does not insert or reset queue', async () => {
  const job = validEnvelope();
  const first = storeWithRows();
  assert.deepEqual(await first.store.claim(job, 'h'.repeat(64), 'nonce'), { duplicate: false });
  assert.equal(first.queries.at(-1)[0], 'COMMIT');
  assert.ok(first.queries.some(([sql]) => sql.includes('pg_advisory_xact_lock')));
  const duplicate = storeWithRows({ existing: [{ event_id: job.eventId, job_id: job.jobId, attempt: 1, payload_hash: 'h'.repeat(64) }] });
  assert.deepEqual(await duplicate.store.claim(job, 'h'.repeat(64), 'fresh-nonce'), { duplicate: true });
  assert.equal(duplicate.queries.some(([sql]) => sql.startsWith('INSERT INTO gateway_runs')), false);
});
test('DB claim rejects nonce replay, conflicting event and fourth attempt', async () => {
  const job = validEnvelope();
  await assert.rejects(storeWithRows({ nonce: false }).store.claim(job, 'hash', 'nonce'), /NONCE_REPLAY/);
  await assert.rejects(storeWithRows({ existing: [{ event_id: job.eventId, payload_hash: 'other' }] }).store.claim(job, 'hash', 'nonce'), /IDEMPOTENCY_CONFLICT/);
  await assert.rejects(storeWithRows({ previous: [{ attempt: 3, state: 'failed' }] }).store.claim({ ...job, attempt: 4 }, 'hash', 'nonce'), /ATTEMPT_CONFLICT/);
  await assert.rejects(storeWithRows({ previous: [{ attempt: 1, state: 'ready' }] }).store.claim({ ...job, attempt: 2 }, 'hash', 'nonce'), /ATTEMPT_CONFLICT/);
  assert.deepEqual(await storeWithRows({ previous: [{ attempt: 1, state: 'failed' }] }).store.claim({ ...job, attempt: 2 }, 'hash', 'nonce'), { duplicate: false });
});

test('late lost-ACK retry keeps immutable event and never inserts a second generation', async () => {
  const job = validEnvelope();
  job.createdAt = '2020-01-01T00:00:00Z';
  assert.equal(validateJobEnvelope(job), job);
  for (const state of ['queued', 'running', 'ready', 'failed']) {
    const { store, queries } = storeWithRows({ existing: [{ event_id: job.eventId,
      job_id: job.jobId, attempt: job.attempt, payload_hash: 'stable-hash', state, payload: null, callback: null }] });
    assert.deepEqual(await store.claim(job, 'stable-hash', 'fresh-nonce'), { duplicate: true });
    assert.equal(queries.some(([sql]) => /INSERT INTO gateway_runs|UPDATE gateway_runs/.test(sql)), false);
  }
});

test('retry revives only encrypted saved callback; expired result never regenerates', async () => {
  const job = validEnvelope();
  const row = { event_id: job.eventId, job_id: job.jobId, attempt: job.attempt,
    payload_hash: 'stable-hash', state: 'delivery_failed', payload: Buffer.from('saved'), callback: Buffer.from('saved') };
  const { store, queries } = storeWithRows({ existing: [row] });
  assert.deepEqual(await store.claim(job, 'stable-hash', 'fresh-nonce'), { duplicate: true });
  assert.ok(queries.some(([sql]) => sql.includes("SET state='callback',callback_attempts=0")));
  assert.equal(queries.some(([sql]) => sql.includes("'queued'")), false);
  await assert.rejects(storeWithRows({ existing: [{ ...row, callback: null, payload: null }] }).store.claim(job, 'stable-hash', 'fresh-nonce'), /DELIVERY_RESULT_EXPIRED/);
});

test('retention clears content but keeps permanent dedup identities', async () => {
  const queries = [];
  const store = Object.create(Store.prototype);
  store.pool = { query: async (sql) => { queries.push(sql); } };
  await store.prune();
  assert.ok(queries.some((sql) => sql.startsWith('UPDATE gateway_runs SET payload=NULL,callback=NULL')));
  assert.equal(queries.some((sql) => /DELETE FROM gateway_runs|TRUNCATE/.test(sql)), false);
});
test('network retries at most three; permanent validation errors never retried', async () => {
  let attempts = 0;
  await assert.rejects(retry3(async () => { attempts++; throw new GatewayError('TEMPORARY', 502, true); }, async () => {}), /TEMPORARY/);
  assert.equal(attempts, 3);
  attempts = 0;
  await assert.rejects(retry3(async () => { attempts++; throw new GatewayError('PERMANENT'); }), /PERMANENT/);
  assert.equal(attempts, 1);
});
test('public-address guard rejects IPv4/IPv6 private, mapped, link-local, multicast, reserved', () => {
  for (const ip of ['127.0.0.1', '10.2.3.4', '172.16.1.1', '192.168.0.1', '169.254.169.254', '0.0.0.0', '100.64.0.1', '224.1.2.3', '::1', '::ffff:127.0.0.1', '::ffff:8.8.8.8', 'fe80::1', 'fc00::1', '2001:db8::1']) assert.equal(publicAddress(ip), false, ip);
  assert.equal(publicAddress('8.8.8.8'), true);
});
test('DNS validates every answer and pins the connection without second resolution', async () => {
  let calls = 0;
  const options = await pinnedOptions(new URL('https://iss.moex.com/iss/securities/SBER.json'), async () => {
    calls++; return calls === 1 ? [{ address: '8.8.8.8', family: 4 }] : [{ address: '127.0.0.1', family: 4 }];
  });
  assert.equal(options.servername, 'iss.moex.com');
  assert.equal(options.rejectUnauthorized, true);
  assert.equal(options.agent, false);
  const actual = await new Promise((resolve) => options.lookup('iss.moex.com', {}, (_, address) => resolve(address)));
  assert.equal(actual, '8.8.8.8'); assert.equal(calls, 1);
  await assert.rejects(pinnedOptions(new URL('https://iss.moex.com'), async () => [{ address: '8.8.8.8', family: 4 }, { address: '10.0.0.1', family: 4 }]), /DNS_NOT_PUBLIC/);
});
test('provider uses same DNS pinning and no uncontrolled source/URL', async () => {
  for (const url of ['https://127.0.0.1/', 'https://iss.moex.com.evil/a', 'https://iss.moex.com@evil/a', 'http://iss.moex.com/iss/securities/SBER.json', 'https://www.rbc.ru/', 'https://api.deepseek.com/evil']) assert.throws(() => allowedUrl(url), /UNSAFE_URL|SOURCE_NOT_ALLOWED/);
  let transportCalls = 0;
  await assert.rejects(externalRequest('https://api.deepseek.com/responses', { provider: true,
    resolve: async () => [{ address: '127.0.0.1', family: 4 }], transport: async () => { transportCalls++; } }), /DNS_NOT_PUBLIC/);
  assert.equal(transportCalls, 0);
});
function fakeRequest(response) {
  return (_options, onResponse) => {
    const req = new EventEmitter();
    req.end = () => { queueMicrotask(() => { onResponse(response); req.emit('close'); }); };
    req.destroy = (error) => { req.emit('error', error); req.emit('close'); };
    return req;
  };
}
test('redirects and oversized responses are rejected by transport itself', async () => {
  const redirect = new PassThrough(); redirect.statusCode = 302; redirect.headers = { location: 'http://127.0.0.1/' };
  await assert.rejects(requestBytes({}, null, { request: fakeRequest(redirect) }), /REDIRECT_FORBIDDEN/);
  const large = new PassThrough(); large.statusCode = 200; large.headers = { 'content-length': 1048577 };
  await assert.rejects(requestBytes({}, null, { request: fakeRequest(large) }), /RESPONSE_TOO_LARGE/);
});
test('MOEX timestamps use official date/time and never fetchedAt/now', () => {
  const now = Date.parse('2026-09-20T12:00:00Z');
  assert.equal(moexTimestamp({ SYSTIME: '2026-09-20 14:00:00' }, now), '2026-09-20T11:00:00.000Z');
  assert.equal(moexTimestamp({ TRADEDATE: '2026-09-20', UPDATETIME: '14:00:00' }, now), '2026-09-20T11:00:00.000Z');
  for (const row of [{}, { UPDATETIME: '14:00:00' }, { fetchedAt: new Date(now).toISOString() }]) assert.throws(() => moexTimestamp(row, now), /SOURCE_TIMESTAMP_MISSING/);
  assert.throws(() => moexTimestamp({ SYSTIME: '2026-09-18 14:00:00' }, now), /SOURCE_TIMESTAMP_STALE/);
  assert.throws(() => moexTimestamp({ SYSTIME: '2026-09-21 14:00:00' }, now), /SOURCE_TIMESTAMP_STALE/);
});
function marketDocument(timestamp) {
  return Buffer.from(JSON.stringify({ securities: { columns: ['SECID', 'ISIN', 'SHORTNAME'], data: [['SBER', 'RU0009029540', 'Сбер']] },
    marketdata: { columns: ['SECID', 'LAST', 'SYSTIME'], data: [['SBER', 300, timestamp]] } }));
}
test('market collector fails closed without fresh official timestamps', async () => {
  await assert.rejects(collectMarket(validEnvelope().analysisPackage, async () => marketDocument(null)), /INSTRUMENT_DATA_UNAVAILABLE/);
  await assert.rejects(collectMarket(validEnvelope().analysisPackage, async () => marketDocument('2020-01-01 10:00:00')), /INSTRUMENT_DATA_UNAVAILABLE/);
});
test('marketDataAsOf is from response and source timestamps distinguish fetch from publication', async () => {
  const now = Date.parse('2026-09-20T12:00:00Z');
  const result = await collectMarket(validEnvelope().analysisPackage, async (url) => url.includes('moex') ? marketDocument('2026-09-20 14:00:00') : Buffer.from('<html>Official context</html>'), () => now);
  assert.equal(result.marketDataAsOf, '2026-09-20T11:00:00.000Z');
  assert.equal(result.sources[0].publishedAt, result.marketDataAsOf);
  assert.equal(result.sources[0].fetchedAt, '2026-09-20T12:00:00.000Z');
});
function modelResult(pkg) {
  const expected = cashFirstAdjustments(pkg);
  return { summary: 'Тест', assumptions: { manualExecutionOnly: true, taxesAreEstimates: true, missingInformation: [], limitations: ['Нет налоговых лотов'] },
    aggregates: expected.map((r) => ({ riskBucket: r.riskBucket, currentPercent: r.currentPercent, proposedPercent: r.projectedPercent })), actions: [] };
}
test('DeepSeek schema closes every object including assumptions', () => {
  function walk(schema) {
    if (schema.type === 'object') {
      assert.equal(schema.additionalProperties, false);
      assert.deepEqual(schema.required.sort(), Object.keys(schema.properties).sort());
      Object.values(schema.properties).forEach(walk);
    }
    if (schema.items) walk(schema.items);
  }
  walk(recommendationSchema);
});
test('model wrong types, extra assumptions, duplicates and bad allocation are rejected', () => {
  const pkg = validEnvelope().analysisPackage;
  for (const mutate of [
    (r) => { r.assumptions.email = 'private@example.com'; },
    (r) => { r.aggregates[0].currentPercent = '40'; },
    (r) => { r.aggregates[1] = r.aggregates[0]; },
    (r) => { r.actions = []; },
  ]) {
    const value = modelResult(pkg); mutate(value);
    assert.throws(() => validateRecommendation(value, new Set(['SBER|RU0009029540']), cashFirstAdjustments(pkg)), /INVALID_MODEL/);
  }
});
test('invalid provider JSON fails analysis with safe error', async () => {
  const request = async (url) => {
    if (url.includes('deepseek')) return Buffer.from('{invalid');
    if (url.includes('moex')) return marketDocument(new Date(Date.now() - 60000).toISOString());
    return Buffer.from('<html>Official context</html>');
  };
  await assert.rejects(analyze(validEnvelope(), config, request), /INVALID_MODEL_JSON/);
});
test('successful analysis validates JSON and sends collecting/analyzing before terminal callback', async () => {
  const job = validEnvelope();
  const base = job.analysisPackage.positions[0];
  job.analysisPackage.freeCash = '0'; job.analysisPackage.monthlyContribution = '0';
  job.analysisPackage.positions = [
    { ...base, secid: 'LQDT', isin: 'RU000A1014L8', riskBucket: 'conservative', marketValue: '400' },
    { ...base, riskBucket: 'moderate', marketValue: '300' },
    { ...base, secid: 'GAZP', isin: 'RU0007661625', riskBucket: 'aggressive', marketValue: '300' },
  ];
  const readyModel = modelResult(job.analysisPackage);
  const states = []; let saved; let done;
  const request = async (url, options) => {
    if (url.includes('deepseek')) {
      assert.equal(JSON.parse(options.body).text.format.strict, true);
      return Buffer.from(JSON.stringify({ output_text: JSON.stringify(readyModel) }));
    }
    if (!url.includes('moex')) return Buffer.from('Official context');
    return Buffer.from(JSON.stringify({
      securities: { columns: ['SECID', 'ISIN', 'SHORTNAME'], data: job.analysisPackage.positions.map((p) => [p.secid, p.isin, p.secid]) },
      marketdata: { columns: ['SECID', 'LAST', 'SYSTIME'], data: job.analysisPackage.positions.map((p) => [p.secid, 100, new Date(Date.now() - 60000).toISOString()]) },
    }));
  };
  const store = { next: async () => ({ eventId: job.eventId, job, previous: 'queued' }),
    saveCallback: async (_, value) => { saved = value; }, callbackAttempt: async () => true,
    finish: async (_, state) => { done = state; }, deadLetter: async () => assert.fail('Unexpected delivery failure') };
  const result = await drain(store, config, {
    analysis: (j, c, _, progress) => analyze(j, c, request, progress),
    callback: async (path, body, signedHeaders) => {
      const value = JSON.parse(body); states.push(value.status);
      if (value.status === 'ready') assert.equal(saved.status, 'ready');
      assert.equal(signedHeaders['x-finance-signature'], hmacSignature({ secret: config.callbackSecret, method: 'POST', path,
        timestamp: signedHeaders['x-finance-timestamp'], nonce: signedHeaders['x-finance-nonce'], body }));
    },
  });
  assert.deepEqual(states, ['collecting', 'analyzing', 'ready']);
  assert.equal(done, 'ready'); assert.equal(result.state, 'ready');
});
test('resumed saved callback does not regenerate report or resend progress', async () => {
  const job = validEnvelope(); let attempts = 2; let done;
  const store = { next: async () => ({ eventId: job.eventId, job, previous: 'callback', callback: { status: 'ready' } }),
    callbackAttempt: async () => attempts < 3 ? (++attempts, true) : false,
    finish: async (_, state) => { done = state; }, deadLetter: async () => assert.fail('unexpected') };
  await drain(store, config, { analysis: async () => assert.fail('must not call model'), callback: async () => {} });
  assert.equal(attempts, 3); assert.equal(done, 'ready');
});
test('PII fields rejected and provider payload excludes job/account identity', () => {
  for (const field of ['email', 'ownerUserId', 'accountNumber', 'screenshot', 'callbackUrl']) {
    const job = validEnvelope(); job.analysisPackage[field] = 'PERSON 123';
    assert.throws(() => validateJobEnvelope(job));
  }
  const job = validEnvelope(); job.analysisPackage.positions[0].holdingStartedAt = 'PERSON 123';
  assert.throws(() => validateJobEnvelope(job));
  const payload = JSON.stringify(providerPayload(validEnvelope().analysisPackage, { universe: new Map(), documents: [] }, 'model'));
  for (const value of [validEnvelope().eventId, validEnvelope().jobId, 'screenshot', 'accountNumber']) assert.equal(payload.includes(value), false);
});
test('queue payload encrypted and tampering rejected', () => {
  const crypt = cipher(config.queueKey); const job = validEnvelope();
  const sealed = crypt.seal(job);
  assert.equal(sealed.includes(Buffer.from('SBER')), false);
  assert.deepEqual(crypt.open(sealed), job);
  sealed[30] ^= 1;
  assert.throws(() => crypt.open(sealed));
});
test('callback saved before delivery, max three attempts across resume, no repeated analysis', async () => {
  let attempts = 0; let analysisCalls = 0; let saved; let dead = false;
  const job = validEnvelope();
  const store = { next: async () => ({ eventId: job.eventId, job, previous: 'queued', callback: saved }),
    saveCallback: async (_, value) => { saved = value; }, callbackAttempt: async () => attempts < 3 ? (++attempts, true) : false,
    deadLetter: async () => { dead = true; }, finish: async () => assert.fail('Must not finish') };
  const work = { analysis: async () => { analysisCalls++; throw new Error('SENSITIVE SECRET'); }, callback: async (path, body) => {
    if (JSON.parse(body).status === 'collecting') return;
    assert.ok(saved); assert.match(path, /^\/api\/v2\//);
    assert.equal(body.includes(Buffer.from('SENSITIVE SECRET')), false);
    throw new GatewayError('NETWORK_ERROR', 502, true);
  } };
  await drain(store, config, work); await drain(store, config, work);
  assert.equal(attempts, 3); assert.equal(analysisCalls, 1); assert.equal(dead, true);
});
test('no request/model logging; safe HTTP failure body contains no PII', async (t) => {
  const server = createServer(config, { claim: async () => { throw new Error('PERSON 123 PASSWORD'); } }).listen(0, '127.0.0.1');
  await once(server, 'listening'); t.after(() => server.close());
  const raw = Buffer.from(JSON.stringify(validEnvelope()));
  const response = await fetch(`http://127.0.0.1:${server.address().port}/accept`, { method: 'POST', headers: headers(raw), body: raw });
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: 'GATEWAY_UNAVAILABLE' });
  for (const file of ['server', 'analysis', 'ingress', 'store', 'network']) {
    const source = await readFile(new URL(`../gateway/${file}.mjs`, import.meta.url), 'utf8');
    assert.doesNotMatch(source, /console\.(log|error)|JSON\.stringify\(error\)/);
  }
});
