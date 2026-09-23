package com.finance.mvp.investments

import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.local.CachedInvestmentRecommendation
import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InvestmentRecommendationStateTest {
    @Test
    fun readyJobWithoutReportKeepsPollingAcrossReload() {
        assertTrue(needsRecommendationPolling(CachedInvestmentRecommendation(job(RecommendationStatus.Ready), report = null)))
    }

    @Test
    fun readyJobWithReportStopsPolling() {
        val cached = CachedInvestmentRecommendation(job(RecommendationStatus.Ready), report("2026-09-22T10:00:00Z"))
        assertFalse(needsRecommendationPolling(cached))
    }

    @Test
    fun reportBecomesStaleWhenValidUntilPassesEvenIfServerFlagIsFalse() {
        assertEquals(
            RecommendationStatus.Stale,
            recommendationStatus(
                job(RecommendationStatus.Ready),
                report("2026-09-20T09:59:59Z"),
                Instant.parse("2026-09-20T10:00:00Z"),
            ),
        )
    }

    private fun job(status: RecommendationStatus) = RecommendationJob(
        id = "job-1",
        snapshotIds = listOf("snapshot-1"),
        status = status,
        attemptCount = 1,
        marketDataAsOf = null,
        cashFirstAdjustments = emptyList(),
        createdAt = "2026-09-20T09:00:00Z",
        updatedAt = "2026-09-20T09:30:00Z",
        completedAt = if (status == RecommendationStatus.Ready) "2026-09-20T09:30:00Z" else null,
    )

    private fun report(validUntil: String) = RecommendationReport(
        id = "report-1",
        jobId = "job-1",
        summary = "Итог",
        assumptions = mapOf("horizon" to "5 years"),
        generatedAt = "2026-09-20T09:30:00Z",
        validUntil = validUntil,
        isStale = false,
        disclaimer = "Не ИИР",
        actions = emptyList(),
        sources = emptyList(),
    )
}
