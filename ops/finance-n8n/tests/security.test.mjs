import assert from 'node:assert/strict';
import test from 'node:test';
import { loadSecurityCore, validEnvelope } from './helpers.mjs';

test('HMAC accepts canonical valid request and rejects replay window/signature', async () => {
  const core = await loadSecurityCore();
  const body = validEnvelope();
  const secret = 'a'.repeat(64);
  const timestamp = Math.floor(Date.now() / 1000);
  const nonce = 'nonce-value-1234567890';
  const path = '/webhook/internal/finance/investments/recommendations/v1';
  const signature = core.hmacSignature({ secret, method: 'POST', path, timestamp, nonce, body: core.canonicalJson(body) });
  const headers = { 'X-Finance-Timestamp': timestamp, 'X-Finance-Nonce': nonce, 'X-Finance-Signature': signature };
  assert.equal(core.verifyInboundSignature({ headers, body, secret, path }).payloadHash.length, 64);
  assert.throws(() => core.verifyInboundSignature({ headers: { ...headers, 'X-Finance-Signature': '0'.repeat(64) }, body, secret, path }), /INVALID_SIGNATURE/);
  assert.throws(() => core.verifyInboundSignature({ headers, body, secret, path, nowEpoch: timestamp + 301 }), /STALE_SIGNATURE/);
});

test('ingress rejects screenshots, URLs and stale jobs', async () => {
  const core = await loadSecurityCore();
  const screenshot = validEnvelope();
  screenshot.analysisPackage.screenshot = 'base64';
  assert.throws(() => core.validateJobEnvelope(screenshot), /UNEXPECTED_FIELD|SENSITIVE_FIELD/);
  const url = validEnvelope();
  url.analysisPackage.positions[0].averagePrice = 'https://127.0.0.1/secret';
  assert.throws(() => core.validateJobEnvelope(url), /INVALID_MONEY|PAYLOAD_URL_FORBIDDEN/);
  const stale = validEnvelope(new Date(Date.now() - 25 * 60 * 60 * 1000));
  assert.throws(() => core.validateJobEnvelope(stale), /STALE_JOB/);
});

test('source allowlist blocks private, redirect and unlicensed news access', async () => {
  const core = await loadSecurityCore();
  assert.match(core.assertAllowedSourceUrl('https://iss.moex.com/iss/index.json'), /^https:/);
  assert.throws(() => core.assertAllowedSourceUrl('http://iss.moex.com/'), /UNSAFE_SOURCE_URL/);
  assert.throws(() => core.assertAllowedSourceUrl('https://127.0.0.1/'), /PRIVATE_SOURCE_FORBIDDEN/);
  assert.throws(() => core.assertAllowedSourceUrl('https://evil.example/'), /SOURCE_NOT_ALLOWLISTED/);
  assert.throws(() => core.assertAllowedSourceUrl('https://www.rbc.ru/'), /SOURCE_NOT_ALLOWLISTED/);
  let calls = 0;
  const redirecting = async () => ({ status: 302, ok: false, headers: new Map(), text: async () => '' });
  await assert.rejects(() => core.safeFetch('https://iss.moex.com/iss/index.json', {}, async (...args) => { calls += 1; return redirecting(...args); }), /REDIRECT_FORBIDDEN/);
  assert.equal(calls, 3);
});

test('invalid DeepSeek JSON and unverified action are rejected', async () => {
  const core = await loadSecurityCore();
  assert.throws(() => core.extractProviderJson({ output_text: '{broken' }), /JSON|property name|position/i);
  assert.throws(() => core.extractProviderJson({}), /INVALID_LLM_JSON/);
  const pkg = validEnvelope().analysisPackage;
  const expected = core.cashFirstAdjustments(pkg);
  const recommendation = {
    summary: 'Тест', assumptions: {},
    aggregates: expected.map((item) => ({ riskBucket: item.riskBucket, currentPercent: item.currentPercent, proposedPercent: item.projectedPercent })),
    actions: [{
      instrumentName: 'Подмена', ticker: 'EVIL', isin: 'RU0000000001', riskBucket: 'moderate', action: 'keep',
      currentPercent: 100, targetPercent: 100, amount: 0, priority: 1, rationale: 'x', risks: 'x',
    }],
  };
  assert.throws(() => core.validateModelRecommendation(recommendation, new Set(['SBER|RU0009029540']), expected), /UNVERIFIED_ACTION_INSTRUMENT/);
});
