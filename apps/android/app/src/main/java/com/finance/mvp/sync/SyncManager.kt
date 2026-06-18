package com.finance.mvp.sync

import androidx.room.withTransaction
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.InvestmentMigrationCreateRequest
import com.finance.mvp.api.PlanningAllocationCreateRequest
import com.finance.mvp.api.PlanningAllocationUpdateRequest
import com.finance.mvp.api.PlanningIncomeSourceCreateRequest
import com.finance.mvp.api.PlanningIncomeSourceUpdateRequest
import com.finance.mvp.api.PlanningPlanCreateRequest
import com.finance.mvp.api.SyncMutationRequest
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
import com.finance.mvp.local.SyncStateEntity
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject

class SyncManager(
    private val database: FinanceLocalDatabase,
    private val apiClient: SyncApiClient,
    private val deviceIdStore: DeviceIdStore,
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
    private val nowIso: () -> String = { Instant.now().toString() },
    private val uuidFactory: () -> String = { UUID.randomUUID().toString() },
) {
    suspend fun enqueueManualTransactionCreate(
        userId: String,
        transactionType: String,
        amount: String,
        currency: String,
        accountId: String,
        categoryId: String? = null,
        counterpartyAccountId: String? = null,
        transactionDate: String,
        note: String? = null,
        localTransactionId: String = uuidFactory(),
    ): LocalTransactionEntity {
        val deviceId = deviceIdStore.deviceId()
        val now = nowEpochMillis()
        val payload = transactionPayload(
            transactionType = transactionType,
            amount = amount,
            currency = currency,
            accountId = accountId,
            categoryId = categoryId,
            counterpartyAccountId = counterpartyAccountId,
            transactionDate = transactionDate,
            note = note,
        )
        val clientMutationId = stableMutationId(
            deviceId = deviceId,
            entityId = localTransactionId,
            operation = OPERATION_CREATE,
            baseVersion = null,
            payloadJson = payload.toString(),
        )
        val transaction = LocalTransactionEntity(
            localId = localTransactionId,
            userId = userId,
            serverId = null,
            transactionType = transactionType,
            amount = amount,
            currency = currency,
            accountId = accountId,
            categoryId = categoryId,
            counterpartyAccountId = counterpartyAccountId,
            transactionDate = transactionDate,
            occurredAt = null,
            note = note,
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        val mutation = PendingMutationEntity(
            clientMutationId = clientMutationId,
            userId = userId,
            deviceId = deviceId,
            entityType = ENTITY_TRANSACTIONS,
            entityId = localTransactionId,
            operation = OPERATION_CREATE,
            baseVersion = null,
            payloadJson = payload.toString(),
            status = MUTATION_STATUS_QUEUED,
            attempts = 0,
            lastError = null,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )

        database.withTransaction {
            database.localTransactionDao().upsert(transaction)
            database.pendingMutationDao().insertIgnoringConflict(mutation)
        }
        return transaction
    }

    suspend fun enqueueAccountCreate(
        userId: String,
        name: String,
        accountType: String,
        ownershipType: String,
        currency: String,
        initialBalance: String,
        householdId: String? = null,
        assetCategoryId: String? = null,
        isPaymentAccount: Boolean = true,
        localAccountId: String = uuidFactory(),
    ): LocalAccountEntity {
        val now = nowEpochMillis()
        val payload = accountCreatePayload(
            name = name,
            accountType = accountType,
            ownershipType = ownershipType,
            currency = currency,
            initialBalance = initialBalance,
            householdId = householdId,
            assetCategoryId = assetCategoryId,
            isPaymentAccount = isPaymentAccount,
        )
        val account = LocalAccountEntity(
            localId = localAccountId,
            userId = userId,
            serverId = null,
            name = name,
            accountType = accountType,
            ownershipType = ownershipType,
            currency = currency,
            currentBalance = initialBalance,
            householdId = householdId?.takeIf { it.isNotBlank() },
            assetCategoryId = assetCategoryId?.takeIf { it.isNotBlank() },
            isPaymentAccount = isPaymentAccount,
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )

        database.withTransaction {
            database.localAccountDao().upsert(account)
            database.pendingMutationDao().insertIgnoringConflict(
                pendingMutation(
                    userId = userId,
                    entityType = ENTITY_ACCOUNTS,
                    entityId = localAccountId,
                    operation = OPERATION_CREATE,
                    baseVersion = null,
                    payload = payload,
                ),
            )
        }
        return account
    }

    suspend fun enqueueAccountUpdate(
        userId: String,
        entityId: String,
        baseVersion: Int,
        name: String? = null,
        accountType: String? = null,
        currency: String? = null,
        assetCategoryId: String? = null,
        clearAssetCategoryId: Boolean = false,
        isPaymentAccount: Boolean? = null,
        currentBalance: String? = null,
    ): PendingMutationEntity? {
        if (currentBalance != null) return null
        val payload = accountUpdatePayload(
            baseVersion = baseVersion,
            name = name,
            accountType = accountType,
            currency = currency,
            assetCategoryId = assetCategoryId,
            clearAssetCategoryId = clearAssetCategoryId,
            isPaymentAccount = isPaymentAccount,
        )
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ACCOUNTS,
            entityId = entityId,
            operation = OPERATION_UPDATE,
            baseVersion = baseVersion,
            payload = payload,
            localUpdate = { markAccountPendingUpdate(userId, entityId, payload) },
        )
    }

    suspend fun enqueueAccountArchive(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ACCOUNTS,
            entityId = entityId,
            operation = OPERATION_ARCHIVE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markAccountRecordStatus(userId, entityId, RECORD_STATUS_ARCHIVED) },
        )
    }

    suspend fun enqueueAccountRestore(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ACCOUNTS,
            entityId = entityId,
            operation = OPERATION_RESTORE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markAccountRecordStatus(userId, entityId, RECORD_STATUS_ACTIVE) },
        )
    }

    suspend fun enqueueAccountDelete(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ACCOUNTS,
            entityId = entityId,
            operation = OPERATION_DELETE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markAccountRecordStatus(userId, entityId, RECORD_STATUS_DELETED) },
        )
    }

    suspend fun enqueueCategoryCreate(
        userId: String,
        name: String,
        categoryType: String,
        scope: String,
        householdId: String? = null,
        iconKey: String? = null,
        color: String? = null,
        localCategoryId: String = uuidFactory(),
    ): LocalCategoryEntity {
        val now = nowEpochMillis()
        val payload = categoryCreatePayload(
            name = name,
            categoryType = categoryType,
            scope = scope,
            householdId = householdId,
            iconKey = iconKey,
            color = color,
        )
        val category = LocalCategoryEntity(
            localId = localCategoryId,
            userId = userId,
            serverId = null,
            name = name,
            categoryType = categoryType,
            scope = scope,
            householdId = householdId?.takeIf { it.isNotBlank() },
            iconKey = iconKey.orEmpty(),
            color = color.orEmpty(),
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )

        database.withTransaction {
            database.localCategoryDao().upsert(category)
            database.pendingMutationDao().insertIgnoringConflict(
                pendingMutation(
                    userId = userId,
                    entityType = ENTITY_CATEGORIES,
                    entityId = localCategoryId,
                    operation = OPERATION_CREATE,
                    baseVersion = null,
                    payload = payload,
                ),
            )
        }
        return category
    }

    suspend fun enqueueCategoryUpdate(
        userId: String,
        entityId: String,
        baseVersion: Int,
        name: String? = null,
        iconKey: String? = null,
        clearIconKey: Boolean = false,
        color: String? = null,
        clearColor: Boolean = false,
    ): PendingMutationEntity {
        val payload = categoryUpdatePayload(
            baseVersion = baseVersion,
            name = name,
            iconKey = iconKey,
            clearIconKey = clearIconKey,
            color = color,
            clearColor = clearColor,
        )
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_UPDATE,
            baseVersion = baseVersion,
            payload = payload,
            localUpdate = { markCategoryPendingUpdate(userId, entityId, payload) },
        )
    }

    suspend fun enqueueCategoryArchive(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_ARCHIVE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markCategoryRecordStatus(userId, entityId, RECORD_STATUS_ARCHIVED) },
        )
    }

    suspend fun enqueueCategoryRestore(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_RESTORE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markCategoryRecordStatus(userId, entityId, RECORD_STATUS_ACTIVE) },
        )
    }

    suspend fun enqueueCategoryDelete(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_DELETE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markCategoryRecordStatus(userId, entityId, RECORD_STATUS_DELETED) },
        )
    }

    suspend fun enqueueAssetCategoryCreate(
        userId: String,
        name: String,
        scopeType: String,
        currency: String,
        manualAmount: String,
        isInvestment: Boolean,
        assetType: String,
        householdId: String? = null,
        ownerUserId: String? = userId,
        iconKey: String? = null,
        localAssetCategoryId: String = uuidFactory(),
    ): LocalAssetCategoryEntity {
        val now = nowEpochMillis()
        val payload = assetCategoryCreatePayload(
            name = name,
            scopeType = scopeType,
            currency = currency,
            manualAmount = manualAmount,
            isInvestment = isInvestment,
            assetType = assetType,
            householdId = householdId,
            iconKey = iconKey,
        )
        val assetCategory = LocalAssetCategoryEntity(
            localId = localAssetCategoryId,
            userId = userId,
            serverId = null,
            name = name,
            scopeType = scopeType,
            householdId = householdId?.takeIf { it.isNotBlank() },
            ownerUserId = ownerUserId?.takeIf { it.isNotBlank() },
            currency = currency,
            manualAmount = manualAmount,
            isInvestment = isInvestment,
            assetType = assetType,
            iconKey = iconKey.orEmpty(),
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )

        database.withTransaction {
            database.localAssetCategoryDao().upsert(assetCategory)
            database.pendingMutationDao().insertIgnoringConflict(
                pendingMutation(
                    userId = userId,
                    entityType = ENTITY_ASSET_CATEGORIES,
                    entityId = localAssetCategoryId,
                    operation = OPERATION_CREATE,
                    baseVersion = null,
                    payload = payload,
                ),
            )
        }
        return assetCategory
    }

    suspend fun enqueueInvestmentMigrationCreate(
        userId: String,
        request: InvestmentMigrationCreateRequest,
        accounts: List<AccountSummary>,
    ): PendingMutationEntity {
        val payload = investmentMigrationCreatePayload(request)
        val mutation = pendingMutation(
            userId = userId,
            entityType = ENTITY_INVESTMENT_MIGRATIONS,
            entityId = request.assetCategoryId,
            operation = OPERATION_CREATE,
            baseVersion = null,
            payload = payload,
        )
        val now = nowEpochMillis()
        database.withTransaction {
            val existingAssetCategory = database.localAssetCategoryDao().findByServerId(userId, request.assetCategoryId)
                ?: database.localAssetCategoryDao().findByLocalId(userId, request.assetCategoryId)
            database.localAssetCategoryDao().upsert(
                LocalAssetCategoryEntity(
                    localId = existingAssetCategory?.localId ?: request.assetCategoryId,
                    userId = userId,
                    serverId = request.assetCategoryId,
                    name = request.name,
                    scopeType = if (request.scope == "household") "household" else "personal",
                    householdId = request.householdId?.takeIf { it.isNotBlank() },
                    ownerUserId = existingAssetCategory?.ownerUserId ?: userId,
                    currency = request.currency,
                    manualAmount = existingAssetCategory?.manualAmount ?: "0",
                    isInvestment = true,
                    assetType = request.assetType,
                    iconKey = request.iconKey.orEmpty(),
                    version = existingAssetCategory?.version,
                    syncStatus = SYNC_STATUS_PENDING,
                    recordStatus = RECORD_STATUS_ACTIVE,
                    createdAtEpochMillis = existingAssetCategory?.createdAtEpochMillis ?: now,
                    updatedAtEpochMillis = now,
                    deletedAtEpochMillis = null,
                ),
            )
            accounts.forEach { account ->
                val accountId = account.id.takeIf { it.isNotBlank() } ?: return@forEach
                val existingAccount = database.localAccountDao().findByServerId(userId, accountId)
                    ?: database.localAccountDao().findByLocalId(userId, accountId)
                database.localAccountDao().upsert(
                    (existingAccount ?: LocalAccountEntity(
                        localId = accountId,
                        userId = userId,
                        serverId = accountId,
                        name = account.name,
                        accountType = account.type,
                        ownershipType = account.ownershipType,
                        currency = account.currency,
                        currentBalance = account.currentBalance,
                        householdId = account.householdId?.takeIf { it.isNotBlank() },
                        assetCategoryId = account.assetCategoryId?.takeIf { it.isNotBlank() },
                        isPaymentAccount = account.isPaymentAccount,
                        version = account.version,
                        syncStatus = SYNC_STATUS_SYNCED,
                        recordStatus = account.status,
                        createdAtEpochMillis = now,
                        updatedAtEpochMillis = now,
                    )).copy(
                        assetCategoryId = request.assetCategoryId,
                        syncStatus = SYNC_STATUS_PENDING,
                        updatedAtEpochMillis = now,
                    ),
                )
            }
            database.pendingMutationDao().insertIgnoringConflict(mutation)
        }
        return mutation
    }

    suspend fun enqueueAssetCategoryUpdate(
        userId: String,
        entityId: String,
        baseVersion: Int,
        name: String? = null,
        manualAmount: String? = null,
        isInvestment: Boolean? = null,
        assetType: String? = null,
        iconKey: String? = null,
        clearIconKey: Boolean = false,
    ): PendingMutationEntity {
        val payload = assetCategoryUpdatePayload(
            baseVersion = baseVersion,
            name = name,
            manualAmount = manualAmount,
            isInvestment = isInvestment,
            assetType = assetType,
            iconKey = iconKey,
            clearIconKey = clearIconKey,
        )
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ASSET_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_UPDATE,
            baseVersion = baseVersion,
            payload = payload,
            localUpdate = { markAssetCategoryPendingUpdate(userId, entityId, payload) },
        )
    }

    suspend fun enqueueAssetCategoryArchive(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ASSET_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_ARCHIVE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markAssetCategoryRecordStatus(userId, entityId, RECORD_STATUS_ARCHIVED) },
        )
    }

    suspend fun enqueueAssetCategoryRestore(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ASSET_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_RESTORE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markAssetCategoryRecordStatus(userId, entityId, RECORD_STATUS_ACTIVE) },
        )
    }

    suspend fun enqueueAssetCategoryDelete(userId: String, entityId: String, baseVersion: Int): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_ASSET_CATEGORIES,
            entityId = entityId,
            operation = OPERATION_DELETE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markAssetCategoryRecordStatus(userId, entityId, RECORD_STATUS_DELETED) },
        )
    }

    suspend fun enqueueTransactionUpdate(
        userId: String,
        entityId: String,
        baseVersion: Int,
        payload: JSONObject,
    ): PendingMutationEntity {
        return enqueueTransactionMutation(
            userId = userId,
            entityId = entityId,
            operation = OPERATION_UPDATE,
            baseVersion = baseVersion,
            payload = payload,
        )
    }

    suspend fun enqueueTransactionDelete(
        userId: String,
        entityId: String,
        baseVersion: Int,
    ): PendingMutationEntity {
        return enqueueTransactionMutation(
            userId = userId,
            entityId = entityId,
            operation = OPERATION_DELETE,
            baseVersion = baseVersion,
            payload = null,
        )
    }

    suspend fun enqueueTransactionRestore(
        userId: String,
        entityId: String,
        baseVersion: Int,
    ): PendingMutationEntity {
        return enqueueTransactionMutation(
            userId = userId,
            entityId = entityId,
            operation = OPERATION_RESTORE,
            baseVersion = baseVersion,
            payload = null,
        )
    }

    suspend fun enqueuePlanningPlanCreate(
        userId: String,
        request: PlanningPlanCreateRequest,
        localPlanId: String = uuidFactory(),
    ): LocalPlanningPlanEntity {
        val now = nowEpochMillis()
        val payload = planningPlanCreatePayload(request)
        val plan = LocalPlanningPlanEntity(
            localId = localPlanId,
            userId = userId,
            serverId = null,
            scope = request.scope,
            month = request.month,
            currency = request.currency,
            householdId = request.householdId?.takeIf { it.isNotBlank() },
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
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )

        database.withTransaction {
            database.localPlanningPlanDao().upsert(plan)
            database.pendingMutationDao().insertIgnoringConflict(
                pendingMutation(
                    userId = userId,
                    entityType = ENTITY_PLANNING_PLANS,
                    entityId = localPlanId,
                    operation = OPERATION_CREATE,
                    baseVersion = null,
                    payload = payload,
                ),
            )
        }
        return plan
    }

    suspend fun enqueuePlanningIncomeSourceCreate(
        userId: String,
        planId: String,
        request: PlanningIncomeSourceCreateRequest,
        localIncomeSourceId: String = uuidFactory(),
    ): LocalPlanningIncomeSourceEntity {
        val now = nowEpochMillis()
        val plan = findPlanningPlanByAnyId(userId, planId)
        val payload = planningIncomeSourceCreatePayload(planId = plan?.serverId ?: planId, request = request)
        val source = LocalPlanningIncomeSourceEntity(
            localId = localIncomeSourceId,
            userId = userId,
            serverId = null,
            planLocalId = plan?.localId ?: planId,
            planServerId = plan?.serverId ?: planId,
            amount = request.amount,
            source = request.source,
            description = request.description,
            dayOfMonth = request.dayOfMonth,
            confirmed = false,
            effectiveDate = request.effectiveDate,
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        database.withTransaction {
            database.localPlanningIncomeSourceDao().upsert(source)
            database.pendingMutationDao().insertIgnoringConflict(
                pendingMutation(
                    userId = userId,
                    entityType = ENTITY_PLANNING_INCOME_SOURCES,
                    entityId = localIncomeSourceId,
                    operation = OPERATION_CREATE,
                    baseVersion = null,
                    payload = payload,
                ),
            )
        }
        return source
    }

    suspend fun enqueuePlanningIncomeSourceUpdate(
        userId: String,
        entityId: String,
        baseVersion: Int,
        request: PlanningIncomeSourceUpdateRequest,
    ): PendingMutationEntity {
        val payload = planningIncomeSourceUpdatePayload(baseVersion = baseVersion, request = request)
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_PLANNING_INCOME_SOURCES,
            entityId = entityId,
            operation = OPERATION_UPDATE,
            baseVersion = baseVersion,
            payload = payload,
            localUpdate = { markPlanningIncomeSourcePendingUpdate(userId, entityId, payload) },
        )
    }

    suspend fun enqueuePlanningIncomeSourceConfirm(
        userId: String,
        entityId: String,
        baseVersion: Int,
    ): PendingMutationEntity {
        val payload = JSONObject().put("version", baseVersion)
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_PLANNING_INCOME_SOURCES,
            entityId = entityId,
            operation = OPERATION_CONFIRM,
            baseVersion = baseVersion,
            payload = payload,
            localUpdate = { markPlanningIncomeSourceConfirmed(userId, entityId) },
        )
    }

    suspend fun enqueuePlanningIncomeSourceDelete(
        userId: String,
        entityId: String,
        baseVersion: Int,
    ): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_PLANNING_INCOME_SOURCES,
            entityId = entityId,
            operation = OPERATION_DELETE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markPlanningIncomeSourceRecordStatus(userId, entityId, RECORD_STATUS_DELETED) },
        )
    }

    suspend fun enqueuePlanningAllocationCreate(
        userId: String,
        planId: String,
        request: PlanningAllocationCreateRequest,
        localAllocationId: String = uuidFactory(),
    ): LocalPlanningAllocationEntity {
        val now = nowEpochMillis()
        val plan = findPlanningPlanByAnyId(userId, planId)
        val payload = planningAllocationCreatePayload(planId = plan?.serverId ?: planId, request = request)
        val allocation = LocalPlanningAllocationEntity(
            localId = localAllocationId,
            userId = userId,
            serverId = null,
            planLocalId = plan?.localId ?: planId,
            planServerId = plan?.serverId ?: planId,
            targetType = request.targetType,
            targetId = request.targetId,
            targetSnapshot = request.targetSnapshot,
            requiresAttention = false,
            attentionReason = null,
            comment = request.comment,
            allocationMode = request.allocationMode,
            allocationValue = request.allocationValue,
            calculatedAmount = if (request.allocationMode == "amount") request.allocationValue else "0",
            recurrenceType = request.recurrenceType,
            isSavingsGoal = request.isSavingsGoal,
            goalTargetAmount = request.goalTargetAmount,
            goalDueMonth = request.goalDueMonth,
            goalMonthlyAmount = null,
            actualAmount = null,
            varianceAmount = null,
            progressPercent = null,
            progressStatus = null,
            status = null,
            version = null,
            syncStatus = SYNC_STATUS_PENDING,
            recordStatus = RECORD_STATUS_ACTIVE,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        database.withTransaction {
            database.localPlanningAllocationDao().upsert(allocation)
            database.pendingMutationDao().insertIgnoringConflict(
                pendingMutation(
                    userId = userId,
                    entityType = ENTITY_PLANNING_ALLOCATIONS,
                    entityId = localAllocationId,
                    operation = OPERATION_CREATE,
                    baseVersion = null,
                    payload = payload,
                ),
            )
        }
        return allocation
    }

    suspend fun enqueuePlanningAllocationUpdate(
        userId: String,
        entityId: String,
        baseVersion: Int,
        request: PlanningAllocationUpdateRequest,
    ): PendingMutationEntity {
        val payload = planningAllocationUpdatePayload(baseVersion = baseVersion, request = request)
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_PLANNING_ALLOCATIONS,
            entityId = entityId,
            operation = OPERATION_UPDATE,
            baseVersion = baseVersion,
            payload = payload,
            localUpdate = { markPlanningAllocationPendingUpdate(userId, entityId, payload) },
        )
    }

    suspend fun enqueuePlanningAllocationDelete(
        userId: String,
        entityId: String,
        baseVersion: Int,
    ): PendingMutationEntity {
        return enqueueReferenceMutation(
            userId = userId,
            entityType = ENTITY_PLANNING_ALLOCATIONS,
            entityId = entityId,
            operation = OPERATION_DELETE,
            baseVersion = baseVersion,
            payload = null,
            localUpdate = { markPlanningAllocationRecordStatus(userId, entityId, RECORD_STATUS_DELETED) },
        )
    }

    suspend fun pushPendingMutations(userId: String, limit: Int = 100): SyncPushSummary {
        val pending = database.pendingMutationDao().pendingForUser(userId = userId, limit = limit)
        if (pending.isEmpty()) return SyncPushSummary()
        val (syncablePending, onlineOnlyPending) = pending.partition { isSyncableEntityType(it.entityType) }
        if (onlineOnlyPending.isNotEmpty()) {
            database.pendingMutationDao().deleteByClientMutationIds(
                onlineOnlyPending.map { it.clientMutationId },
            )
        }
        if (syncablePending.isEmpty()) {
            return SyncPushSummary(rejected = onlineOnlyPending.size)
        }

        val response = apiClient.syncPush(
            SyncPushRequest(
                deviceId = deviceIdStore.deviceId(),
                mutations = syncablePending.map { it.toSyncMutationRequest() },
            ),
        )

        return when (response) {
            is ApiResult.Success -> {
                val summary = applyPushResponse(userId, syncablePending, response.value)
                summary.copy(rejected = summary.rejected + onlineOnlyPending.size)
            }
            is ApiResult.Failure -> {
                val retriable = response.statusCode.isRetriableStatus()
                syncablePending.forEach { mutation ->
                    markMutationAfterFailure(
                        mutation = mutation,
                        retriable = retriable,
                        message = response.message,
                    )
                }
                SyncPushSummary(
                    pushed = syncablePending.size,
                    rejected = onlineOnlyPending.size,
                    retry = if (retriable) syncablePending.size else 0,
                    failed = if (retriable) 0 else syncablePending.size,
                )
            }
        }
    }

    suspend fun pullAndApply(userId: String, limit: Int = 100): ApiResult<SyncPullResponse> {
        val deviceId = deviceIdStore.deviceId()
        val state = database.syncStateDao().find(userId, deviceId)
        val response = apiClient.syncPull(
            SyncPullRequest(
                deviceId = deviceId,
                cursor = state?.serverCursor ?: 0,
                limit = limit,
                entityTypes = SYNC_PULL_ENTITY_TYPES,
            ),
        )
        if (response is ApiResult.Success) {
            applyPullChanges(userId = userId, response = response.value)
            database.syncStateDao().upsert(
                SyncStateEntity(
                    userId = userId,
                    deviceId = deviceId,
                    serverCursor = response.value.nextCursor,
                    lastSuccessfulSyncAt = response.value.serverTime,
                    updatedAtEpochMillis = nowEpochMillis(),
                ),
            )
        }
        return response
    }

    suspend fun syncOnce(userId: String): SyncOnceSummary {
        val push = pushPendingMutations(userId)
        val pull = pullAndApply(userId)
        return SyncOnceSummary(push = push, pullSucceeded = pull is ApiResult.Success)
    }

    suspend fun syncNow(userId: String): SyncOnceSummary = syncOnce(userId)

    suspend fun pendingAttentionCount(userId: String): Int {
        return database.pendingMutationDao().countForUser(
            userId = userId,
            statuses = listOf(MUTATION_STATUS_QUEUED, MUTATION_STATUS_RETRY),
        )
    }

    suspend fun failedAttentionCount(userId: String): Int {
        return database.pendingMutationDao().countForUser(
            userId = userId,
            statuses = listOf(MUTATION_STATUS_FAILED, MUTATION_STATUS_REJECTED),
        )
    }

    suspend fun syncIssuesForUser(userId: String, limit: Int = 100): List<SyncIssueSummary> {
        return database.pendingMutationDao().syncIssuesForUser(
            userId = userId,
            statuses = listOf(MUTATION_STATUS_FAILED, MUTATION_STATUS_REJECTED),
            limit = limit,
        ).map { mutation ->
            SyncIssueSummary(
                entityType = mutation.entityType,
                operation = mutation.operation,
                status = mutation.status,
                lastError = mutation.lastError,
                attempts = mutation.attempts,
                updatedAtEpochMillis = mutation.updatedAtEpochMillis,
                createdAtEpochMillis = mutation.createdAtEpochMillis,
            )
        }
    }

    suspend fun retryFailedIssuesAndSyncNow(userId: String): SyncOnceSummary {
        database.pendingMutationDao().updateStatusesForUser(
            userId = userId,
            statuses = listOf(MUTATION_STATUS_FAILED),
            nextStatus = MUTATION_STATUS_RETRY,
            updatedAtEpochMillis = nowEpochMillis(),
        )
        return syncNow(userId)
    }

    suspend fun clearUserData(userId: String) {
        database.withTransaction {
            database.localTransactionDao().deleteForUser(userId)
            database.localAccountDao().deleteForUser(userId)
            database.localCategoryDao().deleteForUser(userId)
            database.localAssetCategoryDao().deleteForUser(userId)
            database.localPlanningPlanDao().deleteForUser(userId)
            database.localPlanningIncomeSourceDao().deleteForUser(userId)
            database.localPlanningAllocationDao().deleteForUser(userId)
            database.pendingMutationDao().deleteForUser(userId)
            database.syncStateDao().deleteForUser(userId)
        }
    }

    suspend fun applyPullChanges(userId: String, response: SyncPullResponse) {
        database.withTransaction {
            response.changes
                .forEach { change ->
                    val payload = change.payload
                    when (change.entityType) {
                        ENTITY_TRANSACTIONS -> {
                            if (payload != null) {
                                applyTransactionPayload(
                                    userId = userId,
                                    payload = payload,
                                    fallbackEntityId = change.entityId,
                                    syncStatus = SYNC_STATUS_SYNCED,
                                )
                            } else if (change.changeType == OPERATION_DELETE) {
                                markTransactionDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                )
                            }
                        }
                        ENTITY_ACCOUNTS -> {
                            if (payload != null) {
                                applyAccountPayload(userId = userId, payload = payload, fallbackEntityId = change.entityId)
                            } else if (change.changeType == OPERATION_DELETE) {
                                markAccountDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                    tombstonePayload = change.tombstonePayload,
                                )
                            }
                        }
                        ENTITY_CATEGORIES -> {
                            if (payload != null) {
                                applyCategoryPayload(userId = userId, payload = payload, fallbackEntityId = change.entityId)
                            } else if (change.changeType == OPERATION_DELETE) {
                                markCategoryDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                    tombstonePayload = change.tombstonePayload,
                                )
                            }
                        }
                        ENTITY_ASSET_CATEGORIES -> {
                            if (payload != null) {
                                applyAssetCategoryPayload(userId = userId, payload = payload, fallbackEntityId = change.entityId)
                            } else if (change.changeType == OPERATION_DELETE) {
                                markAssetCategoryDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                    tombstonePayload = change.tombstonePayload,
                                )
                            }
                        }
                        ENTITY_PLANNING_PLANS -> {
                            if (payload != null) {
                                applyPlanningPlanPayload(
                                    userId = userId,
                                    payload = payload,
                                    fallbackEntityId = change.entityId,
                                )
                            } else if (change.changeType == OPERATION_DELETE) {
                                markPlanningPlanDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                    tombstonePayload = change.tombstonePayload,
                                )
                            }
                        }
                        ENTITY_PLANNING_INCOME_SOURCES -> {
                            if (payload != null) {
                                applyPlanningIncomeSourcePayload(
                                    userId = userId,
                                    payload = payload,
                                    fallbackEntityId = change.entityId,
                                )
                            } else if (change.changeType == OPERATION_DELETE) {
                                markPlanningIncomeSourceDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                    tombstonePayload = change.tombstonePayload,
                                )
                            }
                        }
                        ENTITY_PLANNING_ALLOCATIONS -> {
                            if (payload != null) {
                                applyPlanningAllocationPayload(
                                    userId = userId,
                                    payload = payload,
                                    fallbackEntityId = change.entityId,
                                )
                            } else if (change.changeType == OPERATION_DELETE) {
                                markPlanningAllocationDeleted(
                                    userId = userId,
                                    entityId = change.entityId,
                                    version = change.entityVersion,
                                    tombstonePayload = change.tombstonePayload,
                                )
                            }
                        }
                    }
                }
        }
    }

    private suspend fun enqueueTransactionMutation(
        userId: String,
        entityId: String,
        operation: String,
        baseVersion: Int?,
        payload: JSONObject?,
    ): PendingMutationEntity {
        requireSyncableEntityType(ENTITY_TRANSACTIONS)
        val deviceId = deviceIdStore.deviceId()
        val now = nowEpochMillis()
        val payloadJson = payload?.toString()
        val mutation = PendingMutationEntity(
            clientMutationId = stableMutationId(
                deviceId = deviceId,
                entityId = entityId,
                operation = operation,
                baseVersion = baseVersion,
                payloadJson = payloadJson,
            ),
            userId = userId,
            deviceId = deviceId,
            entityType = ENTITY_TRANSACTIONS,
            entityId = entityId,
            operation = operation,
            baseVersion = baseVersion,
            payloadJson = payloadJson,
            status = MUTATION_STATUS_QUEUED,
            attempts = 0,
            lastError = null,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        database.pendingMutationDao().insertIgnoringConflict(mutation)
        return mutation
    }

    private suspend fun enqueueReferenceMutation(
        userId: String,
        entityType: String,
        entityId: String,
        operation: String,
        baseVersion: Int?,
        payload: JSONObject?,
        localUpdate: suspend () -> Unit,
    ): PendingMutationEntity {
        val mutation = pendingMutation(
            userId = userId,
            entityType = entityType,
            entityId = entityId,
            operation = operation,
            baseVersion = baseVersion,
            payload = payload,
        )
        database.withTransaction {
            localUpdate()
            database.pendingMutationDao().insertIgnoringConflict(mutation)
        }
        return mutation
    }

    private suspend fun pendingMutation(
        userId: String,
        entityType: String,
        entityId: String,
        operation: String,
        baseVersion: Int?,
        payload: JSONObject?,
    ): PendingMutationEntity {
        requireSyncableEntityType(entityType)
        val deviceId = deviceIdStore.deviceId()
        val now = nowEpochMillis()
        val payloadJson = payload?.toString()
        return PendingMutationEntity(
            clientMutationId = stableMutationId(
                deviceId = deviceId,
                entityType = entityType,
                entityId = entityId,
                operation = operation,
                baseVersion = baseVersion,
                payloadJson = payloadJson,
            ),
            userId = userId,
            deviceId = deviceId,
            entityType = entityType,
            entityId = entityId,
            operation = operation,
            baseVersion = baseVersion,
            payloadJson = payloadJson,
            status = MUTATION_STATUS_QUEUED,
            attempts = 0,
            lastError = null,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
    }

    private suspend fun applyPushResponse(
        userId: String,
        pending: List<PendingMutationEntity>,
        response: SyncPushResponse,
    ): SyncPushSummary {
        var applied = 0
        var rejected = 0
        var retry = 0
        val resultsById = response.results.associateBy { it.clientMutationId }
        database.withTransaction {
            pending.forEach { mutation ->
                val result = resultsById[mutation.clientMutationId]
                when {
                    result == null -> {
                        retry += 1
                        markMutationAfterFailure(mutation, retriable = true, message = "Missing sync result")
                    }
                    result.status == MUTATION_STATUS_APPLIED -> {
                        applied += 1
                        database.pendingMutationDao().updateStatus(
                            clientMutationId = mutation.clientMutationId,
                            status = MUTATION_STATUS_APPLIED,
                            attempts = mutation.attempts + 1,
                            lastError = null,
                            updatedAtEpochMillis = nowEpochMillis(),
                            lastAttemptAtEpochMillis = nowEpochMillis(),
                        )
                        result.data?.let { payload ->
                            applySyncedPayload(
                                userId = userId,
                                entityType = result.entityType,
                                entityId = result.entityId,
                                payload = payload,
                            )
                        }
                    }
                    result.errorCode.isRetriableSyncError() -> {
                        retry += 1
                        markMutationAfterFailure(mutation, retriable = true, message = result.message)
                    }
                    else -> {
                        rejected += 1
                        database.pendingMutationDao().updateStatus(
                            clientMutationId = mutation.clientMutationId,
                            status = MUTATION_STATUS_REJECTED,
                            attempts = mutation.attempts + 1,
                            lastError = result.errorCode ?: result.message ?: "Rejected by sync API",
                            updatedAtEpochMillis = nowEpochMillis(),
                            lastAttemptAtEpochMillis = nowEpochMillis(),
                        )
                    }
                }
            }
        }
        return SyncPushSummary(pushed = pending.size, applied = applied, rejected = rejected, retry = retry)
    }

    private suspend fun applySyncedPayload(
        userId: String,
        entityType: String,
        entityId: String,
        payload: JSONObject,
    ) {
        when (entityType) {
            ENTITY_TRANSACTIONS -> applyTransactionPayload(
                userId = userId,
                payload = payload,
                fallbackEntityId = entityId,
                syncStatus = SYNC_STATUS_SYNCED,
            )
            ENTITY_ACCOUNTS -> applyAccountPayload(userId = userId, payload = payload, fallbackEntityId = entityId)
            ENTITY_CATEGORIES -> applyCategoryPayload(userId = userId, payload = payload, fallbackEntityId = entityId)
            ENTITY_ASSET_CATEGORIES -> applyAssetCategoryPayload(
                userId = userId,
                payload = payload,
                fallbackEntityId = entityId,
            )
            ENTITY_INVESTMENT_MIGRATIONS -> applyInvestmentMigrationPayload(
                userId = userId,
                payload = payload,
                fallbackEntityId = entityId,
            )
            ENTITY_PLANNING_PLANS -> applyPlanningPlanPayload(
                userId = userId,
                payload = payload,
                fallbackEntityId = entityId,
            )
            ENTITY_PLANNING_INCOME_SOURCES -> applyPlanningIncomeSourcePayload(
                userId = userId,
                payload = payload,
                fallbackEntityId = entityId,
            )
            ENTITY_PLANNING_ALLOCATIONS -> applyPlanningAllocationPayload(
                userId = userId,
                payload = payload,
                fallbackEntityId = entityId,
            )
        }
    }

    private suspend fun markMutationAfterFailure(
        mutation: PendingMutationEntity,
        retriable: Boolean,
        message: String?,
    ) {
        database.pendingMutationDao().updateStatus(
            clientMutationId = mutation.clientMutationId,
            status = if (retriable) MUTATION_STATUS_RETRY else MUTATION_STATUS_FAILED,
            attempts = mutation.attempts + 1,
            lastError = message,
            updatedAtEpochMillis = nowEpochMillis(),
            lastAttemptAtEpochMillis = nowEpochMillis(),
        )
    }

    private suspend fun applyTransactionPayload(
        userId: String,
        payload: JSONObject,
        fallbackEntityId: String,
        syncStatus: String,
    ) {
        val serverId = payload.optNullableString("id") ?: fallbackEntityId
        val existing = database.localTransactionDao().findByServerId(userId, serverId)
            ?: database.localTransactionDao().findByLocalId(userId, serverId)
        val now = nowEpochMillis()
        database.localTransactionDao().upsert(
            LocalTransactionEntity(
                localId = existing?.localId ?: serverId,
                userId = userId,
                serverId = serverId,
                transactionType = payload.optString("transactionType", existing?.transactionType ?: "expense"),
                amount = payload.optString("amount", existing?.amount ?: "0"),
                currency = payload.optString("currency", existing?.currency ?: "USD"),
                accountId = payload.optString("accountId", existing?.accountId.orEmpty()),
                categoryId = payload.optNullableString("categoryId") ?: existing?.categoryId,
                counterpartyAccountId = payload.optNullableString("counterpartyAccountId")
                    ?: existing?.counterpartyAccountId,
                transactionDate = payload.optNullableString("transactionDate")
                    ?: existing?.transactionDate
                    ?: payload.optString("occurredAt").take(10),
                occurredAt = payload.optNullableString("occurredAt") ?: existing?.occurredAt,
                note = payload.optNullableString("description") ?: existing?.note,
                version = payload.optIntOrNull("version") ?: existing?.version,
                syncStatus = syncStatus,
                recordStatus = payload.optString("recordStatus", existing?.recordStatus ?: RECORD_STATUS_ACTIVE),
                createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis,
            ),
        )
    }

    private suspend fun markTransactionDeleted(userId: String, entityId: String, version: Int?) {
        val existing = database.localTransactionDao().findByServerId(userId, entityId)
            ?: database.localTransactionDao().findByLocalId(userId, entityId)
            ?: return
        database.localTransactionDao().upsert(
            existing.copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: existing.version,
                updatedAtEpochMillis = nowEpochMillis(),
                deletedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun applyAccountPayload(userId: String, payload: JSONObject, fallbackEntityId: String) {
        val serverId = payload.optEntityId("accountId") ?: fallbackEntityId
        val existing = database.localAccountDao().findByServerId(userId, serverId)
            ?: database.localAccountDao().findByLocalId(userId, serverId)
        val now = nowEpochMillis()
        database.localAccountDao().upsert(
            LocalAccountEntity(
                localId = existing?.localId ?: serverId,
                userId = userId,
                serverId = serverId,
                name = payload.optString("name", existing?.name ?: ""),
                accountType = payload.optString("accountType", existing?.accountType ?: "cash"),
                ownershipType = payload.optString("ownershipType", existing?.ownershipType ?: "personal"),
                currency = payload.optString("currency", existing?.currency ?: "USD"),
                currentBalance = payload.optString(
                    "currentBalance",
                    payload.optString("initialBalance", existing?.currentBalance ?: "0"),
                ),
                householdId = payload.optNullableStringOrExisting("householdId", existing?.householdId),
                assetCategoryId = payload.optNullableStringOrExisting("assetCategoryId", existing?.assetCategoryId),
                isPaymentAccount = payload.optBoolean("isPaymentAccount", existing?.isPaymentAccount ?: true),
                version = payload.optIntOrNull("version") ?: existing?.version,
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = payload.recordStatus(existing?.recordStatus),
                createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (payload.recordStatus(existing?.recordStatus) == RECORD_STATUS_DELETED) {
                    existing?.deletedAtEpochMillis ?: now
                } else {
                    null
                },
            ),
        )
    }

    private suspend fun markAccountDeleted(
        userId: String,
        entityId: String,
        version: Int?,
        tombstonePayload: JSONObject?,
    ) {
        val existing = database.localAccountDao().findByServerId(userId, entityId)
            ?: database.localAccountDao().findByLocalId(userId, entityId)
        val now = nowEpochMillis()
        database.localAccountDao().upsert(
            (existing ?: tombstonePayload.toDeletedAccountEntity(userId, entityId, now)).copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: tombstonePayload?.optIntOrNull("version") ?: existing?.version,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis ?: now,
            ),
        )
    }

    private suspend fun applyCategoryPayload(userId: String, payload: JSONObject, fallbackEntityId: String) {
        val serverId = payload.optEntityId("categoryId") ?: fallbackEntityId
        val existing = database.localCategoryDao().findByServerId(userId, serverId)
            ?: database.localCategoryDao().findByLocalId(userId, serverId)
        val now = nowEpochMillis()
        database.localCategoryDao().upsert(
            LocalCategoryEntity(
                localId = existing?.localId ?: serverId,
                userId = userId,
                serverId = serverId,
                name = payload.optString("name", existing?.name ?: ""),
                categoryType = payload.optString("type", payload.optString("categoryType", existing?.categoryType ?: "expense")),
                scope = payload.optString("scope", existing?.scope ?: "personal"),
                householdId = payload.optNullableStringOrExisting("householdId", existing?.householdId),
                iconKey = payload.optString("iconKey", existing?.iconKey ?: ""),
                color = payload.optString("color", existing?.color ?: ""),
                version = payload.optIntOrNull("version") ?: existing?.version,
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = payload.recordStatus(existing?.recordStatus),
                createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (payload.recordStatus(existing?.recordStatus) == RECORD_STATUS_DELETED) {
                    existing?.deletedAtEpochMillis ?: now
                } else {
                    null
                },
            ),
        )
    }

    private suspend fun markCategoryDeleted(
        userId: String,
        entityId: String,
        version: Int?,
        tombstonePayload: JSONObject?,
    ) {
        val existing = database.localCategoryDao().findByServerId(userId, entityId)
            ?: database.localCategoryDao().findByLocalId(userId, entityId)
        val now = nowEpochMillis()
        database.localCategoryDao().upsert(
            (existing ?: tombstonePayload.toDeletedCategoryEntity(userId, entityId, now)).copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: tombstonePayload?.optIntOrNull("version") ?: existing?.version,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis ?: now,
            ),
        )
    }

    private suspend fun applyAssetCategoryPayload(userId: String, payload: JSONObject, fallbackEntityId: String) {
        val serverId = payload.optEntityId("assetCategoryId") ?: fallbackEntityId
        val existing = database.localAssetCategoryDao().findByServerId(userId, serverId)
            ?: database.localAssetCategoryDao().findByLocalId(userId, serverId)
        val now = nowEpochMillis()
        database.localAssetCategoryDao().upsert(
            LocalAssetCategoryEntity(
                localId = existing?.localId ?: serverId,
                userId = userId,
                serverId = serverId,
                name = payload.optString("name", existing?.name ?: ""),
                scopeType = payload.optString("scopeType", payload.optString("scope", existing?.scopeType ?: "personal")),
                householdId = payload.optNullableStringOrExisting("householdId", existing?.householdId),
                ownerUserId = payload.optNullableStringOrExisting("ownerUserId", existing?.ownerUserId),
                currency = payload.optString("currency", existing?.currency ?: "USD"),
                manualAmount = payload.optString("manualAmount", existing?.manualAmount ?: "0"),
                isInvestment = payload.optBoolean("isInvestment", existing?.isInvestment ?: false),
                assetType = payload.optString("assetType", payload.optString("accountType", existing?.assetType ?: "bank")),
                iconKey = payload.optString("iconKey", existing?.iconKey ?: ""),
                version = payload.optIntOrNull("version") ?: existing?.version,
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = payload.recordStatus(existing?.recordStatus),
                createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (payload.recordStatus(existing?.recordStatus) == RECORD_STATUS_DELETED) {
                    existing?.deletedAtEpochMillis ?: now
                } else {
                    null
                },
            ),
        )
    }

    private suspend fun applyInvestmentMigrationPayload(userId: String, payload: JSONObject, fallbackEntityId: String) {
        val assetCategoryPayload = payload.optJSONObject("assetCategory")
            ?: payload.optJSONObject("asset_category")
            ?: payload.takeIf { it.has("assetCategoryId") || it.has("name") }
        assetCategoryPayload?.let {
            applyAssetCategoryPayload(userId = userId, payload = it, fallbackEntityId = fallbackEntityId)
        }
        payload.optJSONArray("accounts")
            ?.toObjectList()
            ?.forEach { accountPayload ->
                applyAccountPayload(
                    userId = userId,
                    payload = accountPayload,
                    fallbackEntityId = accountPayload.optEntityId("accountId") ?: "",
                )
            }
    }

    private suspend fun markAssetCategoryDeleted(
        userId: String,
        entityId: String,
        version: Int?,
        tombstonePayload: JSONObject?,
    ) {
        val existing = database.localAssetCategoryDao().findByServerId(userId, entityId)
            ?: database.localAssetCategoryDao().findByLocalId(userId, entityId)
        val now = nowEpochMillis()
        database.localAssetCategoryDao().upsert(
            (existing ?: tombstonePayload.toDeletedAssetCategoryEntity(userId, entityId, now)).copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: tombstonePayload?.optIntOrNull("version") ?: existing?.version,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis ?: now,
            ),
        )
    }

    private suspend fun applyPlanningPlanPayload(userId: String, payload: JSONObject, fallbackEntityId: String) {
        val serverId = payload.optEntityId("planId") ?: fallbackEntityId
        val existing = database.localPlanningPlanDao().findByServerId(userId, serverId)
            ?: database.localPlanningPlanDao().findByLocalId(userId, fallbackEntityId)
            ?: database.localPlanningPlanDao().findByLocalId(userId, serverId)
        val summary = payload.optJSONObject("summary")
        val now = nowEpochMillis()
        val recordStatus = payload.recordStatus(existing?.recordStatus)
        val entity = LocalPlanningPlanEntity(
            localId = existing?.localId ?: fallbackEntityId.ifBlank { serverId },
            userId = userId,
            serverId = serverId,
            scope = payload.optString("scope", existing?.scope ?: "personal"),
            month = payload.optString("month", existing?.month ?: ""),
            currency = payload.optString("currency", existing?.currency ?: "USD"),
            householdId = payload.optNullableStringOrExisting("householdId", existing?.householdId),
            totalPlannedIncome = summary?.optString("totalPlannedIncome", existing?.totalPlannedIncome ?: "0")
                ?: payload.optString("totalPlannedIncome", existing?.totalPlannedIncome ?: "0"),
            previousMonthSurplus = summary?.optString("previousMonthSurplus", existing?.previousMonthSurplus ?: "0")
                ?: payload.optString("previousMonthSurplus", existing?.previousMonthSurplus ?: "0"),
            allocatedTotal = summary?.optString("totalAllocatedAmount", existing?.allocatedTotal ?: "0")
                ?: payload.optString("allocatedTotal", existing?.allocatedTotal ?: "0"),
            remainingAmount = summary?.optString("unallocatedAmount", existing?.remainingAmount ?: "0")
                ?: payload.optString("remainingAmount", existing?.remainingAmount ?: "0"),
            overallocatedAmount = payload.optString(
                "overallocatedAmount",
                if (summary?.optBoolean("overallocated", false) == true) {
                    summary.optString("unallocatedAmount", existing?.overallocatedAmount ?: "0").trim().removePrefix("-")
                } else {
                    existing?.overallocatedAmount ?: "0"
                },
            ),
            isUnderallocated = summary?.optBoolean("underallocated", existing?.isUnderallocated ?: false)
                ?: payload.optBoolean("isUnderallocated", existing?.isUnderallocated ?: false),
            isOverallocated = summary?.optBoolean("overallocated", existing?.isOverallocated ?: false)
                ?: payload.optBoolean("isOverallocated", existing?.isOverallocated ?: false),
            status = payload.optNullableString("status") ?: summary?.optNullableString("status") ?: existing?.status,
            progressStatus = payload.optNullableString("progressStatus")
                ?: summary?.optNullableString("progressStatus")
                ?: existing?.progressStatus,
            progressPercent = payload.optNullableString("progressPercent")
                ?: summary?.optNullableString("progressPercent")
                ?: existing?.progressPercent,
            version = payload.optIntOrNull("version") ?: existing?.version,
            syncStatus = SYNC_STATUS_SYNCED,
            recordStatus = recordStatus,
            createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
            updatedAtEpochMillis = now,
            deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) {
                existing?.deletedAtEpochMillis ?: now
            } else {
                null
            },
        )
        database.localPlanningPlanDao().upsert(entity)
        payload.optJSONArray("incomeSources")?.toObjectList().orEmpty().forEach { sourcePayload ->
            applyPlanningIncomeSourcePayload(
                userId = userId,
                payload = sourcePayload,
                fallbackEntityId = sourcePayload.optEntityId("incomeSourceId").orEmpty(),
                parentPlanLocalId = entity.localId,
                parentPlanServerId = entity.serverId,
            )
        }
        payload.optJSONArray("allocations")?.toObjectList().orEmpty().forEach { allocationPayload ->
            applyPlanningAllocationPayload(
                userId = userId,
                payload = allocationPayload,
                fallbackEntityId = allocationPayload.optEntityId("allocationId").orEmpty(),
                parentPlanLocalId = entity.localId,
                parentPlanServerId = entity.serverId,
            )
        }
    }

    private suspend fun markPlanningPlanDeleted(
        userId: String,
        entityId: String,
        version: Int?,
        tombstonePayload: JSONObject?,
    ) {
        val existing = database.localPlanningPlanDao().findByServerId(userId, entityId)
            ?: database.localPlanningPlanDao().findByLocalId(userId, entityId)
        val now = nowEpochMillis()
        database.localPlanningPlanDao().upsert(
            (existing ?: tombstonePayload.toDeletedPlanningPlanEntity(userId, entityId, now)).copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: tombstonePayload?.optIntOrNull("version") ?: existing?.version,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis ?: now,
            ),
        )
    }

    private suspend fun applyPlanningIncomeSourcePayload(
        userId: String,
        payload: JSONObject,
        fallbackEntityId: String,
        parentPlanLocalId: String? = null,
        parentPlanServerId: String? = null,
    ) {
        val serverId = payload.optEntityId("incomeSourceId") ?: fallbackEntityId
        val existing = database.localPlanningIncomeSourceDao().findByServerId(userId, serverId)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, fallbackEntityId)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, serverId)
        val planServerId = payload.optNullableString("planId") ?: parentPlanServerId ?: existing?.planServerId
        val plan = planServerId?.let { findPlanningPlanByAnyId(userId, it) }
            ?: parentPlanLocalId?.let { findPlanningPlanByAnyId(userId, it) }
        val now = nowEpochMillis()
        val recordStatus = payload.recordStatus(existing?.recordStatus)
        database.localPlanningIncomeSourceDao().upsert(
            LocalPlanningIncomeSourceEntity(
                localId = existing?.localId ?: fallbackEntityId.ifBlank { serverId },
                userId = userId,
                serverId = serverId,
                planLocalId = plan?.localId ?: existing?.planLocalId ?: planServerId.orEmpty(),
                planServerId = plan?.serverId ?: planServerId ?: existing?.planServerId,
                amount = payload.optString("amount", existing?.amount ?: "0"),
                source = payload.optString("source", existing?.source ?: ""),
                description = payload.optNullableStringOrExisting("description", existing?.description),
                dayOfMonth = payload.optIntOrExisting("dayOfMonth", existing?.dayOfMonth),
                confirmed = payload.optString("confirmationState").ifBlank {
                    if (payload.has("confirmed")) {
                        if (payload.optBoolean("confirmed", existing?.confirmed ?: false)) "confirmed" else "planned"
                    } else {
                        if (existing?.confirmed == true) "confirmed" else "planned"
                    }
                } == "confirmed",
                effectiveDate = payload.optNullableStringOrExisting("effectiveDate", existing?.effectiveDate),
                version = payload.optIntOrNull("version") ?: existing?.version,
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = recordStatus,
                createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) {
                    existing?.deletedAtEpochMillis ?: now
                } else {
                    null
                },
            ),
        )
    }

    private suspend fun markPlanningIncomeSourceDeleted(
        userId: String,
        entityId: String,
        version: Int?,
        tombstonePayload: JSONObject?,
    ) {
        val existing = database.localPlanningIncomeSourceDao().findByServerId(userId, entityId)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, entityId)
        val now = nowEpochMillis()
        database.localPlanningIncomeSourceDao().upsert(
            (existing ?: tombstonePayload.toDeletedPlanningIncomeSourceEntity(userId, entityId, now)).copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: tombstonePayload?.optIntOrNull("version") ?: existing?.version,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis ?: now,
            ),
        )
    }

    private suspend fun applyPlanningAllocationPayload(
        userId: String,
        payload: JSONObject,
        fallbackEntityId: String,
        parentPlanLocalId: String? = null,
        parentPlanServerId: String? = null,
    ) {
        val serverId = payload.optEntityId("allocationId") ?: fallbackEntityId
        val existing = database.localPlanningAllocationDao().findByServerId(userId, serverId)
            ?: database.localPlanningAllocationDao().findByLocalId(userId, fallbackEntityId)
            ?: database.localPlanningAllocationDao().findByLocalId(userId, serverId)
        val planServerId = payload.optNullableString("planId") ?: parentPlanServerId ?: existing?.planServerId
        val plan = planServerId?.let { findPlanningPlanByAnyId(userId, it) }
            ?: parentPlanLocalId?.let { findPlanningPlanByAnyId(userId, it) }
        val targetType = payload.planningAllocationTargetType(existing?.targetType)
        val now = nowEpochMillis()
        val recordStatus = payload.recordStatus(existing?.recordStatus)
        database.localPlanningAllocationDao().upsert(
            LocalPlanningAllocationEntity(
                localId = existing?.localId ?: fallbackEntityId.ifBlank { serverId },
                userId = userId,
                serverId = serverId,
                planLocalId = plan?.localId ?: existing?.planLocalId ?: planServerId.orEmpty(),
                planServerId = plan?.serverId ?: planServerId ?: existing?.planServerId,
                targetType = targetType,
                targetId = payload.planningAllocationTargetId(targetType) ?: existing?.targetId,
                targetSnapshot = payload.optNullableJsonString("targetSnapshot") ?: existing?.targetSnapshot,
                requiresAttention = payload.optBoolean("requiresAttention", existing?.requiresAttention ?: false),
                attentionReason = payload.optNullableStringOrExisting("attentionReason", existing?.attentionReason),
                comment = payload.optNullableStringOrExisting("comment", existing?.comment),
                allocationMode = payload.optString("allocationMode", existing?.allocationMode ?: "amount"),
                allocationValue = payload.optString("allocationValue", existing?.allocationValue ?: "0"),
                calculatedAmount = payload.optString("calculatedAmount", existing?.calculatedAmount ?: "0"),
                recurrenceType = payload.optNullableStringOrExisting("recurrenceType", existing?.recurrenceType),
                isSavingsGoal = payload.optBoolean("isSavingsGoal", payload.optBoolean("savingsGoal", existing?.isSavingsGoal ?: false)),
                goalTargetAmount = payload.optNullableStringOrExisting("goalTargetAmount", existing?.goalTargetAmount),
                goalDueMonth = payload.optNullableStringOrExisting("goalDueMonth", existing?.goalDueMonth),
                goalMonthlyAmount = payload.optNullableStringOrExisting("goalMonthlyAmount", existing?.goalMonthlyAmount),
                actualAmount = payload.optNullableStringOrExisting("actualAmount", existing?.actualAmount),
                varianceAmount = payload.optNullableStringOrExisting("varianceAmount", existing?.varianceAmount),
                progressPercent = payload.optNullableStringOrExisting("progressPercent", existing?.progressPercent),
                progressStatus = payload.optNullableStringOrExisting("progressStatus", existing?.progressStatus),
                status = payload.optNullableStringOrExisting("status", existing?.status),
                version = payload.optIntOrNull("version") ?: existing?.version,
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = recordStatus,
                createdAtEpochMillis = existing?.createdAtEpochMillis ?: now,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) {
                    existing?.deletedAtEpochMillis ?: now
                } else {
                    null
                },
            ),
        )
    }

    private suspend fun markPlanningAllocationDeleted(
        userId: String,
        entityId: String,
        version: Int?,
        tombstonePayload: JSONObject?,
    ) {
        val existing = database.localPlanningAllocationDao().findByServerId(userId, entityId)
            ?: database.localPlanningAllocationDao().findByLocalId(userId, entityId)
        val now = nowEpochMillis()
        database.localPlanningAllocationDao().upsert(
            (existing ?: tombstonePayload.toDeletedPlanningAllocationEntity(userId, entityId, now)).copy(
                syncStatus = SYNC_STATUS_SYNCED,
                recordStatus = RECORD_STATUS_DELETED,
                version = version ?: tombstonePayload?.optIntOrNull("version") ?: existing?.version,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = existing?.deletedAtEpochMillis ?: now,
            ),
        )
    }

    private suspend fun markAccountPendingUpdate(userId: String, entityId: String, payload: JSONObject) {
        val existing = database.localAccountDao().findByServerId(userId, entityId)
            ?: database.localAccountDao().findByLocalId(userId, entityId)
            ?: return
        database.localAccountDao().upsert(
            existing.copy(
                name = payload.optString("name", existing.name),
                accountType = payload.optString("accountType", existing.accountType),
                currency = payload.optString("currency", existing.currency),
                assetCategoryId = payload.optNullableStringOrExisting("assetCategoryId", existing.assetCategoryId),
                isPaymentAccount = payload.optBoolean("isPaymentAccount", existing.isPaymentAccount),
                syncStatus = SYNC_STATUS_PENDING,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun markAccountRecordStatus(userId: String, entityId: String, recordStatus: String) {
        val existing = database.localAccountDao().findByServerId(userId, entityId)
            ?: database.localAccountDao().findByLocalId(userId, entityId)
            ?: return
        val now = nowEpochMillis()
        database.localAccountDao().upsert(
            existing.copy(
                syncStatus = SYNC_STATUS_PENDING,
                recordStatus = recordStatus,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) now else null,
            ),
        )
    }

    private suspend fun markCategoryPendingUpdate(userId: String, entityId: String, payload: JSONObject) {
        val existing = database.localCategoryDao().findByServerId(userId, entityId)
            ?: database.localCategoryDao().findByLocalId(userId, entityId)
            ?: return
        database.localCategoryDao().upsert(
            existing.copy(
                name = payload.optString("name", existing.name),
                iconKey = payload.optNullableStringOrExisting("iconKey", existing.iconKey).orEmpty(),
                color = payload.optNullableStringOrExisting("color", existing.color).orEmpty(),
                syncStatus = SYNC_STATUS_PENDING,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun markCategoryRecordStatus(userId: String, entityId: String, recordStatus: String) {
        val existing = database.localCategoryDao().findByServerId(userId, entityId)
            ?: database.localCategoryDao().findByLocalId(userId, entityId)
            ?: return
        val now = nowEpochMillis()
        database.localCategoryDao().upsert(
            existing.copy(
                syncStatus = SYNC_STATUS_PENDING,
                recordStatus = recordStatus,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) now else null,
            ),
        )
    }

    private suspend fun markAssetCategoryPendingUpdate(userId: String, entityId: String, payload: JSONObject) {
        val existing = database.localAssetCategoryDao().findByServerId(userId, entityId)
            ?: database.localAssetCategoryDao().findByLocalId(userId, entityId)
            ?: return
        database.localAssetCategoryDao().upsert(
            existing.copy(
                name = payload.optString("name", existing.name),
                manualAmount = payload.optString("manualAmount", existing.manualAmount),
                isInvestment = payload.optBoolean("isInvestment", existing.isInvestment),
                assetType = payload.optString("assetType", existing.assetType),
                iconKey = payload.optNullableStringOrExisting("iconKey", existing.iconKey).orEmpty(),
                syncStatus = SYNC_STATUS_PENDING,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun markAssetCategoryRecordStatus(userId: String, entityId: String, recordStatus: String) {
        val existing = database.localAssetCategoryDao().findByServerId(userId, entityId)
            ?: database.localAssetCategoryDao().findByLocalId(userId, entityId)
            ?: return
        val now = nowEpochMillis()
        database.localAssetCategoryDao().upsert(
            existing.copy(
                syncStatus = SYNC_STATUS_PENDING,
                recordStatus = recordStatus,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) now else null,
            ),
        )
    }

    private suspend fun markPlanningIncomeSourcePendingUpdate(userId: String, entityId: String, payload: JSONObject) {
        val existing = database.localPlanningIncomeSourceDao().findByServerId(userId, entityId)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, entityId)
            ?: return
        database.localPlanningIncomeSourceDao().upsert(
            existing.copy(
                amount = payload.optString("amount", existing.amount),
                source = payload.optString("source", existing.source),
                description = payload.optNullableStringOrExisting("description", existing.description),
                dayOfMonth = payload.optIntOrExisting("dayOfMonth", existing.dayOfMonth),
                confirmed = payload.optBoolean("confirmed", existing.confirmed),
                effectiveDate = payload.optNullableStringOrExisting("effectiveDate", existing.effectiveDate),
                syncStatus = SYNC_STATUS_PENDING,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun markPlanningIncomeSourceConfirmed(userId: String, entityId: String) {
        val existing = database.localPlanningIncomeSourceDao().findByServerId(userId, entityId)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, entityId)
            ?: return
        database.localPlanningIncomeSourceDao().upsert(
            existing.copy(
                confirmed = true,
                syncStatus = SYNC_STATUS_PENDING,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun markPlanningIncomeSourceRecordStatus(
        userId: String,
        entityId: String,
        recordStatus: String,
    ) {
        val existing = database.localPlanningIncomeSourceDao().findByServerId(userId, entityId)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, entityId)
            ?: return
        val now = nowEpochMillis()
        database.localPlanningIncomeSourceDao().upsert(
            existing.copy(
                syncStatus = SYNC_STATUS_PENDING,
                recordStatus = recordStatus,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) now else null,
            ),
        )
    }

    private suspend fun markPlanningAllocationPendingUpdate(userId: String, entityId: String, payload: JSONObject) {
        val existing = database.localPlanningAllocationDao().findByServerId(userId, entityId)
            ?: database.localPlanningAllocationDao().findByLocalId(userId, entityId)
            ?: return
        val targetType = payload.optString("targetType", existing.targetType)
        database.localPlanningAllocationDao().upsert(
            existing.copy(
                targetType = targetType,
                targetId = payload.optNullableStringOrExisting("targetId", existing.targetId),
                targetSnapshot = payload.optNullableJsonString("targetSnapshot") ?: existing.targetSnapshot,
                requiresAttention = payload.optBoolean("requiresAttention", existing.requiresAttention),
                attentionReason = payload.optNullableStringOrExisting("attentionReason", existing.attentionReason),
                comment = payload.optNullableStringOrExisting("comment", existing.comment),
                allocationMode = payload.optString("allocationMode", existing.allocationMode),
                allocationValue = payload.optString("allocationValue", existing.allocationValue),
                calculatedAmount = if (payload.optString("allocationMode", existing.allocationMode) == "amount") {
                    payload.optString("allocationValue", existing.calculatedAmount)
                } else {
                    existing.calculatedAmount
                },
                recurrenceType = payload.optNullableStringOrExisting("recurrenceType", existing.recurrenceType),
                isSavingsGoal = payload.optBoolean("isSavingsGoal", existing.isSavingsGoal),
                goalTargetAmount = payload.optNullableStringOrExisting("goalTargetAmount", existing.goalTargetAmount),
                goalDueMonth = payload.optNullableStringOrExisting("goalDueMonth", existing.goalDueMonth),
                syncStatus = SYNC_STATUS_PENDING,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    private suspend fun markPlanningAllocationRecordStatus(userId: String, entityId: String, recordStatus: String) {
        val existing = database.localPlanningAllocationDao().findByServerId(userId, entityId)
            ?: database.localPlanningAllocationDao().findByLocalId(userId, entityId)
            ?: return
        val now = nowEpochMillis()
        database.localPlanningAllocationDao().upsert(
            existing.copy(
                syncStatus = SYNC_STATUS_PENDING,
                recordStatus = recordStatus,
                updatedAtEpochMillis = now,
                deletedAtEpochMillis = if (recordStatus == RECORD_STATUS_DELETED) now else null,
            ),
        )
    }

    private suspend fun findPlanningPlanByAnyId(userId: String, planId: String): LocalPlanningPlanEntity? {
        return database.localPlanningPlanDao().findByServerId(userId, planId)
            ?: database.localPlanningPlanDao().findByLocalId(userId, planId)
    }

    companion object {
        const val ENTITY_TRANSACTIONS = "transactions"
        const val ENTITY_ACCOUNTS = "accounts"
        const val ENTITY_CATEGORIES = "categories"
        const val ENTITY_ASSET_CATEGORIES = "asset_categories"
        const val ENTITY_INVESTMENT_MIGRATIONS = "investment_migrations"
        const val ENTITY_PLANNING_PLANS = "planning_plans"
        const val ENTITY_PLANNING_INCOME_SOURCES = "planning_income_sources"
        const val ENTITY_PLANNING_ALLOCATIONS = "planning_allocations"
        const val ENTITY_CAPTURE_DRAFTS = "capture_drafts"
        const val ENTITY_OCR = "ocr"
        const val ENTITY_SCREENSHOTS = "screenshots"
        val PLANNING_ENTITY_TYPES = listOf(
            ENTITY_PLANNING_PLANS,
            ENTITY_PLANNING_INCOME_SOURCES,
            ENTITY_PLANNING_ALLOCATIONS,
        )
        val SYNC_PUSH_ENTITY_TYPES = setOf(
            ENTITY_TRANSACTIONS,
            ENTITY_ACCOUNTS,
            ENTITY_CATEGORIES,
            ENTITY_ASSET_CATEGORIES,
            ENTITY_INVESTMENT_MIGRATIONS,
            *PLANNING_ENTITY_TYPES.toTypedArray(),
        )
        val ONLINE_ONLY_ENTITY_TYPES = setOf(
            ENTITY_CAPTURE_DRAFTS,
            ENTITY_OCR,
            ENTITY_SCREENSHOTS,
            "capture",
            "captures",
            "screenshot",
            "screenshot_ocr",
        )
        val SYNC_PULL_ENTITY_TYPES = listOf(
            ENTITY_TRANSACTIONS,
            ENTITY_ACCOUNTS,
            ENTITY_CATEGORIES,
            ENTITY_ASSET_CATEGORIES,
            *PLANNING_ENTITY_TYPES.toTypedArray(),
        )
        const val OPERATION_CREATE = "create"
        const val OPERATION_UPDATE = "update"
        const val OPERATION_ARCHIVE = "archive"
        const val OPERATION_DELETE = "delete"
        const val OPERATION_RESTORE = "restore"
        const val OPERATION_CONFIRM = "confirm"

        const val SYNC_STATUS_PENDING = "pending"
        const val SYNC_STATUS_SYNCED = "synced"
        const val RECORD_STATUS_ACTIVE = "active"
        const val RECORD_STATUS_ARCHIVED = "archived"
        const val RECORD_STATUS_DELETED = "deleted"

        const val MUTATION_STATUS_QUEUED = "queued"
        const val MUTATION_STATUS_RETRY = "retry"
        const val MUTATION_STATUS_APPLIED = "applied"
        const val MUTATION_STATUS_REJECTED = "rejected"
        const val MUTATION_STATUS_FAILED = "failed"

        fun isSyncableEntityType(entityType: String): Boolean = entityType in SYNC_PUSH_ENTITY_TYPES

        fun requireSyncableEntityType(entityType: String) {
            require(isSyncableEntityType(entityType)) {
                if (entityType in ONLINE_ONLY_ENTITY_TYPES) {
                    "OCR/screenshot capture is online-only and must not be queued for sync."
                } else {
                    "Unsupported sync entity type: $entityType"
                }
            }
        }

        fun transactionPayload(
            transactionType: String,
            amount: String,
            currency: String,
            accountId: String,
            categoryId: String? = null,
            counterpartyAccountId: String? = null,
            transactionDate: String,
            note: String? = null,
        ): JSONObject {
            return JSONObject()
                .put("transactionType", transactionType)
                .put("accountId", accountId)
                .put("amount", amount)
                .put("currency", currency)
                .put("transactionDate", transactionDate)
                .put("sourceType", "manual")
                .apply {
                    categoryId?.takeIf { it.isNotBlank() }?.let { put("categoryId", it) }
                    counterpartyAccountId?.takeIf { it.isNotBlank() }?.let { put("counterpartyAccountId", it) }
                    note?.let { put("description", it) }
                }
        }

        fun accountCreatePayload(
            name: String,
            accountType: String,
            ownershipType: String,
            currency: String,
            initialBalance: String,
            householdId: String? = null,
            assetCategoryId: String? = null,
            isPaymentAccount: Boolean = true,
        ): JSONObject {
            return JSONObject()
                .put("name", name)
                .put("accountType", accountType)
                .put("ownershipType", ownershipType)
                .put("currency", currency)
                .put("initialBalance", initialBalance)
                .put("isPaymentAccount", isPaymentAccount)
                .apply {
                    householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) }
                    assetCategoryId?.takeIf { it.isNotBlank() }?.let { put("assetCategoryId", it) }
                }
        }

        fun accountUpdatePayload(
            baseVersion: Int,
            name: String? = null,
            accountType: String? = null,
            currency: String? = null,
            assetCategoryId: String? = null,
            clearAssetCategoryId: Boolean = false,
            isPaymentAccount: Boolean? = null,
        ): JSONObject {
            return JSONObject()
                .put("version", baseVersion)
                .apply {
                    name?.let { put("name", it) }
                    accountType?.let { put("accountType", it) }
                    currency?.let { put("currency", it) }
                    when {
                        clearAssetCategoryId -> put("assetCategoryId", JSONObject.NULL)
                        assetCategoryId != null -> put("assetCategoryId", assetCategoryId)
                    }
                    isPaymentAccount?.let { put("isPaymentAccount", it) }
                }
        }

        fun categoryCreatePayload(
            name: String,
            categoryType: String,
            scope: String,
            householdId: String? = null,
            iconKey: String? = null,
            color: String? = null,
        ): JSONObject {
            return JSONObject()
                .put("name", name)
                .put("type", categoryType)
                .put("scope", scope)
                .apply {
                    householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) }
                    iconKey?.takeIf { it.isNotBlank() }?.let { put("iconKey", it) }
                    color?.takeIf { it.isNotBlank() }?.let { put("color", it) }
                }
        }

        fun categoryUpdatePayload(
            baseVersion: Int,
            name: String? = null,
            iconKey: String? = null,
            clearIconKey: Boolean = false,
            color: String? = null,
            clearColor: Boolean = false,
        ): JSONObject {
            return JSONObject()
                .put("version", baseVersion)
                .apply {
                    name?.let { put("name", it) }
                    when {
                        clearIconKey -> put("iconKey", JSONObject.NULL)
                        iconKey != null -> put("iconKey", iconKey)
                    }
                    when {
                        clearColor -> put("color", JSONObject.NULL)
                        color != null -> put("color", color)
                    }
                }
        }

        fun assetCategoryCreatePayload(
            name: String,
            scopeType: String,
            currency: String,
            manualAmount: String,
            isInvestment: Boolean,
            assetType: String,
            householdId: String? = null,
            iconKey: String? = null,
        ): JSONObject {
            return JSONObject()
                .put("name", name)
                .put("scopeType", scopeType)
                .put("currency", currency)
                .put("manualAmount", manualAmount)
                .put("isInvestment", isInvestment)
                .put("assetType", assetType)
                .apply {
                    householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) }
                    iconKey?.takeIf { it.isNotBlank() }?.let { put("iconKey", it) }
                }
        }

        fun assetCategoryUpdatePayload(
            baseVersion: Int,
            name: String? = null,
            manualAmount: String? = null,
            isInvestment: Boolean? = null,
            assetType: String? = null,
            iconKey: String? = null,
            clearIconKey: Boolean = false,
        ): JSONObject {
            return JSONObject()
                .put("version", baseVersion)
                .apply {
                    name?.let { put("name", it) }
                    manualAmount?.let { put("manualAmount", it) }
                    isInvestment?.let { put("isInvestment", it) }
                    assetType?.let { put("assetType", it) }
                    when {
                        clearIconKey -> put("iconKey", JSONObject.NULL)
                        iconKey != null -> put("iconKey", iconKey)
                    }
                }
        }

        fun investmentMigrationCreatePayload(request: InvestmentMigrationCreateRequest): JSONObject {
            return JSONObject()
                .put("assetCategoryId", request.assetCategoryId)
                .put("name", request.name)
                .apply {
                    request.iconKey?.takeIf { it.isNotBlank() }?.let { put("icon", it) }
                    request.color?.takeIf { it.isNotBlank() }?.let { put("color", it) }
                }
                .put("assetType", request.assetType)
                .put("currency", request.currency)
                .put("scope", if (request.scope == "household" || request.scope == "shared") "household" else "personal")
                .apply {
                    request.householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) }
                }
                .put(
                    "accountIds",
                    JSONArray().apply {
                        request.accountIds.forEach { put(it) }
                    },
                )
                .put(
                    "accountVersions",
                    JSONObject().apply {
                        request.accountIds.forEach { accountId ->
                            request.accountVersions[accountId]?.let { put(accountId, it) }
                        }
                        request.accountVersions.keys
                            .filterNot { it in request.accountIds }
                            .sorted()
                            .forEach { accountId -> put(accountId, request.accountVersions.getValue(accountId)) }
                    },
                )
        }

        fun planningPlanCreatePayload(request: PlanningPlanCreateRequest): JSONObject {
            return JSONObject()
                .put("scope", request.scope)
                .put("month", request.month)
                .put("currency", request.currency)
                .apply {
                    request.householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) }
                }
        }

        fun planningIncomeSourceCreatePayload(
            planId: String,
            request: PlanningIncomeSourceCreateRequest,
        ): JSONObject {
            return JSONObject()
                .put("planId", planId)
                .put("amount", request.amount)
                .put("source", request.source)
                .put("dayOfMonth", request.dayOfMonth)
                .apply {
                    request.description?.let { put("description", it) }
                    request.effectiveDate?.let { put("effectiveDate", it) }
                }
        }

        fun planningIncomeSourceUpdatePayload(
            baseVersion: Int,
            request: PlanningIncomeSourceUpdateRequest,
        ): JSONObject {
            return JSONObject()
                .put("version", baseVersion)
                .apply {
                    request.amount?.let { put("amount", it) }
                    request.source?.let { put("source", it) }
                    request.description?.let { put("description", it) }
                    request.dayOfMonth?.let { put("dayOfMonth", it) }
                    request.confirmed?.let { put("confirmed", it) }
                    request.effectiveDate?.let { put("effectiveDate", it) }
                }
        }

        fun planningAllocationCreatePayload(
            planId: String,
            request: PlanningAllocationCreateRequest,
        ): JSONObject {
            return JSONObject()
                .put("planId", planId)
                .put("targetType", request.targetType)
                .put("targetId", request.targetId)
                .put("allocationMode", request.allocationMode)
                .put("allocationValue", request.allocationValue)
                .put("isSavingsGoal", request.isSavingsGoal)
                .apply {
                    request.targetSnapshot?.let { put("targetSnapshot", it) }
                    request.comment?.let { put("comment", it) }
                    request.recurrenceType?.let { put("recurrenceType", it) }
                    if (request.isSavingsGoal) {
                        request.goalTargetAmount?.let { put("goalTargetAmount", it) }
                        request.goalDueMonth?.let { put("goalDueMonth", it) }
                    }
                }
        }

        fun planningAllocationUpdatePayload(
            baseVersion: Int,
            request: PlanningAllocationUpdateRequest,
        ): JSONObject {
            return JSONObject()
                .put("version", baseVersion)
                .apply {
                    request.targetType?.let { put("targetType", it) }
                    request.targetId?.let { put("targetId", it) }
                    request.targetSnapshot?.let { put("targetSnapshot", it) }
                    request.requiresAttention?.let { put("requiresAttention", it) }
                    request.attentionReason?.let { put("attentionReason", it) }
                    request.comment?.let { put("comment", it) }
                    request.allocationMode?.let { put("allocationMode", it) }
                    request.allocationValue?.let { put("allocationValue", it) }
                    request.recurrenceType?.let { put("recurrenceType", it) }
                    request.isSavingsGoal?.let { put("isSavingsGoal", it) }
                    if (request.isSavingsGoal == false) {
                        put("goalTargetAmount", JSONObject.NULL)
                        put("goalDueMonth", JSONObject.NULL)
                    } else {
                        request.goalTargetAmount?.let { put("goalTargetAmount", it) }
                        request.goalDueMonth?.let { put("goalDueMonth", it) }
                    }
                }
        }

        fun stableMutationId(
            deviceId: String,
            entityType: String = ENTITY_TRANSACTIONS,
            entityId: String,
            operation: String,
            baseVersion: Int?,
            payloadJson: String?,
        ): String {
            val hashInput = listOf(entityId, operation, baseVersion?.toString().orEmpty(), payloadJson.orEmpty())
                .joinToString("|")
            val hash = MessageDigest.getInstance("SHA-256")
                .digest(hashInput.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
                .take(16)
            return "$deviceId:$entityType:$entityId:$operation:$hash".take(160)
        }
    }
}

data class SyncPushSummary(
    val pushed: Int = 0,
    val applied: Int = 0,
    val rejected: Int = 0,
    val retry: Int = 0,
    val failed: Int = 0,
)

data class SyncOnceSummary(
    val push: SyncPushSummary,
    val pullSucceeded: Boolean,
)

data class SyncIssueSummary(
    val entityType: String,
    val operation: String,
    val status: String,
    val lastError: String?,
    val attempts: Int,
    val updatedAtEpochMillis: Long,
    val createdAtEpochMillis: Long,
)

private fun PendingMutationEntity.toSyncMutationRequest(): SyncMutationRequest {
    return SyncMutationRequest(
        clientMutationId = clientMutationId,
        entityType = entityType,
        entityId = entityId,
        operation = operation,
        baseVersion = baseVersion,
        payload = payloadJson?.let(::JSONObject),
    )
}

private fun Int?.isRetriableStatus(): Boolean {
    return this == null || this == 408 || this == 429 || this >= 500
}

private fun String?.isRetriableSyncError(): Boolean {
    return this in setOf("RATE_LIMITED", "LOCK_TIMEOUT", "TEMPORARY_UNAVAILABLE")
}

private fun JSONObject.optIntOrNull(name: String): Int? = if (has(name) && !isNull(name)) optInt(name) else null

private fun JSONObject.optNullableString(name: String): String? {
    return optString(name).takeIf { has(name) && !isNull(name) && it.isNotBlank() && it != "null" }
}

private fun JSONObject.optNullableStringOrExisting(name: String, existing: String?): String? {
    return if (has(name)) optNullableString(name) else existing
}

private fun JSONObject.optIntOrExisting(name: String, existing: Int?): Int? {
    return if (has(name)) {
        if (isNull(name)) null else optInt(name)
    } else {
        existing
    }
}

private fun JSONObject.optNullableJsonString(name: String): String? {
    if (!has(name) || isNull(name)) return null
    val value = opt(name) ?: return null
    return when (value) {
        is JSONObject, is JSONArray -> value.toString()
        else -> value.toString().takeIf { it.isNotBlank() && it != "null" }
    }
}

private fun JSONObject.optEntityId(alias: String): String? {
    return optNullableString("id") ?: optNullableString(alias)
}

private fun JSONObject.recordStatus(existing: String?): String {
    return optString("recordStatus", optString("status", existing ?: SyncManager.RECORD_STATUS_ACTIVE))
}

private fun JSONObject.planningAllocationTargetType(existing: String? = null): String {
    val explicit = optString("targetType").takeIf { it.isNotBlank() && it != "null" }
    return explicit ?: existing ?: when {
        optNullableString("assetCategoryId") != null -> "investment_asset_category"
        optNullableString("assetId") != null -> "asset"
        optNullableString("accountId") != null -> "account"
        optNullableString("categoryId") != null -> "expense_category"
        else -> ""
    }
}

private fun JSONObject.planningAllocationTargetId(targetType: String): String? {
    return optNullableString("targetId") ?: when (targetType) {
        "investment_asset_category" -> optNullableString("assetCategoryId")
        "asset" -> optNullableString("assetId")
        "account" -> optNullableString("accountId")
        "expense_category" -> optNullableString("categoryId")
        else -> optNullableString("assetId")
            ?: optNullableString("accountId")
            ?: optNullableString("categoryId")
    }
}

private fun JSONArray.toObjectList(): List<JSONObject> {
    return (0 until length()).mapNotNull { index -> optJSONObject(index) }
}

private fun JSONObject?.toDeletedAccountEntity(
    userId: String,
    entityId: String,
    nowEpochMillis: Long,
): LocalAccountEntity {
    val payload = this
    val fallbackBalance = payload?.optString("initialBalance", "0") ?: "0"
    return LocalAccountEntity(
        localId = entityId,
        userId = userId,
        serverId = entityId,
        name = payload?.optString("name", "").orEmpty(),
        accountType = payload?.optString("accountType", "cash") ?: "cash",
        ownershipType = payload?.optString("ownershipType", "personal") ?: "personal",
        currency = payload?.optString("currency", "USD") ?: "USD",
        currentBalance = payload?.optString("currentBalance", fallbackBalance) ?: "0",
        householdId = payload?.optNullableString("householdId"),
        assetCategoryId = payload?.optNullableString("assetCategoryId"),
        isPaymentAccount = payload?.optBoolean("isPaymentAccount", true) ?: true,
        version = payload?.optIntOrNull("version"),
        syncStatus = SyncManager.SYNC_STATUS_SYNCED,
        recordStatus = SyncManager.RECORD_STATUS_DELETED,
        createdAtEpochMillis = nowEpochMillis,
        updatedAtEpochMillis = nowEpochMillis,
        deletedAtEpochMillis = nowEpochMillis,
    )
}

private fun JSONObject?.toDeletedCategoryEntity(
    userId: String,
    entityId: String,
    nowEpochMillis: Long,
): LocalCategoryEntity {
    val payload = this
    val fallbackCategoryType = payload?.optString("categoryType", "expense") ?: "expense"
    return LocalCategoryEntity(
        localId = entityId,
        userId = userId,
        serverId = entityId,
        name = payload?.optString("name", "").orEmpty(),
        categoryType = payload?.optString("type", fallbackCategoryType) ?: "expense",
        scope = payload?.optString("scope", "personal") ?: "personal",
        householdId = payload?.optNullableString("householdId"),
        iconKey = payload?.optString("iconKey", "") ?: "",
        color = payload?.optString("color", "") ?: "",
        version = payload?.optIntOrNull("version"),
        syncStatus = SyncManager.SYNC_STATUS_SYNCED,
        recordStatus = SyncManager.RECORD_STATUS_DELETED,
        createdAtEpochMillis = nowEpochMillis,
        updatedAtEpochMillis = nowEpochMillis,
        deletedAtEpochMillis = nowEpochMillis,
    )
}

private fun JSONObject?.toDeletedAssetCategoryEntity(
    userId: String,
    entityId: String,
    nowEpochMillis: Long,
): LocalAssetCategoryEntity {
    val payload = this
    val fallbackScopeType = payload?.optString("scope", "personal") ?: "personal"
    val fallbackAssetType = payload?.optString("accountType", "bank") ?: "bank"
    return LocalAssetCategoryEntity(
        localId = entityId,
        userId = userId,
        serverId = entityId,
        name = payload?.optString("name", "").orEmpty(),
        scopeType = payload?.optString("scopeType", fallbackScopeType) ?: "personal",
        householdId = payload?.optNullableString("householdId"),
        ownerUserId = payload?.optNullableString("ownerUserId"),
        currency = payload?.optString("currency", "USD") ?: "USD",
        manualAmount = payload?.optString("manualAmount", "0") ?: "0",
        isInvestment = payload?.optBoolean("isInvestment", false) ?: false,
        assetType = payload?.optString("assetType", fallbackAssetType) ?: "bank",
        iconKey = payload?.optString("iconKey", "") ?: "",
        version = payload?.optIntOrNull("version"),
        syncStatus = SyncManager.SYNC_STATUS_SYNCED,
        recordStatus = SyncManager.RECORD_STATUS_DELETED,
        createdAtEpochMillis = nowEpochMillis,
        updatedAtEpochMillis = nowEpochMillis,
        deletedAtEpochMillis = nowEpochMillis,
    )
}

private fun JSONObject?.toDeletedPlanningPlanEntity(
    userId: String,
    entityId: String,
    nowEpochMillis: Long,
): LocalPlanningPlanEntity {
    val payload = this
    val summary = payload?.optJSONObject("summary")
    return LocalPlanningPlanEntity(
        localId = entityId,
        userId = userId,
        serverId = entityId,
        scope = payload?.optString("scope", "personal") ?: "personal",
        month = payload?.optString("month", "") ?: "",
        currency = payload?.optString("currency", "USD") ?: "USD",
        householdId = payload?.optNullableString("householdId"),
        totalPlannedIncome = summary?.optString("totalPlannedIncome", "0")
            ?: payload?.optString("totalPlannedIncome", "0")
            ?: "0",
        previousMonthSurplus = summary?.optString("previousMonthSurplus", "0")
            ?: payload?.optString("previousMonthSurplus", "0")
            ?: "0",
        allocatedTotal = summary?.optString("totalAllocatedAmount", "0")
            ?: payload?.optString("allocatedTotal", "0")
            ?: "0",
        remainingAmount = summary?.optString("unallocatedAmount", "0")
            ?: payload?.optString("remainingAmount", "0")
            ?: "0",
        overallocatedAmount = payload?.optString("overallocatedAmount", "0") ?: "0",
        isUnderallocated = summary?.optBoolean("underallocated", false)
            ?: payload?.optBoolean("isUnderallocated", false)
            ?: false,
        isOverallocated = summary?.optBoolean("overallocated", false)
            ?: payload?.optBoolean("isOverallocated", false)
            ?: false,
        status = payload?.optNullableString("status"),
        progressStatus = payload?.optNullableString("progressStatus"),
        progressPercent = payload?.optNullableString("progressPercent"),
        version = payload?.optIntOrNull("version"),
        syncStatus = SyncManager.SYNC_STATUS_SYNCED,
        recordStatus = SyncManager.RECORD_STATUS_DELETED,
        createdAtEpochMillis = nowEpochMillis,
        updatedAtEpochMillis = nowEpochMillis,
        deletedAtEpochMillis = nowEpochMillis,
    )
}

private fun JSONObject?.toDeletedPlanningIncomeSourceEntity(
    userId: String,
    entityId: String,
    nowEpochMillis: Long,
): LocalPlanningIncomeSourceEntity {
    val payload = this
    val planId = payload?.optNullableString("planId").orEmpty()
    return LocalPlanningIncomeSourceEntity(
        localId = entityId,
        userId = userId,
        serverId = entityId,
        planLocalId = planId,
        planServerId = planId.takeIf { it.isNotBlank() },
        amount = payload?.optString("amount", "0") ?: "0",
        source = payload?.optString("source", "") ?: "",
        description = payload?.optNullableString("description"),
        dayOfMonth = payload?.optIntOrNull("dayOfMonth"),
        confirmed = payload?.optString("confirmationState").orEmpty().ifBlank {
            if (payload?.optBoolean("confirmed", false) == true) "confirmed" else "planned"
        } == "confirmed",
        effectiveDate = payload?.optNullableString("effectiveDate"),
        version = payload?.optIntOrNull("version"),
        syncStatus = SyncManager.SYNC_STATUS_SYNCED,
        recordStatus = SyncManager.RECORD_STATUS_DELETED,
        createdAtEpochMillis = nowEpochMillis,
        updatedAtEpochMillis = nowEpochMillis,
        deletedAtEpochMillis = nowEpochMillis,
    )
}

private fun JSONObject?.toDeletedPlanningAllocationEntity(
    userId: String,
    entityId: String,
    nowEpochMillis: Long,
): LocalPlanningAllocationEntity {
    val payload = this
    val planId = payload?.optNullableString("planId").orEmpty()
    val targetType = payload?.planningAllocationTargetType() ?: ""
    return LocalPlanningAllocationEntity(
        localId = entityId,
        userId = userId,
        serverId = entityId,
        planLocalId = planId,
        planServerId = planId.takeIf { it.isNotBlank() },
        targetType = targetType,
        targetId = payload?.planningAllocationTargetId(targetType),
        targetSnapshot = payload?.optNullableJsonString("targetSnapshot"),
        requiresAttention = payload?.optBoolean("requiresAttention", false) ?: false,
        attentionReason = payload?.optNullableString("attentionReason"),
        comment = payload?.optNullableString("comment"),
        allocationMode = payload?.optString("allocationMode", "amount") ?: "amount",
        allocationValue = payload?.optString("allocationValue", "0") ?: "0",
        calculatedAmount = payload?.optString("calculatedAmount", "0") ?: "0",
        recurrenceType = payload?.optNullableString("recurrenceType"),
        isSavingsGoal = payload?.optBoolean("isSavingsGoal", payload.optBoolean("savingsGoal", false)) ?: false,
        goalTargetAmount = payload?.optNullableString("goalTargetAmount"),
        goalDueMonth = payload?.optNullableString("goalDueMonth"),
        goalMonthlyAmount = payload?.optNullableString("goalMonthlyAmount"),
        actualAmount = payload?.optNullableString("actualAmount"),
        varianceAmount = payload?.optNullableString("varianceAmount"),
        progressPercent = payload?.optNullableString("progressPercent"),
        progressStatus = payload?.optNullableString("progressStatus"),
        status = payload?.optNullableString("status"),
        version = payload?.optIntOrNull("version"),
        syncStatus = SyncManager.SYNC_STATUS_SYNCED,
        recordStatus = SyncManager.RECORD_STATUS_DELETED,
        createdAtEpochMillis = nowEpochMillis,
        updatedAtEpochMillis = nowEpochMillis,
        deletedAtEpochMillis = nowEpochMillis,
    )
}
