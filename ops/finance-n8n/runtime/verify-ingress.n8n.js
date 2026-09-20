const item = $input.first().json;
const path = '/webhook/internal/finance/investments/recommendations/v1';
const body = typeof item.body === 'string' ? JSON.parse(item.body) : item.body;
const verification = verifyInboundSignature({
  headers: item.headers,
  body,
  secret: $env.FINANCE_INGRESS_HMAC_SECRET,
  path,
});
const job = validateJobEnvelope(body);
return [{ json: {
  event_id: job.eventId,
  job_id: job.jobId,
  attempt: job.attempt,
  payload_hash: verification.payloadHash,
  job_json: JSON.stringify(job),
} }];
