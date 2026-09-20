import crypto from 'node:crypto';
import { verifyInboundSignature, validateJobEnvelope } from './core.mjs';
import { fail, GatewayError } from './network.mjs';

export const INGRESS_PATH = '/webhook/internal/finance/investments/recommendations/v1';
export const HEALTH_PATH = '/webhook/internal/finance/health/v1';
export function serviceAuth(headers, expected) {
  const received = headers['x-finance-gateway-token'];
  if (typeof received !== 'string' || !expected || expected.length < 32) fail('UNAUTHORIZED', 401);
  const a = crypto.createHash('sha256').update(received).digest();
  const b = crypto.createHash('sha256').update(expected).digest();
  if (!crypto.timingSafeEqual(a, b)) fail('UNAUTHORIZED', 401);
}
export async function accept(raw, headers, config, store, { health = false, nowEpoch } = {}) {
  serviceAuth(headers, config.gatewayToken);
  if (!Buffer.isBuffer(raw) || raw.length > 262144) fail('BODY_TOO_LARGE', 413);
  let verification;
  try {
    verification = verifyInboundSignature({ headers, body: raw, secret: config.ingressSecret,
      path: health ? HEALTH_PATH : INGRESS_PATH, nowEpoch });
  } catch { fail('INVALID_SIGNATURE', 401); }
  let job;
  // Authentication precedes parsing, validation and any database mutation.
  try {
    job = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw));
    if (health) {
      if (!job || Array.isArray(job) || Object.keys(job).length) fail('INVALID_HEALTH');
      await store.ping();
      return { status: 200, body: { status: 'ok' } };
    }
    validateJobEnvelope(job, nowEpoch ? new Date(nowEpoch * 1000) : new Date());
  } catch (error) {
    if (error instanceof GatewayError) throw error;
    fail('INVALID_CONTRACT');
  }
  const claim = await store.claim(job, verification.payloadHash, verification.nonce);
  // claim() commits encrypted queue data before resolving; no early acknowledgement.
  return { status: 202, body: { accepted: true, duplicate: claim.duplicate, eventId: job.eventId } };
}
