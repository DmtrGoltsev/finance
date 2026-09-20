export function validEnvelope(now = new Date()) {
  return {
    schemaVersion: 1,
    eventId: '11111111-1111-4111-8111-111111111111',
    jobId: '22222222-2222-4222-8222-222222222222',
    attempt: 1,
    createdAt: now.toISOString(),
    analysisPackage: {
      schemaVersion: 1,
      currency: 'RUB',
      market: 'RU',
      policy: { conservativePercent: '40', moderatePercent: '30', aggressivePercent: '30', tolerancePercent: '5' },
      freeCash: '1000.0000',
      monthlyContribution: '500.0000',
      positions: [{
        secid: 'SBER', isin: 'RU0009029540', instrumentType: 'stock', riskBucket: 'moderate',
        quantity: '10.0000', marketValue: '3000.0000', averagePrice: '300.0000',
        nominal: null, accruedInterest: null, couponRate: null, maturityDate: null,
        taxAccountType: 'brokerage', holdingStartedAt: null, estimatedFeeRate: null,
      }],
      constraints: {
        cashFirst: true, automaticExecution: false, marketDataMaxAgeHours: 24,
        recommendationValidityDays: 7,
        allowedSources: ['moex.com', 'cbr.ru', 'minfin.gov.ru', 'nalog.gov.ru'],
      },
    },
  };
}
