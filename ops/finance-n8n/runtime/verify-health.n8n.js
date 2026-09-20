const item = $input.first().json;
const path = '/webhook/internal/finance/health/v1';
verifyInboundSignature({
  headers: item.headers,
  body: {},
  secret: $env.FINANCE_INGRESS_HMAC_SECRET,
  path,
});
return [{ json: { status: 'ok', service: 'finance-n8n', version: 1 } }];
