package com.finance.mvp.investments

import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.InvestmentPolicy
import com.finance.mvp.api.PortfolioImport
import com.finance.mvp.api.PortfolioPosition
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.local.CachedInvestmentRecommendation
import com.finance.mvp.local.InvestmentStore
import java.time.Instant
import java.util.UUID

data class InvestmentOverview(
    val policy: InvestmentPolicy = InvestmentPolicy(),
    val snapshots: List<PortfolioSnapshot> = emptyList(),
    val recommendations: List<CachedInvestmentRecommendation> = emptyList(),
    val isOffline: Boolean = false,
    val message: String? = null,
)

class InvestmentRepository(
    private val apiClient: FinanceApiClient,
    private val store: InvestmentStore,
    private val now: () -> Instant = Instant::now,
    private val uuid: () -> String = { UUID.randomUUID().toString() },
) {
    suspend fun load(userId: String): InvestmentOverview {
        val cachedSnapshots = store.snapshots(userId)
        val localRecommendations = store.recommendations(userId)
        val policyResult = apiClient.getInvestmentPolicy()
        val snapshotsResult = apiClient.listPortfolioSnapshots()
        val cachedRecommendations = if (policyResult is ApiResult.Success || snapshotsResult is ApiResult.Success) {
            refreshKnownRecommendations(userId, localRecommendations)
        } else {
            localRecommendations
        }
        return if (snapshotsResult is ApiResult.Success) {
            store.cacheSnapshots(userId, snapshotsResult.value)
            InvestmentOverview(
                policy = (policyResult as? ApiResult.Success)?.value ?: InvestmentPolicy(),
                snapshots = snapshotsResult.value,
                recommendations = cachedRecommendations,
            )
        } else {
            InvestmentOverview(
                policy = (policyResult as? ApiResult.Success)?.value ?: InvestmentPolicy(),
                snapshots = cachedSnapshots,
                recommendations = cachedRecommendations,
                isOffline = true,
                message = "Показаны последние сохранённые данные. Импорт и анализ требуют подключения к сети.",
            )
        }
    }

    suspend fun beginImport(brokerage: Brokerage, screenshotCount: Int): ApiResult<PortfolioImport> =
        apiClient.createPortfolioImport(
            idempotencyKey = "android-import-${uuid()}",
            brokerage = brokerage,
            screenshotCount = screenshotCount,
            observedAt = now().toString(),
        )

    suspend fun confirmImport(
        userId: String,
        importId: String,
        freeCash: String,
        monthlyContribution: String,
        positions: List<PortfolioPosition>,
    ): ApiResult<PortfolioSnapshot> {
        val result = apiClient.confirmPortfolioImport(importId, freeCash, monthlyContribution, positions)
        if (result is ApiResult.Success) store.cacheSnapshots(userId, listOf(result.value))
        return result
    }

    suspend fun updatePolicy(policy: InvestmentPolicy): ApiResult<InvestmentPolicy> =
        apiClient.putInvestmentPolicy(policy)

    suspend fun startRecommendation(userId: String, snapshotIds: List<String>): ApiResult<RecommendationJob> {
        val result = apiClient.createRecommendationJob("android-analysis-${uuid()}", snapshotIds)
        if (result is ApiResult.Success) store.cacheRecommendation(userId, result.value)
        return result
    }

    suspend fun refreshRecommendation(userId: String, jobId: String): ApiResult<CachedInvestmentRecommendation> {
        val jobResult = apiClient.getRecommendationJob(jobId)
        if (jobResult is ApiResult.Failure) {
            return ApiResult.Failure(jobResult.message, jobResult.cause, jobResult.statusCode, jobResult.kind)
        }
        jobResult as ApiResult.Success
        val reportResult = if (jobResult.value.status == RecommendationStatus.Ready) {
            apiClient.getRecommendationReport(jobId)
        } else {
            null
        }
        val report = (reportResult as? ApiResult.Success)?.value
        store.cacheRecommendation(userId, jobResult.value, report)
        return ApiResult.Success(CachedInvestmentRecommendation(jobResult.value, report))
    }

    suspend fun cachedRecommendations(userId: String): List<CachedInvestmentRecommendation> =
        store.recommendations(userId)

    suspend fun draft(userId: String): PortfolioDraftState? = store.draft(userId)

    suspend fun saveDraft(userId: String, draft: PortfolioDraftState) = store.cacheDraft(userId, draft)

    suspend fun deleteDraft(userId: String, importId: String) = store.deleteDraft(userId, importId)

    private suspend fun refreshKnownRecommendations(
        userId: String,
        cached: List<CachedInvestmentRecommendation>,
    ): List<CachedInvestmentRecommendation> {
        cached.take(MAX_HISTORY_REFRESH).forEach { existing ->
            val job = (apiClient.getRecommendationJob(existing.job.id) as? ApiResult.Success)?.value
                ?: return@forEach
            val report = when {
                job.status == RecommendationStatus.Ready ->
                    (apiClient.getRecommendationReport(job.id) as? ApiResult.Success)?.value ?: existing.report
                else -> existing.report
            }
            store.cacheRecommendation(userId, job, report)
        }
        return store.recommendations(userId)
    }

    private companion object {
        const val MAX_HISTORY_REFRESH = 50
    }
}

internal fun newestSnapshotsPerBroker(snapshots: List<PortfolioSnapshot>): List<PortfolioSnapshot> =
    snapshots.groupBy { it.brokerage }.values.mapNotNull { brokerSnapshots ->
        brokerSnapshots.maxByOrNull { it.observedAt }
    }.sortedBy { it.brokerage.ordinal }

internal fun recommendationStatus(
    job: RecommendationJob,
    report: RecommendationReport?,
    now: Instant = Instant.now(),
): RecommendationStatus = when {
    report != null && (report.isStale || runCatching { Instant.parse(report.validUntil) <= now }.getOrDefault(false)) ->
        RecommendationStatus.Stale
    else -> job.status
}

internal fun needsRecommendationPolling(cached: CachedInvestmentRecommendation): Boolean =
    cached.job.status in setOf(
        RecommendationStatus.Queued,
        RecommendationStatus.Collecting,
        RecommendationStatus.Analyzing,
    ) || (cached.job.status == RecommendationStatus.Ready && cached.report == null)
