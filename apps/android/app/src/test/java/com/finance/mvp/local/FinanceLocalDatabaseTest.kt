package com.finance.mvp.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.finance.mvp.sync.SyncManager
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class FinanceLocalDatabaseTest {
    private lateinit var database: FinanceLocalDatabase

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, FinanceLocalDatabase::class.java)
            .allowMainThreadQueries()
            .build()
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun pendingMutationsAreReturnedInCreationOrder() = runTest {
        val dao = database.pendingMutationDao()
        dao.insertIgnoringConflict(mutation("second", createdAt = 200))
        dao.insertIgnoringConflict(mutation("first", createdAt = 100))
        dao.insertIgnoringConflict(mutation("applied", createdAt = 50, status = SyncManager.MUTATION_STATUS_APPLIED))

        val pending = dao.pendingForUser(userId = USER_ID)

        assertEquals(listOf("first", "second"), pending.map { it.clientMutationId })
    }

    @Test
    fun pendingMutationCountAndDeleteAreScopedToUser() = runTest {
        val dao = database.pendingMutationDao()
        dao.insertIgnoringConflict(mutation("queued", createdAt = 100))
        dao.insertIgnoringConflict(mutation("retry", createdAt = 200, status = SyncManager.MUTATION_STATUS_RETRY))
        dao.insertIgnoringConflict(mutation("failed", createdAt = 300, status = SyncManager.MUTATION_STATUS_FAILED))
        dao.insertIgnoringConflict(mutation("other-user", createdAt = 400, userId = "other-user"))

        val pendingCount = dao.countForUser(
            userId = USER_ID,
            statuses = listOf(SyncManager.MUTATION_STATUS_QUEUED, SyncManager.MUTATION_STATUS_RETRY),
        )
        val failedCount = dao.countForUser(
            userId = USER_ID,
            statuses = listOf(SyncManager.MUTATION_STATUS_FAILED),
        )

        assertEquals(2, pendingCount)
        assertEquals(1, failedCount)

        dao.deleteForUser(USER_ID)

        assertEquals(0, dao.pendingForUser(USER_ID).size)
        assertEquals(1, dao.pendingForUser("other-user").size)
    }

    @Test
    fun syncIssuesAreScopedAndReturnedNewestFirst() = runTest {
        val dao = database.pendingMutationDao()
        dao.insertIgnoringConflict(
            mutation(
                "old-failed",
                createdAt = 100,
                updatedAt = 200,
                status = SyncManager.MUTATION_STATUS_FAILED,
            ),
        )
        dao.insertIgnoringConflict(
            mutation(
                "new-rejected",
                createdAt = 300,
                updatedAt = 500,
                status = SyncManager.MUTATION_STATUS_REJECTED,
            ),
        )
        dao.insertIgnoringConflict(mutation("queued", createdAt = 600, updatedAt = 600))
        dao.insertIgnoringConflict(
            mutation(
                "other-user-failed",
                createdAt = 700,
                updatedAt = 700,
                userId = "other-user",
                status = SyncManager.MUTATION_STATUS_FAILED,
            ),
        )

        val issues = dao.syncIssuesForUser(USER_ID)

        assertEquals(listOf("new-rejected", "old-failed"), issues.map { it.clientMutationId })
    }

    @Test
    fun localReferenceDaosAreScopedToUser() = runTest {
        database.localAccountDao().upsert(account("acc-1", userId = USER_ID, name = "Cash"))
        database.localAccountDao().upsert(account("acc-2", userId = "other-user", name = "Hidden"))
        database.localCategoryDao().upsert(category("cat-1", userId = USER_ID, name = "Food"))
        database.localCategoryDao().upsert(category("cat-2", userId = "other-user", name = "Hidden"))
        database.localAssetCategoryDao().upsert(assetCategory("asset-1", userId = USER_ID, name = "Brokerage"))
        database.localAssetCategoryDao().upsert(assetCategory("asset-2", userId = "other-user", name = "Hidden"))

        assertEquals(listOf("Cash"), database.localAccountDao().listForUser(USER_ID).map { it.name })
        assertEquals(listOf("Food"), database.localCategoryDao().listForUser(USER_ID).map { it.name })
        assertEquals(listOf("Brokerage"), database.localAssetCategoryDao().listForUser(USER_ID).map { it.name })

        database.localAccountDao().deleteForUser(USER_ID)
        database.localCategoryDao().deleteForUser(USER_ID)
        database.localAssetCategoryDao().deleteForUser(USER_ID)

        assertEquals(0, database.localAccountDao().listForUser(USER_ID).size)
        assertEquals(0, database.localCategoryDao().listForUser(USER_ID).size)
        assertEquals(0, database.localAssetCategoryDao().listForUser(USER_ID).size)
        assertEquals(1, database.localAccountDao().listForUser("other-user").size)
        assertEquals(1, database.localCategoryDao().listForUser("other-user").size)
        assertEquals(1, database.localAssetCategoryDao().listForUser("other-user").size)
    }

    @Test
    fun localPlanningDaosAreScopedToUserAndHideTombstones() = runTest {
        database.localPlanningPlanDao().upsert(planningPlan("plan-1", USER_ID, month = "2026-07"))
        database.localPlanningPlanDao().upsert(planningPlan("plan-2", "other-user", month = "2026-07"))
        database.localPlanningIncomeSourceDao().upsert(planningIncomeSource("income-1", USER_ID, "plan-1", source = "Salary"))
        database.localPlanningIncomeSourceDao().upsert(
            planningIncomeSource(
                "income-deleted",
                USER_ID,
                "plan-1",
                source = "Deleted",
                recordStatus = SyncManager.RECORD_STATUS_DELETED,
            ),
        )
        database.localPlanningIncomeSourceDao().upsert(planningIncomeSource("income-2", "other-user", "plan-2", source = "Hidden"))
        database.localPlanningAllocationDao().upsert(planningAllocation("allocation-1", USER_ID, "plan-1", targetId = "cat-1"))
        database.localPlanningAllocationDao().upsert(
            planningAllocation(
                "allocation-deleted",
                USER_ID,
                "plan-1",
                targetId = "cat-deleted",
                recordStatus = SyncManager.RECORD_STATUS_DELETED,
            ),
        )
        database.localPlanningAllocationDao().upsert(planningAllocation("allocation-2", "other-user", "plan-2", targetId = "cat-2"))

        val current = database.localPlanningPlanDao().findForScopeMonth(USER_ID, "personal", "2026-07", null)
        val history = database.localPlanningPlanDao().historyForScope(USER_ID, "personal", null)
        val income = database.localPlanningIncomeSourceDao().listForPlan(USER_ID, "plan-1")
        val allocations = database.localPlanningAllocationDao().listForPlan(USER_ID, "plan-1")

        assertEquals("plan-1", current?.localId)
        assertEquals(listOf("plan-1"), history.map { it.localId })
        assertEquals(listOf("Salary"), income.map { it.source })
        assertEquals(listOf("cat-1"), allocations.map { it.targetId })

        database.localPlanningPlanDao().deleteForUser(USER_ID)
        database.localPlanningIncomeSourceDao().deleteForUser(USER_ID)
        database.localPlanningAllocationDao().deleteForUser(USER_ID)

        assertEquals(0, database.localPlanningPlanDao().listForUser(USER_ID).size)
        assertEquals(0, database.localPlanningIncomeSourceDao().listForUser(USER_ID).size)
        assertEquals(0, database.localPlanningAllocationDao().listForUser(USER_ID).size)
        assertEquals(1, database.localPlanningPlanDao().listForUser("other-user").size)
        assertEquals(1, database.localPlanningIncomeSourceDao().listForUser("other-user").size)
        assertEquals(1, database.localPlanningAllocationDao().listForUser("other-user").size)
    }

    @Test
    fun localSchemaDoesNotDefineCaptureOcrOrScreenshotStorageTables() {
        val tables = mutableListOf<String>()
        database.openHelper.readableDatabase.query(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).use { cursor ->
            while (cursor.moveToNext()) {
                tables += cursor.getString(0)
            }
        }

        assertTrue(
            tables.none { table ->
                listOf("capture", "ocr", "screenshot", "image").any { forbidden ->
                    table.contains(forbidden, ignoreCase = true)
                }
            },
        )
    }

    private fun mutation(
        id: String,
        createdAt: Long,
        updatedAt: Long = createdAt,
        status: String = SyncManager.MUTATION_STATUS_QUEUED,
        userId: String = USER_ID,
    ): PendingMutationEntity {
        return PendingMutationEntity(
            clientMutationId = id,
            userId = userId,
            deviceId = "android-test-device",
            entityType = SyncManager.ENTITY_TRANSACTIONS,
            entityId = "11111111-1111-4111-8111-111111111111",
            operation = SyncManager.OPERATION_CREATE,
            baseVersion = null,
            payloadJson = "{}",
            status = status,
            attempts = 0,
            lastError = null,
            createdAtEpochMillis = createdAt,
            updatedAtEpochMillis = updatedAt,
        )
    }

    private fun account(id: String, userId: String, name: String): LocalAccountEntity {
        return LocalAccountEntity(
            localId = id,
            userId = userId,
            serverId = id,
            name = name,
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

    private fun category(id: String, userId: String, name: String): LocalCategoryEntity {
        return LocalCategoryEntity(
            localId = id,
            userId = userId,
            serverId = id,
            name = name,
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

    private fun assetCategory(id: String, userId: String, name: String): LocalAssetCategoryEntity {
        return LocalAssetCategoryEntity(
            localId = id,
            userId = userId,
            serverId = id,
            name = name,
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

    private fun planningPlan(id: String, userId: String, month: String): LocalPlanningPlanEntity {
        return LocalPlanningPlanEntity(
            localId = id,
            userId = userId,
            serverId = id,
            scope = "personal",
            month = month,
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

    private fun planningIncomeSource(
        id: String,
        userId: String,
        planId: String,
        source: String,
        recordStatus: String = SyncManager.RECORD_STATUS_ACTIVE,
    ): LocalPlanningIncomeSourceEntity {
        return LocalPlanningIncomeSourceEntity(
            localId = id,
            userId = userId,
            serverId = id,
            planLocalId = planId,
            planServerId = planId,
            amount = "100.00",
            source = source,
            description = null,
            dayOfMonth = 5,
            confirmed = false,
            effectiveDate = null,
            version = 1,
            syncStatus = SyncManager.SYNC_STATUS_SYNCED,
            recordStatus = recordStatus,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
            deletedAtEpochMillis = if (recordStatus == SyncManager.RECORD_STATUS_DELETED) 100 else null,
        )
    }

    private fun planningAllocation(
        id: String,
        userId: String,
        planId: String,
        targetId: String,
        recordStatus: String = SyncManager.RECORD_STATUS_ACTIVE,
    ): LocalPlanningAllocationEntity {
        return LocalPlanningAllocationEntity(
            localId = id,
            userId = userId,
            serverId = id,
            planLocalId = planId,
            planServerId = planId,
            targetType = "expense_category",
            targetId = targetId,
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
            recordStatus = recordStatus,
            createdAtEpochMillis = 100,
            updatedAtEpochMillis = 100,
            deletedAtEpochMillis = if (recordStatus == SyncManager.RECORD_STATUS_DELETED) 100 else null,
        )
    }

    private companion object {
        const val USER_ID = "user-1"
    }
}
