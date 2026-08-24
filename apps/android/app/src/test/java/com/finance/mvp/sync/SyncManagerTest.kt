package com.finance.mvp.sync

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiFailureKind
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.InvestmentMigrationCreateRequest
import com.finance.mvp.api.PlanningAllocationCreateRequest
import com.finance.mvp.api.PlanningAllocationUpdateRequest
import com.finance.mvp.api.PlanningIncomeSourceCreateRequest
import com.finance.mvp.api.PlanningIncomeSourceUpdateRequest
import com.finance.mvp.api.PlanningPlanCreateRequest
import com.finance.mvp.api.SyncChange
import com.finance.mvp.api.SyncMutationResult
import com.finance.mvp.api.SyncPullRequest
import com.finance.mvp.api.SyncPullResponse
import com.finance.mvp.api.SyncPushRequest
import com.finance.mvp.api.SyncPushResponse
import com.finance.mvp.local.FinanceLocalDatabase
import com.finance.mvp.local.LocalAccountEntity
import com.finance.mvp.local.LocalAssetCategoryEntity
import com.finance.mvp.local.LocalCategoryEntity
import com.finance.mvp.local.LocalPlanningAllocationEntity
import com.finance.mvp.local.LocalPlanningIncomeSourceEntity
import com.finance.mvp.local.LocalPlanningPlanEntity
import com.finance.mvp.local.LocalTransactionEntity
import com.finance.mvp.local.PendingMutationEntity
import kotlinx.coroutines.test.runTest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class SyncManagerTest {
    private lateinit var database: FinanceLocalDatabase
    private lateinit var apiClient: FakeSyncApiClient
    private lateinit var manager: SyncManager

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, FinanceLocalDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        apiClient = FakeSyncApiClient()
        manager = SyncManager(
            database = database,
            apiClient = apiClient,
            deviceIdStore = InMemoryDeviceIdStore("android-test-device"),
            nowEpochMillis = { 1000 },
            nowIso = { "2026-06-14T00:00:00Z" },
            uuidFactory = { ENTITY_ID },
        )
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun manualQuickAddIsSavedLocallyWithIdempotentPendingCreate() = runTest {
        manager.enqueueManualTransactionCreate(
            userId = USER_ID,
            transactionType = "expense",
            amount = "12.3400",
            currency = "RUB",
            accountId = "acc-1",
            categoryId = "cat-1",
            transactionDate = "2026-06-14",
            note = "Lunch",
            localTransactionId = ENTITY_ID,
        )
        manager.enqueueManualTransactionCreate(
            userId = USER_ID,
            transactionType = "expense",
            amount = "12.3400",
            currency = "RUB",
            accountId = "acc-1",
            categoryId = "cat-1",
            transactionDate = "2026-06-14",
            note = "Lunch",
            localTransactionId = ENTITY_ID,
        )

        val local = database.localTransactionDao().findByLocalId(USER_ID, ENTITY_ID)
        val pending = database.pendingMutationDao().pendingForUser(USER_ID)

        assertNotNull(local)
        assertEquals(SyncManager.SYNC_STATUS_PENDING, local?.syncStatus)
        assertEquals(1, pending.size)
        assertEquals(
            SyncManager.stableMutationId(
                deviceId = "android-test-device",
                entityId = ENTITY_ID,
                operation = SyncManager.OPERATION_CREATE,
                baseVersion = null,
                payloadJson = SyncManager.transactionPayload(
                    transactionType = "expense",
                    amount = "12.3400",
                    currency = "RUB",
                    accountId = "acc-1",
                    categoryId = "cat-1",
                    transactionDate = "2026-06-14",
                    note = "Lunch",
                ).toString(),
            ),
            pending.single().clientMutationId,
        )
    }

    @Test
    fun captureOcrAndScreenshotsAreOnlineOnlyUnsupportedSyncEntities() {
        assertTrue(SyncManager.isSyncableEntityType(SyncManager.ENTITY_TRANSACTIONS))
        assertTrue(!SyncManager.isSyncableEntityType(SyncManager.ENTITY_CAPTURE_DRAFTS))
        assertTrue(!SyncManager.isSyncableEntityType(SyncManager.ENTITY_OCR))
        assertTrue(!SyncManager.isSyncableEntityType(SyncManager.ENTITY_SCREENSHOTS))
        assertTrue(!SyncManager.isSyncableEntityType("screenshot_ocr"))
        assertTrue(SyncManager.ENTITY_CAPTURE_DRAFTS in SyncManager.ONLINE_ONLY_ENTITY_TYPES)
        assertTrue(SyncManager.ENTITY_OCR in SyncManager.ONLINE_ONLY_ENTITY_TYPES)
        assertTrue(SyncManager.ENTITY_SCREENSHOTS in SyncManager.ONLINE_ONLY_ENTITY_TYPES)
        assertTrue("screenshot_ocr" in SyncManager.ONLINE_ONLY_ENTITY_TYPES)

        try {
            SyncManager.requireSyncableEntityType("screenshot_ocr")
            fail("screenshot_ocr must not be accepted as a syncable entity type")
        } catch (error: IllegalArgumentException) {
            assertTrue(error.message.orEmpty().contains("online-only"))
        }
    }

    @Test
    fun sessionSwitchBetweenPushAndPullStopsBeforeSecondNetworkCallAndCrossUserWrite() = runTest {
        manager.enqueueManualTransactionCreate(
            userId = USER_ID,
            transactionType = "expense",
            amount = "12.34",
            currency = "RUB",
            accountId = "acc-a",
            categoryId = "cat-a",
            transactionDate = "2026-06-14",
            note = "User A pending mutation",
            localTransactionId = ENTITY_ID,
        )
        apiClient.pushHandler = { request ->
            ApiResult.Success(
                SyncPushResponse(
                    deviceId = request.deviceId,
                    serverTime = "2026-06-14T00:00:01Z",
                    results = emptyList(),
                ),
            )
        }
        apiClient.switchUserAfterNextLeaseWrite = "user-b"

        val summary = manager.syncOnce(USER_ID)

        assertTrue(summary.sessionChanged)
        assertEquals(1, apiClient.networkCallCount)
        assertNotNull(apiClient.lastPushRequest)
        assertNull(apiClient.lastPullRequest)
        assertNull(database.localAccountDao().findByServerId(USER_ID, "account-from-user-b"))
        assertTrue(database.pendingMutationDao().pendingForUser(USER_ID).all { it.userId == USER_ID })
    }

    @Test
    fun planningEntitiesAreSyncableForPushAndPull() {
        assertTrue(SyncManager.isSyncableEntityType(SyncManager.ENTITY_PLANNING_PLANS))
        assertTrue(SyncManager.isSyncableEntityType(SyncManager.ENTITY_PLANNING_INCOME_SOURCES))
        assertTrue(SyncManager.isSyncableEntityType(SyncManager.ENTITY_PLANNING_ALLOCATIONS))
        assertTrue(SyncManager.ENTITY_PLANNING_PLANS in SyncManager.SYNC_PULL_ENTITY_TYPES)
        assertTrue(SyncManager.ENTITY_PLANNING_INCOME_SOURCES in SyncManager.SYNC_PULL_ENTITY_TYPES)
        assertTrue(SyncManager.ENTITY_PLANNING_ALLOCATIONS in SyncManager.SYNC_PULL_ENTITY_TYPES)
    }

    @Test
    fun syncIssuesForUserReturnsUiSummaryWithoutPayload() = runTest {
        database.pendingMutationDao().insertIgnoringConflict(
            pendingMutation("failed", USER_ID).copy(
                entityType = SyncManager.ENTITY_ACCOUNTS,
                operation = SyncManager.OPERATION_UPDATE,
                status = SyncManager.MUTATION_STATUS_FAILED,
                attempts = 2,
                lastError = "temporary server error",
                payloadJson = """{"name":"Sensitive Account","balance":"1000.00"}""",
                createdAtEpochMillis = 100,
                updatedAtEpochMillis = 300,
            ),
        )
        database.pendingMutationDao().insertIgnoringConflict(
            pendingMutation("rejected", USER_ID).copy(
                entityType = SyncManager.ENTITY_CATEGORIES,
                operation = SyncManager.OPERATION_DELETE,
                status = SyncManager.MUTATION_STATUS_REJECTED,
                attempts = 1,
                lastError = "version conflict",
                payloadJson = """{"note":"private"}""",
                createdAtEpochMillis = 200,
                updatedAtEpochMillis = 400,
            ),
        )

        val issues = manager.syncIssuesForUser(USER_ID)

        assertEquals(listOf(SyncManager.MUTATION_STATUS_REJECTED, SyncManager.MUTATION_STATUS_FAILED), issues.map { it.status })
        assertEquals(SyncManager.ENTITY_CATEGORIES, issues.first().entityType)
        assertEquals(SyncManager.OPERATION_DELETE, issues.first().operation)
        assertEquals("version conflict", issues.first().lastError)
        assertEquals(1, issues.first().attempts)
        assertTrue(!issues.joinToString().contains("Sensitive Account"))
        assertTrue(!issues.joinToString().contains("1000.00"))
    }

    @Test
    fun pushPurgesOnlineOnlyCaptureMutationWithoutUploadingImagePayload() = runTest {
        val captureMutation = PendingMutationEntity(
            clientMutationId = "capture-mutation-1",
            userId = USER_ID,
            deviceId = "android-test-device",
            entityType = SyncManager.ENTITY_CAPTURE_DRAFTS,
            entityId = ENTITY_ID,
            operation = SyncManager.OPERATION_CREATE,
            baseVersion = null,
            payloadJson = JSONObject()
                .put("imageBytes", "raw-image-bytes-must-not-sync")
                .put("rawOcrText", "raw OCR must not sync")
                .toString(),
            status = SyncManager.MUTATION_STATUS_QUEUED,
            attempts = 0,
            lastError = null,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
        database.pendingMutationDao().insertIgnoringConflict(captureMutation)

        val summary = manager.pushPendingMutations(USER_ID)
        val pending = database.pendingMutationDao().pendingForUser(USER_ID)

        assertEquals(0, summary.pushed)
        assertEquals(1, summary.rejected)
        assertNull(apiClient.lastPushRequest)
        assertEquals(0, pending.size)
    }

    @Test
    fun appliedPushMarksMutationAndLocalTransactionSynced() = runTest {
        manager.enqueueManualTransactionCreate(
            userId = USER_ID,
            transactionType = "expense",
            amount = "12.3400",
            currency = "RUB",
            accountId = "acc-1",
            categoryId = "cat-1",
            transactionDate = "2026-06-14",
            localTransactionId = ENTITY_ID,
        )
        apiClient.pushHandler = { request ->
            val mutation = request.mutations.single()
            ApiResult.Success(
                SyncPushResponse(
                    deviceId = request.deviceId,
                    serverTime = "2026-06-14T00:00:01Z",
                    results = listOf(
                        SyncMutationResult(
                            clientMutationId = mutation.clientMutationId,
                            entityType = mutation.entityType,
                            entityId = mutation.entityId,
                            operation = mutation.operation,
                            status = SyncManager.MUTATION_STATUS_APPLIED,
                            serverVersion = 1,
                            changeSeq = 7,
                            data = JSONObject()
                                .put("id", ENTITY_ID)
                                .put("transactionType", "expense")
                                .put("accountId", "acc-1")
                                .put("categoryId", "cat-1")
                                .put("amount", "12.3400")
                                .put("currency", "RUB")
                                .put("transactionDate", "2026-06-14")
                                .put("description", "Lunch")
                                .put("sourceType", "manual")
                                .put("recordStatus", "active")
                                .put("version", 1),
                        ),
                    ),
                ),
            )
        }

        val summary = manager.pushPendingMutations(USER_ID)
        val request = apiClient.lastPushRequest
        val mutation = database.pendingMutationDao().findByClientMutationId(
            request?.mutations?.single()?.clientMutationId.orEmpty(),
        )
        val local = database.localTransactionDao().findByLocalId(USER_ID, ENTITY_ID)

        assertEquals(1, summary.applied)
        assertNotNull(request)
        assertEquals("transactions", request?.mutations?.single()?.entityType)
        assertEquals(SyncManager.MUTATION_STATUS_APPLIED, mutation?.status)
        assertEquals(SyncManager.SYNC_STATUS_SYNCED, local?.syncStatus)
        assertEquals(1, local?.version)
        assertEquals(ENTITY_ID, local?.serverId)
    }

    @Test
    fun referenceCreatesBuildBackendContractPayloads() = runTest {
        manager.enqueueAccountCreate(
            userId = USER_ID,
            name = "Cash",
            accountType = "cash",
            ownershipType = "personal",
            currency = "RUB",
            initialBalance = "100.0000",
            assetCategoryId = ASSET_CATEGORY_ID,
            localAccountId = ACCOUNT_ID,
        )
        manager.enqueueCategoryCreate(
            userId = USER_ID,
            name = "Food",
            categoryType = "expense",
            scope = "personal",
            iconKey = "utensils",
            color = "#112233",
            localCategoryId = CATEGORY_ID,
        )
        manager.enqueueAssetCategoryCreate(
            userId = USER_ID,
            name = "Brokerage",
            scopeType = "personal",
            currency = "RUB",
            manualAmount = "10.0000",
            isInvestment = true,
            assetType = "brokerage",
            iconKey = "chart",
            localAssetCategoryId = ASSET_CATEGORY_ID,
        )

        val pendingByType = database.pendingMutationDao().pendingForUser(USER_ID).associateBy { it.entityType }
        val accountPayload = JSONObject(pendingByType.getValue(SyncManager.ENTITY_ACCOUNTS).payloadJson.orEmpty())
        val categoryPayload = JSONObject(pendingByType.getValue(SyncManager.ENTITY_CATEGORIES).payloadJson.orEmpty())
        val assetPayload = JSONObject(pendingByType.getValue(SyncManager.ENTITY_ASSET_CATEGORIES).payloadJson.orEmpty())

        assertEquals(3, pendingByType.size)
        assertEquals(SyncManager.OPERATION_CREATE, pendingByType.getValue(SyncManager.ENTITY_ACCOUNTS).operation)
        assertNull(pendingByType.getValue(SyncManager.ENTITY_ACCOUNTS).baseVersion)
        assertEquals("Cash", accountPayload.optString("name"))
        assertEquals("cash", accountPayload.optString("accountType"))
        assertEquals("personal", accountPayload.optString("ownershipType"))
        assertEquals("100.0000", accountPayload.optString("initialBalance"))
        assertEquals(ASSET_CATEGORY_ID, accountPayload.optString("assetCategoryId"))
        assertTrue(accountPayload.optBoolean("isPaymentAccount"))
        assertTrue(pendingByType.getValue(SyncManager.ENTITY_ACCOUNTS).clientMutationId.contains(":accounts:"))

        assertEquals("Food", categoryPayload.optString("name"))
        assertEquals("expense", categoryPayload.optString("type"))
        assertEquals("personal", categoryPayload.optString("scope"))
        assertEquals("utensils", categoryPayload.optString("iconKey"))
        assertEquals("#112233", categoryPayload.optString("color"))

        assertEquals("Brokerage", assetPayload.optString("name"))
        assertEquals("personal", assetPayload.optString("scopeType"))
        assertEquals("10.0000", assetPayload.optString("manualAmount"))
        assertTrue(assetPayload.optBoolean("isInvestment"))
        assertEquals("brokerage", assetPayload.optString("assetType"))
    }

    @Test
    fun investmentMigrationQueuesSingleCommandAndProjectsLocalRows() = runTest {
        val request = InvestmentMigrationCreateRequest(
            assetCategoryId = ASSET_CATEGORY_ID,
            name = "Migrated Investments",
            iconKey = "briefcase",
            color = "#336699",
            assetType = "brokerage",
            currency = "RUB",
            scope = "personal",
            accountIds = listOf(ACCOUNT_ID),
            accountVersions = mapOf(ACCOUNT_ID to 3),
        )
        manager.enqueueInvestmentMigrationCreate(
            userId = USER_ID,
            request = request,
            accounts = listOf(
                AccountSummary(
                    name = "Broker account",
                    type = "brokerage",
                    ownershipType = "personal",
                    currency = "RUB",
                    currentBalance = "1200.0000",
                    id = ACCOUNT_ID,
                    version = 3,
                ),
            ),
        )

        val pending = database.pendingMutationDao().pendingForUser(USER_ID).single()
        val payload = JSONObject(pending.payloadJson.orEmpty())
        val localAssetCategory = database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)
        val localAccount = database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)

        assertEquals(SyncManager.ENTITY_INVESTMENT_MIGRATIONS, pending.entityType)
        assertEquals(ASSET_CATEGORY_ID, pending.entityId)
        assertEquals(SyncManager.OPERATION_CREATE, pending.operation)
        assertTrue(pending.clientMutationId.contains(":investment_migrations:"))
        assertEquals(ASSET_CATEGORY_ID, payload.optString("assetCategoryId"))
        assertEquals("briefcase", payload.optString("icon"))
        assertEquals("#336699", payload.optString("color"))
        assertEquals("brokerage", payload.optString("assetType"))
        assertEquals("personal", payload.optString("scope"))
        assertEquals(ACCOUNT_ID, payload.getJSONArray("accountIds").getString(0))
        assertEquals(3, payload.getJSONObject("accountVersions").getInt(ACCOUNT_ID))
        assertTrue(!payload.has("currentBalance"))
        assertEquals(SyncManager.SYNC_STATUS_PENDING, localAssetCategory?.syncStatus)
        assertTrue(localAssetCategory?.isInvestment == true)
        assertEquals(SyncManager.SYNC_STATUS_PENDING, localAccount?.syncStatus)
        assertEquals(ASSET_CATEGORY_ID, localAccount?.assetCategoryId)
        assertEquals("1200.0000", localAccount?.currentBalance)

        apiClient.pushHandler = { pushRequest ->
            val mutation = pushRequest.mutations.single()
            ApiResult.Success(
                SyncPushResponse(
                    deviceId = pushRequest.deviceId,
                    serverTime = "2026-06-14T00:00:01Z",
                    results = listOf(
                        SyncMutationResult(
                            clientMutationId = mutation.clientMutationId,
                            entityType = mutation.entityType,
                            entityId = mutation.entityId,
                            operation = mutation.operation,
                            status = SyncManager.MUTATION_STATUS_APPLIED,
                            serverVersion = 1,
                            changeSeq = 7,
                            data = JSONObject()
                                .put(
                                    "assetCategory",
                                    JSONObject()
                                        .put("id", ASSET_CATEGORY_ID)
                                        .put("name", "Migrated Investments")
                                        .put("scopeType", "personal")
                                        .put("currency", "RUB")
                                        .put("manualAmount", "0.0000")
                                        .put("isInvestment", true)
                                        .put("assetType", "brokerage")
                                        .put("iconKey", "briefcase")
                                        .put("recordStatus", "active")
                                        .put("version", 1),
                                )
                                .put(
                                    "accounts",
                                    JSONArray().put(
                                        JSONObject()
                                            .put("id", ACCOUNT_ID)
                                            .put("name", "Broker account")
                                            .put("accountType", "brokerage")
                                            .put("ownershipType", "personal")
                                            .put("currency", "RUB")
                                            .put("currentBalance", "1200.0000")
                                            .put("assetCategoryId", ASSET_CATEGORY_ID)
                                            .put("status", "active")
                                            .put("version", 4),
                                    ),
                                ),
                        ),
                    ),
                ),
            )
        }

        val summary = manager.pushPendingMutations(USER_ID)
        val syncedAssetCategory = database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)
        val syncedAccount = database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)

        assertEquals(1, summary.applied)
        assertEquals(SyncManager.SYNC_STATUS_SYNCED, syncedAssetCategory?.syncStatus)
        assertEquals(1, syncedAssetCategory?.version)
        assertEquals(SyncManager.SYNC_STATUS_SYNCED, syncedAccount?.syncStatus)
        assertEquals(4, syncedAccount?.version)
        assertEquals(ASSET_CATEGORY_ID, syncedAccount?.assetCategoryId)
    }

    @Test
    fun planningCreatesBuildBackendContractPayloadsAndUseEntityIds() = runTest {
        manager.enqueuePlanningPlanCreate(
            userId = USER_ID,
            request = PlanningPlanCreateRequest(scope = "personal", month = "2026-07", currency = "RUB"),
            localPlanId = PLAN_ID,
        )
        manager.enqueuePlanningIncomeSourceCreate(
            userId = USER_ID,
            planId = PLAN_ID,
            request = PlanningIncomeSourceCreateRequest(
                amount = "1000.00",
                source = "Salary",
                dayOfMonth = 5,
            ),
            localIncomeSourceId = INCOME_SOURCE_ID,
        )
        manager.enqueuePlanningAllocationCreate(
            userId = USER_ID,
            planId = PLAN_ID,
            request = PlanningAllocationCreateRequest(
                targetType = "expense_category",
                targetId = CATEGORY_ID,
                allocationMode = "amount",
                allocationValue = "400.00",
            ),
            localAllocationId = ALLOCATION_ID,
        )

        val pendingByType = database.pendingMutationDao().pendingForUser(USER_ID).associateBy { it.entityType }
        val planMutation = pendingByType.getValue(SyncManager.ENTITY_PLANNING_PLANS)
        val incomeMutation = pendingByType.getValue(SyncManager.ENTITY_PLANNING_INCOME_SOURCES)
        val allocationMutation = pendingByType.getValue(SyncManager.ENTITY_PLANNING_ALLOCATIONS)
        val planPayload = JSONObject(planMutation.payloadJson.orEmpty())
        val incomePayload = JSONObject(incomeMutation.payloadJson.orEmpty())
        val allocationPayload = JSONObject(allocationMutation.payloadJson.orEmpty())

        assertEquals(PLAN_ID, planMutation.entityId)
        assertEquals(SyncManager.OPERATION_CREATE, planMutation.operation)
        assertNull(planMutation.baseVersion)
        assertEquals("personal", planPayload.optString("scope"))
        assertEquals("2026-07", planPayload.optString("month"))
        assertEquals("RUB", planPayload.optString("currency"))

        assertEquals(INCOME_SOURCE_ID, incomeMutation.entityId)
        assertEquals(SyncManager.OPERATION_CREATE, incomeMutation.operation)
        assertNull(incomeMutation.baseVersion)
        assertEquals(PLAN_ID, incomePayload.optString("planId"))
        assertEquals("1000.00", incomePayload.optString("amount"))
        assertEquals("Salary", incomePayload.optString("source"))
        assertEquals(5, incomePayload.optInt("dayOfMonth"))

        assertEquals(ALLOCATION_ID, allocationMutation.entityId)
        assertEquals(SyncManager.OPERATION_CREATE, allocationMutation.operation)
        assertNull(allocationMutation.baseVersion)
        assertEquals(PLAN_ID, allocationPayload.optString("planId"))
        assertEquals("expense_category", allocationPayload.optString("targetType"))
        assertEquals(CATEGORY_ID, allocationPayload.optString("targetId"))
        assertEquals("amount", allocationPayload.optString("allocationMode"))
        assertEquals("400.00", allocationPayload.optString("allocationValue"))
        assertEquals(SyncManager.SYNC_STATUS_PENDING, database.localPlanningPlanDao().findByLocalId(USER_ID, PLAN_ID)?.syncStatus)
        assertEquals(
            SyncManager.SYNC_STATUS_PENDING,
            database.localPlanningIncomeSourceDao().findByLocalId(USER_ID, INCOME_SOURCE_ID)?.syncStatus,
        )
        assertEquals(
            SyncManager.SYNC_STATUS_PENDING,
            database.localPlanningAllocationDao().findByLocalId(USER_ID, ALLOCATION_ID)?.syncStatus,
        )
    }

    @Test
    fun accountUpdateRequiresBaseVersionAndDoesNotQueueCurrentBalanceChange() = runTest {
        database.localAccountDao().upsert(localAccount(ACCOUNT_ID, USER_ID))

        val mutation = manager.enqueueAccountUpdate(
            userId = USER_ID,
            entityId = ACCOUNT_ID,
            baseVersion = 3,
            name = "Wallet",
            assetCategoryId = ASSET_CATEGORY_ID,
            isPaymentAccount = false,
        )
        val balanceMutation = manager.enqueueAccountUpdate(
            userId = USER_ID,
            entityId = ACCOUNT_ID,
            baseVersion = 3,
            currentBalance = "999.0000",
        )
        val pending = database.pendingMutationDao().pendingForUser(USER_ID)
        val payload = JSONObject(mutation?.payloadJson.orEmpty())
        val local = database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)

        assertNotNull(mutation)
        assertNull(balanceMutation)
        assertEquals(1, pending.size)
        assertEquals(SyncManager.ENTITY_ACCOUNTS, mutation?.entityType)
        assertEquals(SyncManager.OPERATION_UPDATE, mutation?.operation)
        assertEquals(3, mutation?.baseVersion)
        assertEquals(3, payload.optInt("version"))
        assertEquals("Wallet", payload.optString("name"))
        assertEquals(ASSET_CATEGORY_ID, payload.optString("assetCategoryId"))
        assertEquals(false, payload.optBoolean("isPaymentAccount"))
        assertTrue(!payload.has("currentBalance"))
        assertEquals("0", local?.currentBalance)
        assertEquals(SyncManager.SYNC_STATUS_PENDING, local?.syncStatus)
    }

    @Test
    fun archiveRestoreDeleteMutationsCarryBaseVersionWithoutPayload() = runTest {
        database.localAccountDao().upsert(localAccount(ACCOUNT_ID, USER_ID))
        database.localCategoryDao().upsert(localCategory(CATEGORY_ID, USER_ID).copy(recordStatus = SyncManager.RECORD_STATUS_ARCHIVED))
        database.localAssetCategoryDao().upsert(localAssetCategory(ASSET_CATEGORY_ID, USER_ID))

        manager.enqueueAccountArchive(USER_ID, ACCOUNT_ID, baseVersion = 4)
        manager.enqueueCategoryRestore(USER_ID, CATEGORY_ID, baseVersion = 5)
        manager.enqueueAssetCategoryDelete(USER_ID, ASSET_CATEGORY_ID, baseVersion = 6)

        val pending = database.pendingMutationDao().pendingForUser(USER_ID)
        val accountMutation = pending.single { it.entityType == SyncManager.ENTITY_ACCOUNTS }
        val categoryMutation = pending.single { it.entityType == SyncManager.ENTITY_CATEGORIES }
        val assetMutation = pending.single { it.entityType == SyncManager.ENTITY_ASSET_CATEGORIES }

        assertEquals(SyncManager.OPERATION_ARCHIVE, accountMutation.operation)
        assertEquals(4, accountMutation.baseVersion)
        assertNull(accountMutation.payloadJson)
        assertEquals(SyncManager.RECORD_STATUS_ARCHIVED, database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)?.recordStatus)

        assertEquals(SyncManager.OPERATION_RESTORE, categoryMutation.operation)
        assertEquals(5, categoryMutation.baseVersion)
        assertNull(categoryMutation.payloadJson)
        assertEquals(SyncManager.RECORD_STATUS_ACTIVE, database.localCategoryDao().findByServerId(USER_ID, CATEGORY_ID)?.recordStatus)

        assertEquals(SyncManager.OPERATION_DELETE, assetMutation.operation)
        assertEquals(6, assetMutation.baseVersion)
        assertNull(assetMutation.payloadJson)
        assertEquals(
            SyncManager.RECORD_STATUS_DELETED,
            database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)?.recordStatus,
        )
    }

    @Test
    fun planningUpdateConfirmAndDeleteMutationsCarryBaseVersion() = runTest {
        database.localPlanningPlanDao().upsert(localPlanningPlan(PLAN_ID, USER_ID))
        database.localPlanningIncomeSourceDao().upsert(localPlanningIncomeSource(INCOME_SOURCE_ID, USER_ID, PLAN_ID).copy(version = 2))
        database.localPlanningAllocationDao().upsert(localPlanningAllocation(ALLOCATION_ID, USER_ID, PLAN_ID).copy(version = 3))

        val sourceUpdate = manager.enqueuePlanningIncomeSourceUpdate(
            userId = USER_ID,
            entityId = INCOME_SOURCE_ID,
            baseVersion = 2,
            request = PlanningIncomeSourceUpdateRequest(amount = "1200.00"),
        )
        val sourceConfirm = manager.enqueuePlanningIncomeSourceConfirm(
            userId = USER_ID,
            entityId = INCOME_SOURCE_ID,
            baseVersion = 2,
        )
        val allocationUpdate = manager.enqueuePlanningAllocationUpdate(
            userId = USER_ID,
            entityId = ALLOCATION_ID,
            baseVersion = 3,
            request = PlanningAllocationUpdateRequest(allocationValue = "450.00"),
        )
        val allocationDelete = manager.enqueuePlanningAllocationDelete(
            userId = USER_ID,
            entityId = ALLOCATION_ID,
            baseVersion = 3,
        )

        assertEquals(2, sourceUpdate.baseVersion)
        assertEquals(2, JSONObject(sourceUpdate.payloadJson.orEmpty()).optInt("version"))
        assertEquals("1200.00", JSONObject(sourceUpdate.payloadJson.orEmpty()).optString("amount"))
        assertEquals(SyncManager.OPERATION_CONFIRM, sourceConfirm.operation)
        assertEquals(2, sourceConfirm.baseVersion)
        assertEquals(2, JSONObject(sourceConfirm.payloadJson.orEmpty()).optInt("version"))
        assertEquals(3, allocationUpdate.baseVersion)
        assertEquals(3, JSONObject(allocationUpdate.payloadJson.orEmpty()).optInt("version"))
        assertEquals("450.00", JSONObject(allocationUpdate.payloadJson.orEmpty()).optString("allocationValue"))
        assertEquals(SyncManager.OPERATION_DELETE, allocationDelete.operation)
        assertEquals(3, allocationDelete.baseVersion)
        assertNull(allocationDelete.payloadJson)
        assertEquals(
            SyncManager.SYNC_STATUS_PENDING,
            database.localPlanningIncomeSourceDao().findByServerId(USER_ID, INCOME_SOURCE_ID)?.syncStatus,
        )
        assertEquals(
            SyncManager.RECORD_STATUS_DELETED,
            database.localPlanningAllocationDao().findByServerId(USER_ID, ALLOCATION_ID)?.recordStatus,
        )
    }

    @Test
    fun appliedPushMarksReferenceEntitiesSynced() = runTest {
        database.localAccountDao().upsert(localAccount(ACCOUNT_ID, USER_ID))
        database.localCategoryDao().upsert(localCategory(CATEGORY_ID, USER_ID))
        database.localAssetCategoryDao().upsert(localAssetCategory(ASSET_CATEGORY_ID, USER_ID))
        manager.enqueueAccountUpdate(USER_ID, ACCOUNT_ID, baseVersion = 1, name = "Wallet")
        manager.enqueueCategoryUpdate(USER_ID, CATEGORY_ID, baseVersion = 1, name = "Groceries")
        manager.enqueueAssetCategoryUpdate(USER_ID, ASSET_CATEGORY_ID, baseVersion = 1, manualAmount = "25.0000")
        apiClient.pushHandler = { request ->
            ApiResult.Success(
                SyncPushResponse(
                    deviceId = request.deviceId,
                    serverTime = "2026-06-14T00:00:01Z",
                    results = request.mutations.map { mutation ->
                        SyncMutationResult(
                            clientMutationId = mutation.clientMutationId,
                            entityType = mutation.entityType,
                            entityId = mutation.entityId,
                            operation = mutation.operation,
                            status = SyncManager.MUTATION_STATUS_APPLIED,
                            serverVersion = 2,
                            changeSeq = 10,
                            data = when (mutation.entityType) {
                                SyncManager.ENTITY_ACCOUNTS -> JSONObject()
                                    .put("id", ACCOUNT_ID)
                                    .put("name", "Wallet")
                                    .put("accountType", "cash")
                                    .put("ownershipType", "personal")
                                    .put("currency", "RUB")
                                    .put("currentBalance", "0")
                                    .put("assetCategoryId", JSONObject.NULL)
                                    .put("isPaymentAccount", true)
                                    .put("status", "active")
                                    .put("version", 2)
                                SyncManager.ENTITY_CATEGORIES -> JSONObject()
                                    .put("id", CATEGORY_ID)
                                    .put("name", "Groceries")
                                    .put("type", "expense")
                                    .put("scope", "personal")
                                    .put("status", "active")
                                    .put("version", 2)
                                else -> JSONObject()
                                    .put("id", ASSET_CATEGORY_ID)
                                    .put("name", "Brokerage")
                                    .put("scopeType", "personal")
                                    .put("ownerUserId", USER_ID)
                                    .put("currency", "RUB")
                                    .put("manualAmount", "25.0000")
                                    .put("isInvestment", true)
                                    .put("assetType", "brokerage")
                                    .put("recordStatus", "active")
                                    .put("version", 2)
                            },
                        )
                    },
                ),
            )
        }

        val summary = manager.pushPendingMutations(USER_ID)

        assertEquals(3, summary.applied)
        assertEquals("Wallet", database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)?.name)
        assertEquals(SyncManager.SYNC_STATUS_SYNCED, database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)?.syncStatus)
        assertEquals(2, database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)?.version)
        assertEquals("Groceries", database.localCategoryDao().findByServerId(USER_ID, CATEGORY_ID)?.name)
        assertEquals(SyncManager.SYNC_STATUS_SYNCED, database.localCategoryDao().findByServerId(USER_ID, CATEGORY_ID)?.syncStatus)
        assertEquals("25.0000", database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)?.manualAmount)
        assertEquals(SyncManager.SYNC_STATUS_SYNCED, database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)?.syncStatus)
        assertTrue(apiClient.lastPushRequest?.mutations.orEmpty().all { it.baseVersion == 1 })
    }

    @Test
    fun rejectedReferencePushMarksMutationRejected() = runTest {
        database.localCategoryDao().upsert(localCategory(CATEGORY_ID, USER_ID))
        val queued = manager.enqueueCategoryUpdate(USER_ID, CATEGORY_ID, baseVersion = 1, name = "Groceries")
        apiClient.pushHandler = { request ->
            val mutation = request.mutations.single()
            ApiResult.Success(
                SyncPushResponse(
                    deviceId = request.deviceId,
                    serverTime = "2026-06-14T00:00:01Z",
                    results = listOf(
                        SyncMutationResult(
                            clientMutationId = mutation.clientMutationId,
                            entityType = mutation.entityType,
                            entityId = mutation.entityId,
                            operation = mutation.operation,
                            status = SyncManager.MUTATION_STATUS_REJECTED,
                            errorCode = "CONFLICTING_UPDATE",
                            message = "Conflicting update.",
                        ),
                    ),
                ),
            )
        }

        val summary = manager.pushPendingMutations(USER_ID)
        val mutation = database.pendingMutationDao().findByClientMutationId(queued.clientMutationId)

        assertEquals(1, summary.rejected)
        assertEquals(SyncManager.MUTATION_STATUS_REJECTED, mutation?.status)
        assertEquals("CONFLICTING_UPDATE", mutation?.lastError)
    }

    @Test
    fun rejectedPlanningConflictMarksMutationRejected() = runTest {
        database.localPlanningPlanDao().upsert(localPlanningPlan(PLAN_ID, USER_ID))
        database.localPlanningAllocationDao().upsert(localPlanningAllocation(ALLOCATION_ID, USER_ID, PLAN_ID))
        val queued = manager.enqueuePlanningAllocationUpdate(
            userId = USER_ID,
            entityId = ALLOCATION_ID,
            baseVersion = 1,
            request = PlanningAllocationUpdateRequest(allocationValue = "450.00"),
        )
        apiClient.pushHandler = { request ->
            val mutation = request.mutations.single()
            ApiResult.Success(
                SyncPushResponse(
                    deviceId = request.deviceId,
                    serverTime = "2026-06-14T00:00:01Z",
                    results = listOf(
                        SyncMutationResult(
                            clientMutationId = mutation.clientMutationId,
                            entityType = mutation.entityType,
                            entityId = mutation.entityId,
                            operation = mutation.operation,
                            status = SyncManager.MUTATION_STATUS_REJECTED,
                            errorCode = "CONFLICTING_UPDATE",
                            message = "Conflicting update.",
                        ),
                    ),
                ),
            )
        }

        val summary = manager.pushPendingMutations(USER_ID)
        val mutation = database.pendingMutationDao().findByClientMutationId(queued.clientMutationId)

        assertEquals(1, summary.rejected)
        assertEquals(SyncManager.MUTATION_STATUS_REJECTED, mutation?.status)
        assertEquals("CONFLICTING_UPDATE", mutation?.lastError)
    }

    @Test
    fun failedNetworkPushMarksMutationForRetry() = runTest {
        manager.enqueueManualTransactionCreate(
            userId = USER_ID,
            transactionType = "expense",
            amount = "12.3400",
            currency = "RUB",
            accountId = "acc-1",
            transactionDate = "2026-06-14",
            localTransactionId = ENTITY_ID,
        )
        apiClient.pushHandler = {
            ApiResult.Failure("temporarily unavailable", statusCode = 503)
        }

        val summary = manager.pushPendingMutations(USER_ID)
        val pending = database.pendingMutationDao().pendingForUser(
            userId = USER_ID,
            statuses = listOf(SyncManager.MUTATION_STATUS_RETRY),
        )

        assertEquals(1, summary.retry)
        assertEquals(1, pending.size)
        assertEquals(1, pending.single().attempts)
    }

    @Test
    fun clearUserDataCleansAllLocalTablesForUser() = runTest {
        database.localTransactionDao().upsert(localTransaction("tx-1", USER_ID))
        database.localTransactionDao().upsert(localTransaction("tx-2", "other-user"))
        database.localAccountDao().upsert(localAccount("acc-1", USER_ID))
        database.localAccountDao().upsert(localAccount("acc-2", "other-user"))
        database.localCategoryDao().upsert(localCategory("cat-1", USER_ID))
        database.localCategoryDao().upsert(localCategory("cat-2", "other-user"))
        database.localAssetCategoryDao().upsert(localAssetCategory("asset-1", USER_ID))
        database.localAssetCategoryDao().upsert(localAssetCategory("asset-2", "other-user"))
        database.localPlanningPlanDao().upsert(localPlanningPlan(PLAN_ID, USER_ID))
        database.localPlanningPlanDao().upsert(localPlanningPlan("plan-other", "other-user"))
        database.localPlanningIncomeSourceDao().upsert(localPlanningIncomeSource(INCOME_SOURCE_ID, USER_ID, PLAN_ID))
        database.localPlanningIncomeSourceDao().upsert(localPlanningIncomeSource("income-other", "other-user", "plan-other"))
        database.localPlanningAllocationDao().upsert(localPlanningAllocation(ALLOCATION_ID, USER_ID, PLAN_ID))
        database.localPlanningAllocationDao().upsert(localPlanningAllocation("allocation-other", "other-user", "plan-other"))
        database.pendingMutationDao().insertIgnoringConflict(pendingMutation("mutation-1", USER_ID))
        database.pendingMutationDao().insertIgnoringConflict(pendingMutation("mutation-2", "other-user"))
        database.syncStateDao().upsert(
            com.finance.mvp.local.SyncStateEntity(USER_ID, "android-test-device", 9, "2026-06-14T00:00:00Z", 100),
        )

        manager.clearUserData(USER_ID)

        assertEquals(0, database.localTransactionDao().latestForUser(USER_ID).size)
        assertEquals(0, database.localAccountDao().listForUser(USER_ID).size)
        assertEquals(0, database.localCategoryDao().listForUser(USER_ID).size)
        assertEquals(0, database.localAssetCategoryDao().listForUser(USER_ID).size)
        assertEquals(0, database.localPlanningPlanDao().listForUser(USER_ID).size)
        assertEquals(0, database.localPlanningIncomeSourceDao().listForUser(USER_ID).size)
        assertEquals(0, database.localPlanningAllocationDao().listForUser(USER_ID).size)
        assertEquals(0, database.pendingMutationDao().pendingForUser(USER_ID).size)
        assertEquals(null, database.syncStateDao().find(USER_ID, "android-test-device"))
        assertEquals(1, database.localTransactionDao().latestForUser("other-user").size)
        assertEquals(1, database.localAccountDao().listForUser("other-user").size)
        assertEquals(1, database.localCategoryDao().listForUser("other-user").size)
        assertEquals(1, database.localAssetCategoryDao().listForUser("other-user").size)
        assertEquals(1, database.localPlanningPlanDao().listForUser("other-user").size)
        assertEquals(1, database.localPlanningIncomeSourceDao().listForUser("other-user").size)
        assertEquals(1, database.localPlanningAllocationDao().listForUser("other-user").size)
        assertEquals(1, database.pendingMutationDao().pendingForUser("other-user").size)
    }

    @Test
    fun pullAppliesAccountCategoryAndAssetCategoryPayloads() = runTest {
        apiClient.pullHandler = {
            ApiResult.Success(
                SyncPullResponse(
                    changes = listOf(
                        syncChange(
                            entityType = SyncManager.ENTITY_ACCOUNTS,
                            entityId = ACCOUNT_ID,
                            payload = JSONObject()
                                .put("id", ACCOUNT_ID)
                                .put("name", "Cash")
                                .put("accountType", "cash")
                                .put("ownershipType", "personal")
                                .put("currency", "RUB")
                                .put("currentBalance", "100.00")
                                .put("isPaymentAccount", true)
                                .put("status", "active")
                                .put("version", 3),
                        ),
                        syncChange(
                            seq = 2,
                            entityType = SyncManager.ENTITY_CATEGORIES,
                            entityId = CATEGORY_ID,
                            payload = JSONObject()
                                .put("id", CATEGORY_ID)
                                .put("name", "Food")
                                .put("type", "expense")
                                .put("scope", "personal")
                                .put("iconKey", "utensils")
                                .put("color", "#112233")
                                .put("status", "active")
                                .put("version", 4),
                        ),
                        syncChange(
                            seq = 3,
                            entityType = SyncManager.ENTITY_ASSET_CATEGORIES,
                            entityId = ASSET_CATEGORY_ID,
                            payload = JSONObject()
                                .put("id", ASSET_CATEGORY_ID)
                                .put("name", "Brokerage")
                                .put("scopeType", "personal")
                                .put("ownerUserId", USER_ID)
                                .put("currency", "RUB")
                                .put("manualAmount", "10.00")
                                .put("isInvestment", true)
                                .put("assetType", "brokerage")
                                .put("iconKey", "chart")
                                .put("recordStatus", "active")
                                .put("version", 5),
                        ),
                    ),
                    nextCursor = 3,
                    hasMore = false,
                    serverTime = "2026-06-14T00:00:00Z",
                ),
            )
        }

        manager.pullAndApply(USER_ID)

        assertEquals(SyncManager.SYNC_PULL_ENTITY_TYPES, apiClient.lastPullRequest?.entityTypes)
        assertEquals("Cash", database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)?.name)
        assertEquals("Food", database.localCategoryDao().findByServerId(USER_ID, CATEGORY_ID)?.name)
        val assetCategory = database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)
        assertEquals("Brokerage", assetCategory?.name)
        assertTrue(assetCategory?.isInvestment == true)
        assertEquals(3L, database.syncStateDao().find(USER_ID, "android-test-device")?.serverCursor)
    }

    @Test
    fun pullAppliesPlanningPayloadsWithChildren() = runTest {
        manager.applyPullChanges(
            userId = USER_ID,
            response = SyncPullResponse(
                changes = listOf(
                    syncChange(
                        entityType = SyncManager.ENTITY_PLANNING_PLANS,
                        entityId = PLAN_ID,
                        payload = JSONObject()
                            .put("id", PLAN_ID)
                            .put("scope", "personal")
                            .put("month", "2026-07")
                            .put("currency", "RUB")
                            .put("summary", JSONObject().put("totalPlannedIncome", "1000.00").put("totalAllocatedAmount", "400.00"))
                            .put("incomeSources", JSONArray().put(planningIncomePayload()))
                            .put("allocations", JSONArray().put(planningAllocationPayload())),
                    ),
                ),
                nextCursor = 1,
                hasMore = false,
                serverTime = "2026-06-14T00:00:00Z",
            ),
        )

        val plan = database.localPlanningPlanDao().findByServerId(USER_ID, PLAN_ID)
        val income = database.localPlanningIncomeSourceDao().findByServerId(USER_ID, INCOME_SOURCE_ID)
        val allocation = database.localPlanningAllocationDao().findByServerId(USER_ID, ALLOCATION_ID)

        assertEquals("1000.00", plan?.totalPlannedIncome)
        assertEquals("400.00", plan?.allocatedTotal)
        assertEquals("Salary", income?.source)
        assertEquals(PLAN_ID, income?.planServerId)
        assertEquals("expense_category", allocation?.targetType)
        assertEquals(CATEGORY_ID, allocation?.targetId)
        assertEquals(PLAN_ID, allocation?.planServerId)
    }

    @Test
    fun pullTombstonesMarkReferenceRowsDeleted() = runTest {
        database.localAccountDao().upsert(localAccount(ACCOUNT_ID, USER_ID))
        database.localCategoryDao().upsert(localCategory(CATEGORY_ID, USER_ID))

        manager.applyPullChanges(
            userId = USER_ID,
            response = SyncPullResponse(
                changes = listOf(
                    syncChange(
                        entityType = SyncManager.ENTITY_ACCOUNTS,
                        entityId = ACCOUNT_ID,
                        changeType = SyncManager.OPERATION_DELETE,
                        entityVersion = 6,
                        payload = null,
                        tombstonePayload = JSONObject().put("id", ACCOUNT_ID).put("version", 6),
                    ),
                    syncChange(
                        seq = 2,
                        entityType = SyncManager.ENTITY_CATEGORIES,
                        entityId = CATEGORY_ID,
                        changeType = SyncManager.OPERATION_DELETE,
                        entityVersion = 7,
                        payload = null,
                        tombstonePayload = JSONObject().put("id", CATEGORY_ID).put("version", 7),
                    ),
                    syncChange(
                        seq = 3,
                        entityType = SyncManager.ENTITY_ASSET_CATEGORIES,
                        entityId = ASSET_CATEGORY_ID,
                        changeType = SyncManager.OPERATION_DELETE,
                        entityVersion = 8,
                        payload = null,
                        tombstonePayload = JSONObject()
                            .put("id", ASSET_CATEGORY_ID)
                            .put("name", "Deleted asset")
                            .put("version", 8),
                    ),
                ),
                nextCursor = 3,
                hasMore = false,
                serverTime = "2026-06-14T00:00:00Z",
            ),
        )

        val account = database.localAccountDao().findByServerId(USER_ID, ACCOUNT_ID)
        val category = database.localCategoryDao().findByServerId(USER_ID, CATEGORY_ID)
        val assetCategory = database.localAssetCategoryDao().findByServerId(USER_ID, ASSET_CATEGORY_ID)

        assertEquals(SyncManager.RECORD_STATUS_DELETED, account?.recordStatus)
        assertEquals(6, account?.version)
        assertEquals(SyncManager.RECORD_STATUS_DELETED, category?.recordStatus)
        assertEquals(7, category?.version)
        assertEquals(SyncManager.RECORD_STATUS_DELETED, assetCategory?.recordStatus)
        assertEquals("Deleted asset", assetCategory?.name)
        assertEquals(8, assetCategory?.version)
    }

    @Test
    fun pullTombstonesMarkPlanningRowsDeleted() = runTest {
        database.localPlanningPlanDao().upsert(localPlanningPlan(PLAN_ID, USER_ID))
        database.localPlanningIncomeSourceDao().upsert(localPlanningIncomeSource(INCOME_SOURCE_ID, USER_ID, PLAN_ID))
        database.localPlanningAllocationDao().upsert(localPlanningAllocation(ALLOCATION_ID, USER_ID, PLAN_ID))

        manager.applyPullChanges(
            userId = USER_ID,
            response = SyncPullResponse(
                changes = listOf(
                    syncChange(
                        entityType = SyncManager.ENTITY_PLANNING_PLANS,
                        entityId = PLAN_ID,
                        changeType = SyncManager.OPERATION_DELETE,
                        entityVersion = 4,
                        payload = null,
                        tombstonePayload = JSONObject().put("id", PLAN_ID).put("version", 4),
                    ),
                    syncChange(
                        seq = 2,
                        entityType = SyncManager.ENTITY_PLANNING_INCOME_SOURCES,
                        entityId = INCOME_SOURCE_ID,
                        changeType = SyncManager.OPERATION_DELETE,
                        entityVersion = 5,
                        payload = null,
                        tombstonePayload = JSONObject().put("id", INCOME_SOURCE_ID).put("planId", PLAN_ID).put("version", 5),
                    ),
                    syncChange(
                        seq = 3,
                        entityType = SyncManager.ENTITY_PLANNING_ALLOCATIONS,
                        entityId = ALLOCATION_ID,
                        changeType = SyncManager.OPERATION_DELETE,
                        entityVersion = 6,
                        payload = null,
                        tombstonePayload = JSONObject().put("id", ALLOCATION_ID).put("planId", PLAN_ID).put("version", 6),
                    ),
                ),
                nextCursor = 3,
                hasMore = false,
                serverTime = "2026-06-14T00:00:00Z",
            ),
        )

        val plan = database.localPlanningPlanDao().findByServerId(USER_ID, PLAN_ID)
        val income = database.localPlanningIncomeSourceDao().findByServerId(USER_ID, INCOME_SOURCE_ID)
        val allocation = database.localPlanningAllocationDao().findByServerId(USER_ID, ALLOCATION_ID)

        assertEquals(SyncManager.RECORD_STATUS_DELETED, plan?.recordStatus)
        assertEquals(4, plan?.version)
        assertEquals(SyncManager.RECORD_STATUS_DELETED, income?.recordStatus)
        assertEquals(5, income?.version)
        assertEquals(SyncManager.RECORD_STATUS_DELETED, allocation?.recordStatus)
        assertEquals(6, allocation?.version)
    }

    private fun syncChange(
        seq: Long = 1,
        entityType: String,
        entityId: String,
        changeType: String = SyncManager.OPERATION_UPDATE,
        entityVersion: Int? = null,
        payload: JSONObject?,
        tombstonePayload: JSONObject? = null,
    ): SyncChange {
        return SyncChange(
            seq = seq,
            entityType = entityType,
            entityId = entityId,
            changeType = changeType,
            entityVersion = entityVersion,
            payload = payload,
            tombstonePayload = tombstonePayload,
            createdAt = "2026-06-14T00:00:00Z",
        )
    }

    private fun planningIncomePayload(): JSONObject {
        return JSONObject()
            .put("id", INCOME_SOURCE_ID)
            .put("planId", PLAN_ID)
            .put("amount", "1000.00")
            .put("source", "Salary")
            .put("dayOfMonth", 5)
            .put("confirmed", false)
            .put("version", 2)
    }

    private fun planningAllocationPayload(): JSONObject {
        return JSONObject()
            .put("id", ALLOCATION_ID)
            .put("planId", PLAN_ID)
            .put("targetType", "expense_category")
            .put("targetId", CATEGORY_ID)
            .put("allocationMode", "amount")
            .put("allocationValue", "400.00")
            .put("calculatedAmount", "400.00")
            .put("requiresAttention", false)
            .put("version", 2)
    }

    private fun localTransaction(id: String, userId: String): LocalTransactionEntity {
        return LocalTransactionEntity(
            localId = id,
            userId = userId,
            serverId = id,
            transactionType = "expense",
            amount = "1.00",
            currency = "RUB",
            accountId = "acc-1",
            categoryId = null,
            counterpartyAccountId = null,
            transactionDate = "2026-06-14",
            occurredAt = null,
            note = null,
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun localAccount(id: String, userId: String): LocalAccountEntity {
        return LocalAccountEntity(
            localId = id,
            userId = userId,
            serverId = id,
            name = "Cash",
            accountType = "cash",
            ownershipType = "personal",
            currency = "RUB",
            currentBalance = "0",
            householdId = null,
            assetCategoryId = null,
            isPaymentAccount = true,
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun localCategory(id: String, userId: String): LocalCategoryEntity {
        return LocalCategoryEntity(
            localId = id,
            userId = userId,
            serverId = id,
            name = "Food",
            categoryType = "expense",
            scope = "personal",
            householdId = null,
            iconKey = "",
            color = "",
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun localAssetCategory(id: String, userId: String): LocalAssetCategoryEntity {
        return LocalAssetCategoryEntity(
            localId = id,
            userId = userId,
            serverId = id,
            name = "Brokerage",
            scopeType = "personal",
            householdId = null,
            ownerUserId = userId,
            currency = "RUB",
            manualAmount = "0",
            isInvestment = true,
            assetType = "brokerage",
            iconKey = "",
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun localPlanningPlan(id: String, userId: String): LocalPlanningPlanEntity {
        return LocalPlanningPlanEntity(
            localId = id,
            userId = userId,
            serverId = id,
            scope = "personal",
            month = "2026-07",
            currency = "RUB",
            householdId = null,
            totalPlannedIncome = "0",
            previousMonthSurplus = "0",
            allocatedTotal = "0",
            remainingAmount = "0",
            overallocatedAmount = "0",
            isUnderallocated = false,
            isOverallocated = false,
            status = null,
            progressStatus = null,
            progressPercent = null,
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun localPlanningIncomeSource(id: String, userId: String, planId: String): LocalPlanningIncomeSourceEntity {
        return LocalPlanningIncomeSourceEntity(
            localId = id,
            userId = userId,
            serverId = id,
            planLocalId = planId,
            planServerId = planId,
            amount = "100.00",
            source = "Salary",
            description = null,
            dayOfMonth = 5,
            confirmed = false,
            effectiveDate = null,
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun localPlanningAllocation(id: String, userId: String, planId: String): LocalPlanningAllocationEntity {
        return LocalPlanningAllocationEntity(
            localId = id,
            userId = userId,
            serverId = id,
            planLocalId = planId,
            planServerId = planId,
            targetType = "expense_category",
            targetId = CATEGORY_ID,
            targetSnapshot = null,
            requiresAttention = false,
            attentionReason = null,
            comment = null,
            allocationMode = "amount",
            allocationValue = "50.00",
            calculatedAmount = "50.00",
            recurrenceType = "regular",
            isSavingsGoal = false,
            goalTargetAmount = null,
            goalDueMonth = null,
            goalMonthlyAmount = null,
            actualAmount = null,
            varianceAmount = null,
            progressPercent = null,
            progressStatus = null,
            status = null,
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = SyncManager.RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private fun pendingMutation(id: String, userId: String): PendingMutationEntity {
        return PendingMutationEntity(
            clientMutationId = id,
            userId = userId,
            deviceId = "android-test-device",
            entityType = SyncManager.ENTITY_TRANSACTIONS,
            entityId = ENTITY_ID,
            operation = SyncManager.OPERATION_CREATE,
            baseVersion = null,
            payloadJson = "{}",
            status = SyncManager.MUTATION_STATUS_QUEUED,
            attempts = 0,
            lastError = null,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
        )
    }

    private class FakeSyncApiClient : SyncApiClient {
        var lastPushRequest: SyncPushRequest? = null
        var lastPullRequest: SyncPullRequest? = null
        var pushHandler: suspend (SyncPushRequest) -> ApiResult<SyncPushResponse> = {
            ApiResult.Success(SyncPushResponse(it.deviceId, "2026-06-14T00:00:00Z", emptyList()))
        }
        var pullHandler: suspend (SyncPullRequest) -> ApiResult<SyncPullResponse> = {
            ApiResult.Success(
                SyncPullResponse(
                    changes = emptyList(),
                    nextCursor = it.cursor,
                    hasMore = false,
                    serverTime = "2026-06-14T00:00:00Z",
                ),
            )
        }
        var currentAuthenticatedUserId: String = USER_ID
        var switchUserAfterNextLeaseWrite: String? = null
        var networkCallCount: Int = 0
            private set
        private var boundUserId: String? = null

        override suspend fun bindSession(userId: String): ApiResult<SyncApiClient> {
            return if (currentAuthenticatedUserId == userId) {
                boundUserId = userId
                ApiResult.Success(this)
            } else {
                sessionChangedFailure()
            }
        }

        override suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> {
            if (!boundSessionIsCurrent()) return sessionChangedFailure()
            networkCallCount += 1
            lastPushRequest = request
            return pushHandler(request)
        }

        override suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> {
            if (!boundSessionIsCurrent()) return sessionChangedFailure()
            networkCallCount += 1
            lastPullRequest = request
            return pullHandler(request)
        }

        override suspend fun <T> withSessionLease(block: suspend () -> T): ApiResult<T> {
            if (!boundSessionIsCurrent()) return sessionChangedFailure()
            val value = block()
            switchUserAfterNextLeaseWrite?.let {
                currentAuthenticatedUserId = it
                switchUserAfterNextLeaseWrite = null
            }
            return ApiResult.Success(value)
        }

        private fun boundSessionIsCurrent(): Boolean {
            return boundUserId == null || boundUserId == currentAuthenticatedUserId
        }

        private fun sessionChangedFailure(): ApiResult.Failure = ApiResult.Failure(
            "session changed",
            kind = ApiFailureKind.SESSION_CHANGED,
        )
    }

    private companion object {
        const val USER_ID = "user-1"
        const val ENTITY_ID = "11111111-1111-4111-8111-111111111111"
        const val ACCOUNT_ID = "22222222-2222-4222-8222-222222222222"
        const val CATEGORY_ID = "33333333-3333-4333-8333-333333333333"
        const val ASSET_CATEGORY_ID = "44444444-4444-4444-8444-444444444444"
        const val PLAN_ID = "55555555-5555-4555-8555-555555555555"
        const val INCOME_SOURCE_ID = "66666666-6666-4666-8666-666666666666"
        const val ALLOCATION_ID = "77777777-7777-4777-8777-777777777777"
    }
}
