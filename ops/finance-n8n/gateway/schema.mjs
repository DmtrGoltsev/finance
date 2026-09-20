import Ajv from 'ajv';
import { fail } from './network.mjs';
import { validateModelRecommendation } from './core.mjs';

const obj = (properties) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });
const text = (maxLength) => ({ type: 'string', minLength: 1, maxLength });
const bucket = { type: 'string', enum: ['conservative', 'moderate', 'aggressive'] };
const percent = { type: 'number', minimum: 0, maximum: 100 };
export const recommendationSchema = obj({
  summary: text(5000),
  assumptions: obj({
    manualExecutionOnly: { type: 'boolean', const: true },
    taxesAreEstimates: { type: 'boolean', const: true },
    missingInformation: { type: 'array', maxItems: 30, items: text(500) },
    limitations: { type: 'array', minItems: 1, maxItems: 30, items: text(500) },
  }),
  aggregates: { type: 'array', minItems: 3, maxItems: 3, items: obj({ riskBucket: bucket, currentPercent: percent, proposedPercent: percent }) },
  actions: { type: 'array', maxItems: 200, items: obj({
    instrumentName: text(300),
    ticker: { type: 'string', pattern: '^[A-Z0-9][A-Z0-9._-]{0,31}$' },
    isin: { type: 'string', pattern: '^[A-Z]{2}[A-Z0-9]{9}[0-9]$' },
    riskBucket: bucket,
    action: { type: 'string', enum: ['keep', 'reduce', 'increase', 'add'] },
    currentPercent: percent, targetPercent: percent,
    amount: { type: 'number', minimum: 0, maximum: 1e12 },
    priority: { type: 'integer', minimum: 1, maximum: 100 },
    rationale: text(5000), risks: text(5000),
  }) },
});
const validate = new Ajv({ strict: true, allErrors: false }).compile(recommendationSchema);
export function validateRecommendation(value, instruments, adjustments) {
  if (!validate(value)) fail('INVALID_MODEL_SCHEMA');
  if (new Set(value.aggregates.map((v) => v.riskBucket)).size !== 3) fail('INVALID_MODEL_BUCKETS');
  try { validateModelRecommendation(value, instruments, adjustments); }
  catch { fail('INVALID_MODEL_ALLOCATION'); }
  return value;
}
