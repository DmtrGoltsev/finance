import crypto from 'node:crypto';

const MAX_CLOCK_SKEW_SECONDS = 300;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SECID_RE = /^[A-Z0-9][A-Z0-9._-]{0,31}$/;
const ISIN_RE = /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/;
const MONEY_RE = /^\d+(?:\.\d{1,4})?$/;
const RISK_BUCKETS = ['conservative', 'moderate', 'aggressive'];

function exactKeys(value, required, optional = []) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('INVALID_OBJECT');
  }
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) throw new Error(`UNEXPECTED_FIELD:${key}`);
  }
  for (const key of required) {
    if (!(key in value)) throw new Error(`MISSING_FIELD:${key}`);
  }
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function hmacSignature({ secret, method, path, timestamp, nonce, body }) {
  const prefix = Buffer.from([method.toUpperCase(), path, String(timestamp), nonce, ''].join('\n'));
  const canonical = Buffer.concat([prefix, Buffer.isBuffer(body) ? body : Buffer.from(body)]);
  return crypto.createHmac('sha256', secret).update(canonical).digest('hex');
}

function safeEqualHex(left, right) {
  if (!/^[0-9a-f]{64}$/i.test(left || '') || !/^[0-9a-f]{64}$/i.test(right || '')) return false;
  return crypto.timingSafeEqual(Buffer.from(left, 'hex'), Buffer.from(right, 'hex'));
}

function normalizedHeaders(headers) {
  return Object.fromEntries(Object.entries(headers || {}).map(([key, value]) => [key.toLowerCase(), String(value)]));
}

function verifyInboundSignature({ headers, body, secret, path, nowEpoch = Math.floor(Date.now() / 1000) }) {
  if (!secret || secret.length < 32) throw new Error('INGRESS_SECRET_NOT_CONFIGURED');
  const normalized = normalizedHeaders(headers);
  const timestampText = normalized['x-finance-timestamp'];
  const nonce = normalized['x-finance-nonce'];
  const signature = normalized['x-finance-signature'];
  if (!/^\d{10}$/.test(timestampText || '')) throw new Error('INVALID_TIMESTAMP');
  if (!/^[A-Za-z0-9_-]{16,128}$/.test(nonce || '')) throw new Error('INVALID_NONCE');
  const timestamp = Number(timestampText);
  if (Math.abs(nowEpoch - timestamp) > MAX_CLOCK_SKEW_SECONDS) throw new Error('STALE_SIGNATURE');
  if (!Buffer.isBuffer(body)) throw new Error('RAW_BODY_REQUIRED');
  const canonicalBody = body;
  const expected = hmacSignature({ secret, method: 'POST', path, timestamp, nonce, body: canonicalBody });
  if (!safeEqualHex(expected, signature)) throw new Error('INVALID_SIGNATURE');
  return { timestamp, nonce, canonicalBody, payloadHash: sha256(canonicalBody) };
}

function assertNoSensitivePayload(value, path = '$') {
  const forbiddenKeys = new Set([
    'email', 'phone', 'fullName', 'ownerUserId', 'userId', 'accountNumber', 'brokerAccountId',
    'screenshot', 'screenshots', 'image', 'binary', 'base64', 'url', 'callbackUrl', 'webhookUrl',
  ]);
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoSensitivePayload(item, `${path}[${index}]`));
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, item] of Object.entries(value)) {
    if (forbiddenKeys.has(key)) throw new Error(`SENSITIVE_FIELD:${path}.${key}`);
    if (typeof item === 'string' && /^https?:\/\//i.test(item)) throw new Error(`PAYLOAD_URL_FORBIDDEN:${path}.${key}`);
    assertNoSensitivePayload(item, `${path}.${key}`);
  }
}

function assertMoney(value, field) {
  if (typeof value !== 'string' || value.length > 24 || !MONEY_RE.test(value) || Number(value) > 1e12) throw new Error(`INVALID_MONEY:${field}`);
}

function validateAnalysisPackage(pkg) {
  exactKeys(pkg, ['schemaVersion', 'currency', 'market', 'policy', 'freeCash', 'monthlyContribution', 'positions', 'constraints']);
  if (pkg.schemaVersion !== 1 || pkg.currency !== 'RUB' || pkg.market !== 'RU') throw new Error('INVALID_ANALYSIS_SCOPE');
  exactKeys(pkg.policy, ['conservativePercent', 'moderatePercent', 'aggressivePercent', 'tolerancePercent']);
  for (const value of Object.values(pkg.policy)) assertMoney(value, 'policy');
  const allocation = ['conservativePercent', 'moderatePercent', 'aggressivePercent'].map((key) => Number(pkg.policy[key]));
  if (allocation.some((value) => !Number.isFinite(value) || value < 0) || Math.abs(allocation.reduce((a, b) => a + b, 0) - 100) > 0.0001) throw new Error('INVALID_POLICY');
  const tolerance = Number(pkg.policy.tolerancePercent);
  if (!Number.isFinite(tolerance) || tolerance < 0 || tolerance > 25) throw new Error('INVALID_TOLERANCE');
  assertMoney(pkg.freeCash, 'freeCash');
  assertMoney(pkg.monthlyContribution, 'monthlyContribution');
  if (!Array.isArray(pkg.positions) || pkg.positions.length < 1 || pkg.positions.length > 500) throw new Error('INVALID_POSITIONS');
  const positionKeys = ['secid', 'isin', 'instrumentType', 'riskBucket', 'quantity', 'marketValue', 'averagePrice', 'nominal', 'accruedInterest', 'couponRate', 'maturityDate', 'taxAccountType', 'holdingStartedAt', 'estimatedFeeRate'];
  for (const position of pkg.positions) {
    exactKeys(position, positionKeys);
    if (!SECID_RE.test(position.secid) || !ISIN_RE.test(position.isin)) throw new Error('INVALID_INSTRUMENT_ID');
    if (!['stock', 'bond', 'fund'].includes(position.instrumentType) || !RISK_BUCKETS.includes(position.riskBucket)) throw new Error('INVALID_INSTRUMENT_CLASS');
    assertMoney(position.quantity, 'quantity');
    assertMoney(position.marketValue, 'marketValue');
    for (const key of ['averagePrice', 'nominal', 'accruedInterest', 'couponRate', 'estimatedFeeRate']) {
      if (position[key] !== null) assertMoney(position[key], key);
    }
    if (!['brokerage', 'iis_a', 'iis_b', 'iis_iii'].includes(position.taxAccountType)) throw new Error('INVALID_TAX_ACCOUNT');
    for (const key of ['maturityDate', 'holdingStartedAt']) {
      if (position[key] !== null && (typeof position[key] !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(position[key]) || !Number.isFinite(Date.parse(position[key])))) throw new Error('INVALID_DATE');
    }
  }
  exactKeys(pkg.constraints, ['cashFirst', 'automaticExecution', 'marketDataMaxAgeHours', 'recommendationValidityDays', 'allowedSources']);
  if (pkg.constraints.cashFirst !== true || pkg.constraints.automaticExecution !== false || pkg.constraints.marketDataMaxAgeHours !== 24 || pkg.constraints.recommendationValidityDays !== 7) throw new Error('INVALID_CONSTRAINTS');
  const sourceNames = new Set(['moex.com', 'cbr.ru', 'minfin.gov.ru', 'nalog.gov.ru', 'e-disclosure.ru', 'interfax.ru', 'tass.ru', 'rbc.ru', 'issuer-official-sites']);
  if (!Array.isArray(pkg.constraints.allowedSources) || !pkg.constraints.allowedSources.length || pkg.constraints.allowedSources.some((name) => !sourceNames.has(name))) throw new Error('INVALID_SOURCE_SCOPE');
  assertNoSensitivePayload(pkg);
}

function validateJobEnvelope(envelope, now = new Date()) {
  exactKeys(envelope, ['schemaVersion', 'eventId', 'jobId', 'attempt', 'createdAt', 'analysisPackage']);
  if (envelope.schemaVersion !== 1 || !UUID_RE.test(envelope.eventId) || !UUID_RE.test(envelope.jobId)) throw new Error('INVALID_JOB_ID');
  if (!Number.isInteger(envelope.attempt) || envelope.attempt < 1 || envelope.attempt > 3) throw new Error('INVALID_ATTEMPT');
  const createdAt = new Date(envelope.createdAt);
  // Event creation is immutable on redelivery; freshness/replay protection uses signed timestamp + nonce.
  if (!Number.isFinite(createdAt.getTime()) || createdAt > new Date(now.getTime() + 5 * 60 * 1000)) throw new Error('STALE_JOB');
  validateAnalysisPackage(envelope.analysisPackage);
  return envelope;
}

function validateModelRecommendation(value, allowedInstruments, expectedAdjustments) {
  exactKeys(value, ['summary', 'assumptions', 'aggregates', 'actions']);
  if (typeof value.summary !== 'string' || value.summary.length < 1 || value.summary.length > 5000) throw new Error('INVALID_SUMMARY');
  if (!value.assumptions || typeof value.assumptions !== 'object' || Array.isArray(value.assumptions)) throw new Error('INVALID_ASSUMPTIONS');
  if (!Array.isArray(value.aggregates) || value.aggregates.length !== 3 || !Array.isArray(value.actions) || value.actions.length > 200) throw new Error('INVALID_RECOMMENDATION_SHAPE');
  const expectedByBucket = new Map(expectedAdjustments.map((item) => [item.riskBucket, item]));
  for (const aggregate of value.aggregates) {
    exactKeys(aggregate, ['riskBucket', 'currentPercent', 'proposedPercent']);
    const expected = expectedByBucket.get(aggregate.riskBucket);
    if (!expected || Math.abs(Number(aggregate.currentPercent) - expected.currentPercent) > 0.0001 || Math.abs(Number(aggregate.proposedPercent) - expected.projectedPercent) > 0.0001) throw new Error('AGGREGATE_MISMATCH');
  }
  const additions = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, 0]));
  const reductions = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, 0]));
  for (const action of value.actions) {
    exactKeys(action, ['instrumentName', 'ticker', 'isin', 'riskBucket', 'action', 'currentPercent', 'targetPercent', 'amount', 'priority', 'rationale', 'risks']);
    if (!SECID_RE.test(action.ticker) || !ISIN_RE.test(action.isin) || !allowedInstruments.has(`${action.ticker}|${action.isin}`)) throw new Error('UNVERIFIED_ACTION_INSTRUMENT');
    if (!RISK_BUCKETS.includes(action.riskBucket) || !['keep', 'reduce', 'increase', 'add'].includes(action.action)) throw new Error('INVALID_ACTION');
    if (!Number.isInteger(action.priority) || action.priority < 1 || action.priority > 100 || typeof action.rationale !== 'string' || typeof action.risks !== 'string') throw new Error('INVALID_ACTION_DETAILS');
    assertMoney(String(action.amount), 'action.amount');
    const amount = Number(action.amount);
    if (action.action === 'reduce') reductions[action.riskBucket] += amount;
    if (action.action === 'increase' || action.action === 'add') additions[action.riskBucket] += amount;
    if (action.action === 'keep' && amount !== 0) throw new Error('KEEP_AMOUNT_MUST_BE_ZERO');
  }
  for (const expected of expectedAdjustments) {
    if (Math.abs(additions[expected.riskBucket] - expected.addAmount) > 0.0001 || Math.abs(reductions[expected.riskBucket] - expected.reduceAmount) > 0.0001) throw new Error('ACTION_TOTAL_MISMATCH');
  }
  return value;
}

function round4(value) { return Math.round((value + Number.EPSILON) * 10000) / 10000; }

function cashFirstAdjustments(pkg) {
  const current = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, 0]));
  for (const position of pkg.positions) current[position.riskBucket] += Number(position.marketValue);
  const invested = Object.values(current).reduce((a, b) => a + b, 0);
  let cash = Math.max(0, Number(pkg.freeCash)) + Math.max(0, Number(pkg.monthlyContribution));
  const total = invested + cash;
  const targets = {
    conservative: Number(pkg.policy.conservativePercent),
    moderate: Number(pkg.policy.moderatePercent),
    aggressive: Number(pkg.policy.aggressivePercent),
  };
  const tolerance = Number(pkg.policy.tolerancePercent);
  if (total <= 0) return RISK_BUCKETS.map((riskBucket) => ({ riskBucket, addAmount: 0, reduceAmount: 0, currentPercent: 0, projectedPercent: 0, targetPercent: targets[riskBucket] }));
  const targetAmounts = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, round4(total * targets[bucket] / 100)]));
  const additions = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, 0]));
  const reductions = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, 0]));
  const projected = { ...current };
  for (const bucket of RISK_BUCKETS) {
    const addition = Math.min(Math.max(0, targetAmounts[bucket] - current[bucket]), cash);
    additions[bucket] = round4(addition); projected[bucket] += addition; cash -= addition;
  }
  if (cash > 0) { additions.conservative = round4(additions.conservative + cash); projected.conservative += cash; cash = 0; }
  const deficits = Object.fromEntries(RISK_BUCKETS.map((bucket) => [bucket, Math.max(0, targetAmounts[bucket] - projected[bucket])]));
  let totalDeficit = Object.values(deficits).reduce((a, b) => a + b, 0);
  if (totalDeficit > 0) {
    for (const source of RISK_BUCKETS) {
      let reduction = Math.min(Math.max(0, projected[source] - total * (targets[source] + tolerance) / 100), totalDeficit);
      if (reduction <= 0) continue;
      reductions[source] = round4(reduction); projected[source] -= reduction; totalDeficit -= reduction;
      for (const destination of RISK_BUCKETS) {
        const moved = Math.min(deficits[destination], reduction);
        if (moved <= 0) continue;
        additions[destination] = round4(additions[destination] + moved); projected[destination] += moved; deficits[destination] -= moved; reduction -= moved;
      }
    }
  }
  return RISK_BUCKETS.map((riskBucket) => ({
    riskBucket,
    addAmount: round4(additions[riskBucket]),
    reduceAmount: round4(reductions[riskBucket]),
    currentPercent: invested > 0 ? round4(current[riskBucket] * 100 / invested) : 0,
    projectedPercent: round4(projected[riskBucket] * 100 / total),
    targetPercent: targets[riskBucket],
  }));
}

function extractProviderJson(response) {
  if (typeof response.output_text === 'string') return JSON.parse(response.output_text);
  const outputText = Array.isArray(response.output)
    ? response.output.flatMap((item) => item.content || []).find((item) => item.type === 'output_text')?.text
    : null;
  if (typeof outputText === 'string') return JSON.parse(outputText);
  const chatText = response.choices?.[0]?.message?.content;
  if (typeof chatText === 'string') return JSON.parse(chatText);
  throw new Error('INVALID_LLM_JSON');
}

export { sha256, hmacSignature, verifyInboundSignature, validateJobEnvelope,
  validateAnalysisPackage, cashFirstAdjustments, validateModelRecommendation, extractProviderJson };
