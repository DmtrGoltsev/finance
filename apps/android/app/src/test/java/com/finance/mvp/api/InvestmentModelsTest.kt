package com.finance.mvp.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InvestmentModelsTest {
    @Test
    fun deliveryFailureSurvivesCacheAndOnlyEnablesRetryForDeliveryFailure() {
        val job = parseRecommendationJob(JSONObject("""{"id":"same-job","snapshotIds":[],"status":"failed","attemptCount":1,"createdAt":"2026-09-20T10:00:00Z","updatedAt":"2026-09-20T10:00:00Z","lastErrorCode":"delivery_failed"}"""))
        assertTrue(job.needsDeliveryRetry)
        assertEquals(job, parseRecommendationJob(JSONObject(job.toCacheJson())))
        assertTrue(!job.copy(lastErrorCode = "analysis_failed").needsDeliveryRetry)
        assertTrue(!job.copy(status = RecommendationStatus.Queued).needsDeliveryRetry)
        assertTrue(!job.copy(lastErrorCode = null).needsDeliveryRetry)
    }

    @Test
    fun portfolioInputContainsEveryEditableContractFieldAndNoImageData() {
        val json = PortfolioPosition(
            instrumentName = "ОФЗ 26238",
            ticker = "SU26238RMFS4",
            isin = "RU000A1038V6",
            instrumentType = InvestmentInstrumentType.Bond,
            riskBucket = InvestmentRiskBucket.Conservative,
            quantity = "2",
            marketPrice = "620",
            marketValue = "1240",
            averagePrice = "610",
            nominal = "1000",
            accruedInterest = "12.5",
            couponRate = "7.1",
            maturityDate = "2041-05-15",
            taxAccountType = TaxAccountType.IisIII,
            holdingStartedAt = "2026-01-01",
            estimatedFeeRate = "0.3",
        ).toInputJson()

        assertEquals("RU000A1038V6", json.getString("isin"))
        assertEquals("iis_iii", json.getString("taxAccountType"))
        assertEquals("12.5", json.getString("accruedInterest"))
        assertTrue(!json.has("image") && !json.has("ocrText"))
    }

    @Test
    fun parsesNullableRecommendationDatesAndStaleReport() {
        val job = parseRecommendationJob(
            JSONObject(
                """{"data":{"id":"job-1","snapshotIds":["snap-1"],"status":"queued","attemptCount":0,"marketDataAsOf":null,"cashFirstAdjustments":[],"createdAt":"2026-09-20T10:00:00Z","updatedAt":"2026-09-20T10:00:00Z","completedAt":null}}""",
            ),
        )
        assertNull(job.marketDataAsOf)
        assertEquals(RecommendationStatus.Queued, job.status)
    }

    @Test
    fun recommendationAssumptionsSurviveApiParsingAndCacheRoundTrip() {
        val report = parseRecommendationReport(
            JSONObject(
                """{"data":{"id":"report-1","jobId":"job-1","summary":"Итог","assumptions":{"monthlyContribution":"50000","horizon":"5 years"},"generatedAt":"2026-09-20T10:00:00Z","validUntil":"2026-09-21T10:00:00Z","isStale":false,"disclaimer":"Не ИИР","actions":[],"sources":[]}}""",
            ),
        )

        assertEquals("50000", report.assumptions["monthlyContribution"])
        val cached = parseRecommendationReport(JSONObject(report.toCacheJson()))
        assertEquals(report.assumptions, cached.assumptions)
    }
}
