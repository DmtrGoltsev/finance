package com.finance.mvp.sync

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiFailureKind
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.PlanningPlan
import com.finance.mvp.api.PlanningPlanCopyRequest
import com.finance.mvp.api.PlanningPlanCreateRequest
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.SyncPullRequest
import com.finance.mvp.api.SyncPullResponse
import com.finance.mvp.api.SyncPushRequest
import com.finance.mvp.api.SyncPushResponse
import com.finance.mvp.api.TransactionSummary
import com.finance.mvp.local.FinanceLocalDatabase
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PlanningRepositoryTest {
    private lateinit var database: FinanceLocalDatabase
    private lateinit var apiClient: FakePlanningApiClient
    private lateinit var repository: PlanningRepository

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, FinanceLocalDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        apiClient = FakePlanningApiClient()
        val syncManager = SyncManager(
            database = database,
            apiClient = NoopSyncApiClient(),
            deviceIdStore = InMemoryDeviceIdStore("android-test-device"),
            nowEpochMillis = { 1000 },
            uuidFactory = { PLAN_ID },
        )
        repository = PlanningRepository(
            database = database,
            apiClient = apiClient,
            syncManager = syncManager,
            nowEpochMillis = { 1000 },
        )
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun retriableCreatePlanFailureQueuesPendingPlan() = runTest {
        apiClient.createPlanResult = ApiResult.Failure("offline", kind = ApiFailureKind.NETWORK)

        val outcome = repository.createPlan(USER_ID, planCreateRequest())
        val pending = database.pendingMutationDao().pendingForUser(USER_ID)
        val localPlan = database.localPlanningPlanDao().findByLocalId(USER_ID, PLAN_ID)

        assertTrue(outcome is PlanningMutationOutcome.Queued)
        assertEquals(1, pending.size)
        assertEquals(SyncManager.ENTITY_PLANNING_PLANS, pending.single().entityType)
        assertEquals(SyncManager.OPERATION_CREATE, pending.single().operation)
        assertEquals(SyncManager.SYNC_STATUS_PENDING, localPlan?.syncStatus)
    }

    @Test
    fun nonRetriableCreatePlanFailuresDoNotQueue() = runTest {
        listOf(
            ApiResult.Failure("bad request", statusCode = 400),
            ApiResult.Failure("contract", kind = ApiFailureKind.CONTRACT),
            ApiResult.Failure("unknown", kind = ApiFailureKind.UNKNOWN),
        ).forEach { failure ->
            apiClient.createPlanResult = failure

            val outcome = repository.createPlan(USER_ID, planCreateRequest())

            assertTrue(outcome is PlanningMutationOutcome.Failed)
            assertEquals(0, database.pendingMutationDao().pendingForUser(USER_ID).size)
            assertEquals(0, database.localPlanningPlanDao().listForUser(USER_ID).size)
        }
    }

    @Test
    fun copyPlanRetriableFailureIsOnlineOnlyAndDoesNotQueue() = runTest {
        apiClient.copyPlanResult = ApiResult.Failure("offline", kind = ApiFailureKind.NETWORK)

        val outcome = repository.copyPlan(
            userId = USER_ID,
            sourcePlanId = PLAN_ID,
            request = PlanningPlanCopyRequest(targetMonth = "2026-08"),
        )

        assertTrue(outcome is PlanningMutationOutcome.Failed)
        assertTrue((outcome as PlanningMutationOutcome.Failed).failure.message.contains("требует подключения"))
        assertEquals(0, database.pendingMutationDao().pendingForUser(USER_ID).size)
        assertEquals(0, database.localPlanningPlanDao().listForUser(USER_ID).size)
    }

    private fun planCreateRequest(): PlanningPlanCreateRequest {
        return PlanningPlanCreateRequest(scope = "personal", month = "2026-07", currency = "RUB")
    }

    private class NoopSyncApiClient : SyncApiClient {
        override suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> {
            return ApiResult.Failure("unused")
        }

        override suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> {
            return ApiResult.Failure("unused")
        }
    }

    private class FakePlanningApiClient : FinanceApiClient {
        override val config: ApiConfig = ApiConfig("http://localhost:8000")
        var createPlanResult: ApiResult<PlanningPlan> = ApiResult.Success(
            PlanningPlan(id = PLAN_ID, scope = "personal", month = "2026-07", currency = "RUB", version = 1),
        )
        var copyPlanResult: ApiResult<PlanningPlan> = ApiResult.Success(
            PlanningPlan(id = PLAN_ID, scope = "personal", month = "2026-08", currency = "RUB", version = 1),
        )

        override suspend fun login(email: String, password: String): ApiResult<SessionStatus> = ApiResult.Failure("unused")
        override suspend fun sessionStatus(): ApiResult<SessionStatus> = ApiResult.Failure("unused")
        override suspend fun dashboard(startDate: String?, endDate: String?): ApiResult<FinanceDashboard> = ApiResult.Failure("unused")

        override suspend fun createDemoAccount(
            householdId: String?,
            currency: String,
            initialBalance: String,
            accountType: String,
            ownershipType: String,
            isPaymentAccount: Boolean,
        ): ApiResult<AccountSummary> = ApiResult.Failure("unused")

        override suspend fun createAccount(
            name: String,
            currency: String,
            initialBalance: String,
            accountType: String,
            householdId: String?,
            assetCategoryId: String?,
            isPaymentAccount: Boolean,
        ): ApiResult<AccountSummary> = ApiResult.Failure("unused")

        override suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary> = ApiResult.Failure("unused")
        override suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary> = ApiResult.Failure("unused")
        override suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary> = ApiResult.Failure("unused")

        override suspend fun createDemoCategory(householdId: String?, categoryType: String): ApiResult<CategorySummary> {
            return ApiResult.Failure("unused")
        }

        override suspend fun createCategory(
            name: String,
            householdId: String?,
            categoryType: String,
        ): ApiResult<CategorySummary> = ApiResult.Failure("unused")

        override suspend fun updateCategory(category: CategorySummary): ApiResult<CategorySummary> = ApiResult.Failure("unused")
        override suspend fun archiveCategory(categoryId: String): ApiResult<CategorySummary> = ApiResult.Failure("unused")
        override suspend fun restoreCategory(categoryId: String): ApiResult<CategorySummary> = ApiResult.Failure("unused")

        override suspend fun createDemoTransaction(
            account: AccountSummary,
            category: CategorySummary?,
            transactionType: String,
            amount: String,
            transactionDate: String,
        ): ApiResult<TransactionSummary> = ApiResult.Failure("unused")

        override suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary> {
            return ApiResult.Failure("unused")
        }

        override suspend fun deleteTransaction(transactionId: String): ApiResult<Unit> = ApiResult.Failure("unused")
        override suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary> = ApiResult.Failure("unused")

        override suspend fun createDemoTransfer(
            source: AccountSummary,
            destination: AccountSummary,
            amount: String,
        ): ApiResult<TransactionSummary> = ApiResult.Failure("unused")

        override suspend fun createPlanningPlan(request: PlanningPlanCreateRequest): ApiResult<PlanningPlan> {
            return createPlanResult
        }

        override suspend fun copyPlanningPlan(planId: String, request: PlanningPlanCopyRequest): ApiResult<PlanningPlan> {
            return copyPlanResult
        }

        override suspend fun logout(): ApiResult<Unit> = ApiResult.Failure("unused")
    }

    private companion object {
        const val USER_ID = "user-1"
        const val PLAN_ID = "55555555-5555-4555-8555-555555555555"
    }
}
