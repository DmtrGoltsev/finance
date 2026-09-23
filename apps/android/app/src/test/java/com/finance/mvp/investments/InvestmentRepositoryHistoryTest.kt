package com.finance.mvp.investments

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.BrokerageAccountProfile
import com.finance.mvp.api.InvestmentPolicy
import com.finance.mvp.api.PortfolioImport
import com.finance.mvp.api.PortfolioPosition
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationHistoryItem
import com.finance.mvp.api.RecommendationHistoryPage
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.api.TaxAccountType
import com.finance.mvp.local.FinanceLocalDatabase
import com.finance.mvp.local.InvestmentStore
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class InvestmentRepositoryHistoryTest {
    private lateinit var database: FinanceLocalDatabase

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext<Context>(),
            FinanceLocalDatabase::class.java,
        ).allowMainThreadQueries().build()
    }

    @After fun tearDown() = database.close()

    @Test fun retryDeliveryCachesSameJobAndPreservesProfilesWithoutNewIdentity() = runTest {
        val original = job("same-job", "2026-09-20T12:00:00Z")
            .copy(status = RecommendationStatus.Failed, lastErrorCode = "delivery_failed")
        val store = InvestmentStore(database)
        val profiles = listOf(profile("profile-1", "Основной"))
        store.cacheRecommendation("owner", original, accountProfiles = profiles)
        val remote = FakeInvestmentRemote()
        remote.retryResult = ApiResult.Success(original.copy(status = RecommendationStatus.Queued, lastErrorCode = null))
        val repository = InvestmentRepository(remote, store, uuid = { error("Retry must not allocate a new identity") })
        assertTrue(repository.retryDelivery("owner", original.id) is ApiResult.Success)
        assertEquals(listOf(original.id), remote.retriedJobs)
        val cached = store.recommendations("owner").single()
        assertEquals(original.id, cached.job.id)
        assertEquals(RecommendationStatus.Queued, cached.job.status)
        assertEquals(profiles, cached.accountProfiles)
        remote.retryResult = ApiResult.Failure("offline")
        assertTrue(repository.retryDelivery("owner", original.id) is ApiResult.Failure)
        assertEquals(cached, store.recommendations("owner").single())
    }

    @Test fun cleanLoginRestoresAllHistoryPagesNewestFirstWithSummaries() = runTest {
        val main = profile("11111111-1111-4111-8111-111111111111", "Основной")
        val iis = profile("22222222-2222-4222-8222-222222222222", "ИИС")
        val remote = FakeInvestmentRemote(
            historyPages = mutableListOf(
                RecommendationHistoryPage(
                    items = listOf(history(job("new", "2026-09-20T12:00:00Z"), listOf(main, iis), "Новая сводка")),
                    limit = 1, nextCursor = "page-2", hasMore = true,
                ),
                RecommendationHistoryPage(
                    items = listOf(history(job("old", "2026-09-19T12:00:00Z"), listOf(main), "Старая сводка")),
                    limit = 1, nextCursor = null, hasMore = false,
                ),
            ),
        )
        val repository = InvestmentRepository(remote, InvestmentStore(database))

        val overview = repository.load("owner")

        assertEquals(listOf("new", "old"), overview.recommendations.map { it.job.id })
        assertEquals("Новая сводка", overview.recommendations.first().reportSummary)
        assertEquals(listOf("Основной", "ИИС"), overview.recommendations.first().accountProfiles.map { it.userLabel })
        assertEquals(listOf(null, "page-2"), remote.historyCursors)
    }

    @Test fun discardDeletesRemoteImportAndLocalStructuredDraft() = runTest {
        val profile = profile("33333333-3333-4333-8333-333333333333", "Брокерский")
        val store = InvestmentStore(database)
        store.cacheDraft(
            "owner",
            PortfolioDraftState(
                importId = "44444444-4444-4444-8444-444444444444",
                brokerage = Brokerage.SberInvestments,
                screenshotCount = 1,
                positions = emptyList(),
                createdAtEpochMillis = 1,
                accountProfile = profile,
            ),
        )
        val remote = FakeInvestmentRemote()

        val result = InvestmentRepository(remote, store).discardDraft("owner", "44444444-4444-4444-8444-444444444444")

        assertTrue(result is ApiResult.Success)
        assertEquals(listOf("44444444-4444-4444-8444-444444444444"), remote.discardedImports)
        assertNull(store.draft("owner"))
    }

    @Test fun newestSnapshotsKeepsTwoSberAccountsAndOnlyNewestPerProfile() {
        val main = profile("55555555-5555-4555-8555-555555555555", "Основной")
        val iis = profile("66666666-6666-4666-8666-666666666666", "ИИС")
        val snapshots = listOf(
            snapshot("main-old", main, "2026-09-18T10:00:00Z"),
            snapshot("main-new", main, "2026-09-20T10:00:00Z"),
            snapshot("iis-new", iis, "2026-09-19T10:00:00Z"),
        )

        val newest = newestSnapshotsPerAccount(snapshots)

        assertEquals(setOf("main-new", "iis-new"), newest.map { it.id }.toSet())
    }

    private fun profile(id: String, label: String) = BrokerageAccountProfile(
        id = id,
        brokerage = Brokerage.SberInvestments,
        userLabel = label,
        accountType = if (label == "ИИС") TaxAccountType.IisIII else TaxAccountType.Brokerage,
    )

    private fun job(id: String, createdAt: String) = RecommendationJob(
        id = id, snapshotIds = listOf("snapshot-$id"), status = RecommendationStatus.Ready,
        attemptCount = 1, marketDataAsOf = createdAt, cashFirstAdjustments = emptyList(),
        createdAt = createdAt, updatedAt = createdAt, completedAt = createdAt,
    )

    private fun history(job: RecommendationJob, profiles: List<BrokerageAccountProfile>, summary: String) =
        RecommendationHistoryItem(job, profiles, summary, "/api/v1/investments/recommendation-jobs/${job.id}/report")

    private fun snapshot(id: String, profile: BrokerageAccountProfile, observedAt: String) = PortfolioSnapshot(
        id = id, importId = "import-$id", brokerage = profile.brokerage, observedAt = observedAt,
        currency = "RUB", freeCash = "0", monthlyContribution = "0", totalValue = "100",
        positions = emptyList(), createdAt = observedAt, accountProfile = profile,
    )

    private class FakeInvestmentRemote(
        val historyPages: MutableList<RecommendationHistoryPage> = mutableListOf(
            RecommendationHistoryPage(emptyList(), 100, null, false),
        ),
    ) : InvestmentRemoteDataSource {
        val historyCursors = mutableListOf<String?>()
        val discardedImports = mutableListOf<String>()
        val retriedJobs = mutableListOf<String>()
        var retryResult: ApiResult<RecommendationJob> = ApiResult.Failure("unused")
        override suspend fun retryRecommendationDelivery(jobId: String): ApiResult<RecommendationJob> {
            retriedJobs += jobId
            return retryResult
        }

        override suspend fun getInvestmentPolicy() = ApiResult.Success(InvestmentPolicy())
        override suspend fun putInvestmentPolicy(policy: InvestmentPolicy) = ApiResult.Success(policy)
        override suspend fun createPortfolioImport(idempotencyKey: String, accountProfile: BrokerageAccountProfile, screenshotCount: Int, observedAt: String): ApiResult<PortfolioImport> =
            ApiResult.Failure("unused")
        override suspend fun confirmPortfolioImport(importId: String, accountProfileId: String, freeCash: String, monthlyContribution: String, positions: List<PortfolioPosition>): ApiResult<PortfolioSnapshot> =
            ApiResult.Failure("unused")
        override suspend fun discardPortfolioImport(importId: String): ApiResult<Unit> {
            discardedImports += importId
            return ApiResult.Success(Unit)
        }
        override suspend fun listPortfolioSnapshots() = ApiResult.Success(emptyList<PortfolioSnapshot>())
        override suspend fun createRecommendationJob(idempotencyKey: String, snapshotIds: List<String>): ApiResult<RecommendationJob> =
            ApiResult.Failure("unused")
        override suspend fun listRecommendationJobs(limit: Int, cursor: String?): ApiResult<RecommendationHistoryPage> {
            historyCursors += cursor
            return ApiResult.Success(historyPages.removeAt(0))
        }
        override suspend fun getRecommendationJob(jobId: String): ApiResult<RecommendationJob> = ApiResult.Failure("unused")
        override suspend fun getRecommendationReport(jobId: String): ApiResult<RecommendationReport> = ApiResult.Failure("unused")
    }
}
