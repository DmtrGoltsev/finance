package com.finance.mvp.investments

import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.BrokerageAccountProfile
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.InvestmentPolicy
import com.finance.mvp.api.PortfolioImport
import com.finance.mvp.api.PortfolioPosition
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationHistoryItem
import com.finance.mvp.api.RecommendationHistoryPage
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.api.TaxAccountType
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

internal interface InvestmentRemoteDataSource {
    suspend fun getInvestmentPolicy(): ApiResult<InvestmentPolicy>
    suspend fun putInvestmentPolicy(policy: InvestmentPolicy): ApiResult<InvestmentPolicy>
    suspend fun createPortfolioImport(
        idempotencyKey: String,
        accountProfile: BrokerageAccountProfile,
        screenshotCount: Int,
        observedAt: String,
    ): ApiResult<PortfolioImport>
    suspend fun confirmPortfolioImport(
        importId: String,
        accountProfileId: String,
        freeCash: String,
        monthlyContribution: String,
        positions: List<PortfolioPosition>,
    ): ApiResult<PortfolioSnapshot>
    suspend fun discardPortfolioImport(importId: String): ApiResult<Unit>
    suspend fun listPortfolioSnapshots(): ApiResult<List<PortfolioSnapshot>>
    suspend fun createRecommendationJob(idempotencyKey: String, snapshotIds: List<String>): ApiResult<RecommendationJob>
    suspend fun listRecommendationJobs(limit: Int, cursor: String?): ApiResult<RecommendationHistoryPage>
    suspend fun getRecommendationJob(jobId: String): ApiResult<RecommendationJob>
    suspend fun getRecommendationReport(jobId: String): ApiResult<RecommendationReport>
}

private class FinanceInvestmentRemoteDataSource(
    private val client: FinanceApiClient,
) : InvestmentRemoteDataSource {
    override suspend fun getInvestmentPolicy() = client.getInvestmentPolicy()
    override suspend fun putInvestmentPolicy(policy: InvestmentPolicy) = client.putInvestmentPolicy(policy)
    override suspend fun createPortfolioImport(idempotencyKey: String, accountProfile: BrokerageAccountProfile, screenshotCount: Int, observedAt: String) =
        client.createPortfolioImport(idempotencyKey, accountProfile, screenshotCount, observedAt)
    override suspend fun confirmPortfolioImport(importId: String, accountProfileId: String, freeCash: String, monthlyContribution: String, positions: List<PortfolioPosition>) =
        client.confirmPortfolioImport(importId, accountProfileId, freeCash, monthlyContribution, positions)
    override suspend fun discardPortfolioImport(importId: String) = client.discardPortfolioImport(importId)
    override suspend fun listPortfolioSnapshots() = client.listPortfolioSnapshots()
    override suspend fun createRecommendationJob(idempotencyKey: String, snapshotIds: List<String>) =
        client.createRecommendationJob(idempotencyKey, snapshotIds)
    override suspend fun listRecommendationJobs(limit: Int, cursor: String?) = client.listRecommendationJobs(limit, cursor)
    override suspend fun getRecommendationJob(jobId: String) = client.getRecommendationJob(jobId)
    override suspend fun getRecommendationReport(jobId: String) = client.getRecommendationReport(jobId)
}

class InvestmentRepository internal constructor(
    private val remote: InvestmentRemoteDataSource,
    private val store: InvestmentStore,
    private val now: () -> Instant = Instant::now,
    private val uuid: () -> String = { UUID.randomUUID().toString() },
) {
    constructor(
        apiClient: FinanceApiClient,
        store: InvestmentStore,
        now: () -> Instant = Instant::now,
        uuid: () -> String = { UUID.randomUUID().toString() },
    ) : this(FinanceInvestmentRemoteDataSource(apiClient), store, now, uuid)

    suspend fun load(userId: String): InvestmentOverview {
        val cachedSnapshots = store.snapshots(userId)
        val localRecommendations = store.recommendations(userId)
        val policyResult = remote.getInvestmentPolicy()
        val snapshotsResult = remote.listPortfolioSnapshots()
        val historyResult = fetchRecommendationHistory()
        val recommendationsAfterHistory = if (historyResult is ApiResult.Success) {
            historyResult.value.forEach { item ->
                store.cacheRecommendation(
                    userId = userId,
                    job = item.job,
                    accountProfiles = item.accountProfiles,
                    reportSummary = item.reportSummary,
                    reportPath = item.reportPath,
                )
            }
            store.recommendations(userId)
        } else {
            localRecommendations
        }
        val cachedRecommendations = if (
            policyResult is ApiResult.Success || snapshotsResult is ApiResult.Success || historyResult is ApiResult.Success
        ) {
            refreshKnownRecommendations(userId, recommendationsAfterHistory)
        } else recommendationsAfterHistory
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

    suspend fun beginImport(
        brokerage: Brokerage,
        userLabel: String,
        accountType: TaxAccountType,
        screenshotCount: Int,
    ): ApiResult<PortfolioImport> {
        val profile = BrokerageAccountProfile(
            id = uuid(),
            brokerage = brokerage,
            userLabel = userLabel.trim(),
            accountType = accountType,
        )
        return when (val result = remote.createPortfolioImport(
            idempotencyKey = "android-import-${uuid()}",
            accountProfile = profile,
            screenshotCount = screenshotCount,
            observedAt = now().toString(),
        )) {
            is ApiResult.Success -> ApiResult.Success(result.value.copy(accountProfile = result.value.accountProfile ?: profile, brokerage = profile.brokerage))
            is ApiResult.Failure -> result
        }
    }

    suspend fun confirmImport(
        userId: String,
        importId: String,
        accountProfileId: String,
        freeCash: String,
        monthlyContribution: String,
        positions: List<PortfolioPosition>,
    ): ApiResult<PortfolioSnapshot> {
        val result = remote.confirmPortfolioImport(importId, accountProfileId, freeCash, monthlyContribution, positions)
        if (result is ApiResult.Success) store.cacheSnapshots(userId, listOf(result.value))
        return result
    }

    suspend fun updatePolicy(policy: InvestmentPolicy): ApiResult<InvestmentPolicy> =
        remote.putInvestmentPolicy(policy)

    suspend fun startRecommendation(userId: String, snapshotIds: List<String>): ApiResult<RecommendationJob> {
        val result = remote.createRecommendationJob("android-analysis-${uuid()}", snapshotIds)
        if (result is ApiResult.Success) store.cacheRecommendation(userId, result.value)
        return result
    }

    suspend fun refreshRecommendation(userId: String, jobId: String): ApiResult<CachedInvestmentRecommendation> {
        val jobResult = remote.getRecommendationJob(jobId)
        if (jobResult is ApiResult.Failure) {
            return ApiResult.Failure(jobResult.message, jobResult.cause, jobResult.statusCode, jobResult.kind)
        }
        jobResult as ApiResult.Success
        val reportResult = if (jobResult.value.status == RecommendationStatus.Ready) {
            remote.getRecommendationReport(jobId)
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

    suspend fun discardDraft(userId: String, importId: String): ApiResult<Unit> {
        val result = remote.discardPortfolioImport(importId)
        if (result is ApiResult.Success) store.deleteDraft(userId, importId)
        return result
    }

    private suspend fun refreshKnownRecommendations(
        userId: String,
        cached: List<CachedInvestmentRecommendation>,
    ): List<CachedInvestmentRecommendation> {
        cached.take(MAX_HISTORY_REFRESH).forEach { existing ->
            if (!needsRecommendationPolling(existing)) return@forEach
            val job = (remote.getRecommendationJob(existing.job.id) as? ApiResult.Success)?.value
                ?: return@forEach
            val report = when {
                job.status == RecommendationStatus.Ready ->
                    (remote.getRecommendationReport(job.id) as? ApiResult.Success)?.value ?: existing.report
                else -> existing.report
            }
            store.cacheRecommendation(
                userId,
                job,
                report,
                existing.accountProfiles,
                existing.reportSummary,
                existing.reportPath,
            )
        }
        return store.recommendations(userId)
    }

    private suspend fun fetchRecommendationHistory(): ApiResult<List<RecommendationHistoryItem>> {
        val items = mutableListOf<RecommendationHistoryItem>()
        var cursor: String? = null
        repeat(MAX_HISTORY_PAGES) {
            when (val page = remote.listRecommendationJobs(HISTORY_PAGE_SIZE, cursor)) {
                is ApiResult.Failure -> return page
                is ApiResult.Success -> {
                    items += page.value.items
                    if (!page.value.hasMore) return ApiResult.Success(items)
                    cursor = page.value.nextCursor
                        ?: return ApiResult.Failure("Сервер вернул неполную страницу истории без курсора")
                }
            }
        }
        return ApiResult.Success(items)
    }

    private companion object {
        const val MAX_HISTORY_REFRESH = 50
        const val MAX_HISTORY_PAGES = 20
        const val HISTORY_PAGE_SIZE = 100
    }
}

internal fun newestSnapshotsPerAccount(snapshots: List<PortfolioSnapshot>): List<PortfolioSnapshot> =
    snapshots.groupBy { snapshot -> snapshot.accountProfile?.id ?: "legacy:${snapshot.brokerage.apiValue}" }
        .values
        .mapNotNull { accountSnapshots -> accountSnapshots.maxByOrNull { it.observedAt } }
        .sortedWith(compareBy({ it.brokerage.ordinal }, { it.accountProfile?.userLabel.orEmpty() }))

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
    ) || (cached.job.status == RecommendationStatus.Ready && cached.report == null && cached.reportSummary == null)
