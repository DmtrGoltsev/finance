package com.finance.mvp.local

import androidx.room.withTransaction
import com.finance.mvp.api.PlanningAllocation
import com.finance.mvp.api.PlanningIncomeSource
import com.finance.mvp.api.PlanningPlan

class PlanningStore(
    private val database: FinanceLocalDatabase,
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
) {
    suspend fun findPlan(
        userId: String,
        scope: String,
        month: String,
        householdId: String?,
    ): PlanningPlan? {
        val plan = database.localPlanningPlanDao().findForScopeMonth(userId, scope, month, householdId)
            ?: return null
        return plan.toPlanningPlan()
    }

    suspend fun history(userId: String, scope: String, householdId: String?): List<PlanningPlan> {
        return database.localPlanningPlanDao()
            .historyForScope(userId = userId, scope = scope, householdId = householdId)
            .map { it.toPlanningPlan() }
    }

    suspend fun pendingPlanningCount(userId: String, entityTypes: List<String>): Int {
        return database.pendingMutationDao().countForUserAndEntityTypes(
            userId = userId,
            statuses = listOf(MUTATION_STATUS_QUEUED, MUTATION_STATUS_RETRY),
            entityTypes = entityTypes,
        )
    }

    suspend fun cachePlan(
        userId: String,
        plan: PlanningPlan,
        syncStatus: String = SYNC_STATUS_SYNCED,
        recordStatus: String = RECORD_STATUS_ACTIVE,
        replaceChildren: Boolean = false,
    ): PlanningPlan {
        return database.withTransaction {
            val now = nowEpochMillis()
            val entity = upsertPlanEntity(
                userId = userId,
                plan = plan,
                syncStatus = syncStatus,
                recordStatus = recordStatus,
                now = now,
            )
            if (replaceChildren) {
                plan.incomeSources.forEach { source ->
                    upsertIncomeSourceEntity(
                        userId = userId,
                        source = source,
                        planLocalId = entity.localId,
                        planServerId = entity.serverId,
                        syncStatus = syncStatus,
                        recordStatus = RECORD_STATUS_ACTIVE,
                        now = now,
                    )
                }
                plan.allocations.forEach { allocation ->
                    upsertAllocationEntity(
                        userId = userId,
                        allocation = allocation,
                        planLocalId = entity.localId,
                        planServerId = entity.serverId,
                        syncStatus = syncStatus,
                        recordStatus = RECORD_STATUS_ACTIVE,
                        now = now,
                    )
                }
                markMissingChildrenDeleted(
                    userId = userId,
                    planLocalId = entity.localId,
                    activeIncomeIds = plan.incomeSources.map { it.id }.toSet(),
                    activeAllocationIds = plan.allocations.map { it.id }.toSet(),
                    now = now,
                )
            }
            entity.toPlanningPlan()
        }
    }

    suspend fun cachePlanSummaries(userId: String, plans: List<PlanningPlan>) {
        database.withTransaction {
            val now = nowEpochMillis()
            plans.forEach { plan ->
                upsertPlanEntity(
                    userId = userId,
                    plan = plan,
                    syncStatus = SYNC_STATUS_SYNCED,
                    recordStatus = RECORD_STATUS_ACTIVE,
                    now = now,
                )
            }
        }
    }

    suspend fun cacheIncomeSource(
        userId: String,
        source: PlanningIncomeSource,
        syncStatus: String = SYNC_STATUS_SYNCED,
        recordStatus: String = RECORD_STATUS_ACTIVE,
    ): PlanningIncomeSource {
        return database.withTransaction {
            val now = nowEpochMillis()
            val plan = findPlanEntityByAnyId(userId, source.planId)
            upsertIncomeSourceEntity(
                userId = userId,
                source = source,
                planLocalId = plan?.localId ?: source.planId,
                planServerId = plan?.serverId ?: source.planId.takeIf { it.isNotBlank() },
                syncStatus = syncStatus,
                recordStatus = recordStatus,
                now = now,
            ).toPlanningIncomeSource()
        }
    }

    suspend fun cacheAllocation(
        userId: String,
        allocation: PlanningAllocation,
        syncStatus: String = SYNC_STATUS_SYNCED,
        recordStatus: String = RECORD_STATUS_ACTIVE,
    ): PlanningAllocation {
        return database.withTransaction {
            val now = nowEpochMillis()
            val plan = findPlanEntityByAnyId(userId, allocation.planId)
            upsertAllocationEntity(
                userId = userId,
                allocation = allocation,
                planLocalId = plan?.localId ?: allocation.planId,
                planServerId = plan?.serverId ?: allocation.planId.takeIf { it.isNotBlank() },
                syncStatus = syncStatus,
                recordStatus = recordStatus,
                now = now,
            ).toPlanningAllocation()
        }
    }

    suspend fun markIncomeSourceDeleted(userId: String, source: PlanningIncomeSource) {
        database.withTransaction {
            val now = nowEpochMillis()
            val existing = findIncomeSourceEntityByAnyId(userId, source.id)
            if (existing != null) {
                database.localPlanningIncomeSourceDao().upsert(
                    existing.copy(
                        syncStatus = SYNC_STATUS_SYNCED,
                        recordStatus = RECORD_STATUS_DELETED,
                        version = source.version ?: existing.version,
                        updatedAtEpochMillis = now,
                        deletedAtEpochMillis = existing.deletedAtEpochMillis ?: now,
                    ),
                )
            } else {
                val plan = findPlanEntityByAnyId(userId, source.planId)
                database.localPlanningIncomeSourceDao().upsert(
                    source.toEntity(
                        userId = userId,
                        localId = source.id,
                        serverId = source.id.takeIf { it.isNotBlank() },
                        planLocalId = plan?.localId ?: source.planId,
                        planServerId = plan?.serverId ?: source.planId.takeIf { it.isNotBlank() },
                        syncStatus = SYNC_STATUS_SYNCED,
                        recordStatus = RECORD_STATUS_DELETED,
                        now = now,
                        deletedAt = now,
                    ),
                )
            }
        }
    }

    suspend fun markAllocationDeleted(userId: String, allocation: PlanningAllocation) {
        database.withTransaction {
            val now = nowEpochMillis()
            val existing = findAllocationEntityByAnyId(userId, allocation.id)
            if (existing != null) {
                database.localPlanningAllocationDao().upsert(
                    existing.copy(
                        syncStatus = SYNC_STATUS_SYNCED,
                        recordStatus = RECORD_STATUS_DELETED,
                        version = allocation.version ?: existing.version,
                        updatedAtEpochMillis = now,
                        deletedAtEpochMillis = existing.deletedAtEpochMillis ?: now,
                    ),
                )
            } else {
                val plan = findPlanEntityByAnyId(userId, allocation.planId)
                database.localPlanningAllocationDao().upsert(
                    allocation.toEntity(
                        userId = userId,
                        localId = allocation.id,
                        serverId = allocation.id.takeIf { it.isNotBlank() },
                        planLocalId = plan?.localId ?: allocation.planId,
                        planServerId = plan?.serverId ?: allocation.planId.takeIf { it.isNotBlank() },
                        syncStatus = SYNC_STATUS_SYNCED,
                        recordStatus = RECORD_STATUS_DELETED,
                        now = now,
                        deletedAt = now,
                    ),
                )
            }
        }
    }

    private suspend fun upsertPlanEntity(
        userId: String,
        plan: PlanningPlan,
        syncStatus: String,
        recordStatus: String,
        now: Long,
    ): LocalPlanningPlanEntity {
        val serverId = plan.id.takeIf { it.isNotBlank() && syncStatus == SYNC_STATUS_SYNCED }
            ?: plan.id.takeIf { it.isNotBlank() && !it.startsWith(LOCAL_ID_PREFIX) }
        val existing = serverId?.let { database.localPlanningPlanDao().findByServerId(userId, it) }
            ?: plan.id.takeIf { it.isNotBlank() }?.let { database.localPlanningPlanDao().findByLocalId(userId, it) }
        val entity = LocalPlanningPlanEntity(
            localId = existing?.localId ?: plan.id,
            userId = userId,
            serverId = serverId ?: existing?.serverId,
            scope = plan.scope,
            month = plan.month,
            currency = plan.currency,
            householdId = plan.householdId,
            totalPlannedIncome = plan.totalPlannedIncome,
            previousMonthSurplus = plan.previousMonthSurplus,
            allocatedTotal = plan.allocatedTotal,
            remainingAmount = plan.remainingAmount,
            overallocatedAmount = plan.overallocatedAmount,
            isUnderallocated = plan.isUnderallocated,
            isOverallocated = plan.isOverallocated,
            status = plan.status,
            progressStatus = plan.progressStatus,
            progressPercent = plan.progressPercent,
            version = plan.version ?: existing?.version,
            syncStatus = syncStatus,
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
        return entity
    }

    private suspend fun upsertIncomeSourceEntity(
        userId: String,
        source: PlanningIncomeSource,
        planLocalId: String,
        planServerId: String?,
        syncStatus: String,
        recordStatus: String,
        now: Long,
    ): LocalPlanningIncomeSourceEntity {
        val serverId = source.id.takeIf { it.isNotBlank() && syncStatus == SYNC_STATUS_SYNCED }
            ?: source.id.takeIf { it.isNotBlank() && !it.startsWith(LOCAL_ID_PREFIX) }
        val existing = serverId?.let { database.localPlanningIncomeSourceDao().findByServerId(userId, it) }
            ?: source.id.takeIf { it.isNotBlank() }?.let {
                database.localPlanningIncomeSourceDao().findByLocalId(userId, it)
            }
        val entity = source.toEntity(
            userId = userId,
            localId = existing?.localId ?: source.id,
            serverId = serverId ?: existing?.serverId,
            planLocalId = existing?.planLocalId ?: planLocalId,
            planServerId = planServerId ?: existing?.planServerId,
            syncStatus = syncStatus,
            recordStatus = recordStatus,
            now = now,
            createdAt = existing?.createdAtEpochMillis,
            deletedAt = if (recordStatus == RECORD_STATUS_DELETED) existing?.deletedAtEpochMillis ?: now else null,
        )
        database.localPlanningIncomeSourceDao().upsert(entity)
        return entity
    }

    private suspend fun upsertAllocationEntity(
        userId: String,
        allocation: PlanningAllocation,
        planLocalId: String,
        planServerId: String?,
        syncStatus: String,
        recordStatus: String,
        now: Long,
    ): LocalPlanningAllocationEntity {
        val serverId = allocation.id.takeIf { it.isNotBlank() && syncStatus == SYNC_STATUS_SYNCED }
            ?: allocation.id.takeIf { it.isNotBlank() && !it.startsWith(LOCAL_ID_PREFIX) }
        val existing = serverId?.let { database.localPlanningAllocationDao().findByServerId(userId, it) }
            ?: allocation.id.takeIf { it.isNotBlank() }?.let {
                database.localPlanningAllocationDao().findByLocalId(userId, it)
            }
        val entity = allocation.toEntity(
            userId = userId,
            localId = existing?.localId ?: allocation.id,
            serverId = serverId ?: existing?.serverId,
            planLocalId = existing?.planLocalId ?: planLocalId,
            planServerId = planServerId ?: existing?.planServerId,
            syncStatus = syncStatus,
            recordStatus = recordStatus,
            now = now,
            createdAt = existing?.createdAtEpochMillis,
            deletedAt = if (recordStatus == RECORD_STATUS_DELETED) existing?.deletedAtEpochMillis ?: now else null,
        )
        database.localPlanningAllocationDao().upsert(entity)
        return entity
    }

    private suspend fun markMissingChildrenDeleted(
        userId: String,
        planLocalId: String,
        activeIncomeIds: Set<String>,
        activeAllocationIds: Set<String>,
        now: Long,
    ) {
        database.localPlanningIncomeSourceDao()
            .listForPlanIncludingDeleted(userId, planLocalId)
            .filter { it.recordStatus != RECORD_STATUS_DELETED && it.syncStatus != SYNC_STATUS_PENDING }
            .filter { row -> activeIncomeIds.none { it == row.serverId || it == row.localId } }
            .forEach { row ->
                database.localPlanningIncomeSourceDao().upsert(
                    row.copy(
                        recordStatus = RECORD_STATUS_DELETED,
                        syncStatus = SYNC_STATUS_SYNCED,
                        updatedAtEpochMillis = now,
                        deletedAtEpochMillis = row.deletedAtEpochMillis ?: now,
                    ),
                )
            }
        database.localPlanningAllocationDao()
            .listForPlanIncludingDeleted(userId, planLocalId)
            .filter { it.recordStatus != RECORD_STATUS_DELETED && it.syncStatus != SYNC_STATUS_PENDING }
            .filter { row -> activeAllocationIds.none { it == row.serverId || it == row.localId } }
            .forEach { row ->
                database.localPlanningAllocationDao().upsert(
                    row.copy(
                        recordStatus = RECORD_STATUS_DELETED,
                        syncStatus = SYNC_STATUS_SYNCED,
                        updatedAtEpochMillis = now,
                        deletedAtEpochMillis = row.deletedAtEpochMillis ?: now,
                    ),
                )
            }
    }

    private suspend fun findPlanEntityByAnyId(userId: String, id: String): LocalPlanningPlanEntity? {
        return database.localPlanningPlanDao().findByServerId(userId, id)
            ?: database.localPlanningPlanDao().findByLocalId(userId, id)
    }

    private suspend fun findIncomeSourceEntityByAnyId(userId: String, id: String): LocalPlanningIncomeSourceEntity? {
        return database.localPlanningIncomeSourceDao().findByServerId(userId, id)
            ?: database.localPlanningIncomeSourceDao().findByLocalId(userId, id)
    }

    private suspend fun findAllocationEntityByAnyId(userId: String, id: String): LocalPlanningAllocationEntity? {
        return database.localPlanningAllocationDao().findByServerId(userId, id)
            ?: database.localPlanningAllocationDao().findByLocalId(userId, id)
    }

    private suspend fun LocalPlanningPlanEntity.toPlanningPlan(): PlanningPlan {
        return PlanningPlan(
            id = serverId ?: localId,
            scope = scope,
            month = month,
            currency = currency,
            householdId = householdId,
            totalPlannedIncome = totalPlannedIncome,
            previousMonthSurplus = previousMonthSurplus,
            allocatedTotal = allocatedTotal,
            remainingAmount = remainingAmount,
            overallocatedAmount = overallocatedAmount,
            isUnderallocated = isUnderallocated,
            isOverallocated = isOverallocated,
            status = status,
            progressStatus = progressStatus,
            progressPercent = progressPercent,
            incomeSources = database.localPlanningIncomeSourceDao()
                .listForPlan(userId, localId)
                .map { it.toPlanningIncomeSource() },
            allocations = database.localPlanningAllocationDao()
                .listForPlan(userId, localId)
                .map { it.toPlanningAllocation() },
            version = version,
        )
    }

    private fun LocalPlanningIncomeSourceEntity.toPlanningIncomeSource(): PlanningIncomeSource {
        return PlanningIncomeSource(
            id = serverId ?: localId,
            planId = planServerId ?: planLocalId,
            amount = amount,
            source = source,
            description = description,
            dayOfMonth = dayOfMonth,
            confirmed = confirmed,
            effectiveDate = effectiveDate,
            version = version,
        )
    }

    private fun LocalPlanningAllocationEntity.toPlanningAllocation(): PlanningAllocation {
        return PlanningAllocation(
            id = serverId ?: localId,
            planId = planServerId ?: planLocalId,
            targetType = targetType,
            targetId = targetId,
            targetSnapshot = targetSnapshot,
            requiresAttention = requiresAttention,
            attentionReason = attentionReason,
            comment = comment,
            allocationMode = allocationMode,
            allocationValue = allocationValue,
            calculatedAmount = calculatedAmount,
            recurrenceType = recurrenceType,
            isSavingsGoal = isSavingsGoal,
            goalTargetAmount = goalTargetAmount,
            goalDueMonth = goalDueMonth,
            goalMonthlyAmount = goalMonthlyAmount,
            actualAmount = actualAmount,
            varianceAmount = varianceAmount,
            progressPercent = progressPercent,
            progressStatus = progressStatus,
            status = status,
            version = version,
        )
    }

    private fun PlanningIncomeSource.toEntity(
        userId: String,
        localId: String,
        serverId: String?,
        planLocalId: String,
        planServerId: String?,
        syncStatus: String,
        recordStatus: String,
        now: Long,
        createdAt: Long? = null,
        deletedAt: Long? = null,
    ): LocalPlanningIncomeSourceEntity {
        return LocalPlanningIncomeSourceEntity(
            localId = localId,
            userId = userId,
            serverId = serverId,
            planLocalId = planLocalId,
            planServerId = planServerId,
            amount = amount,
            source = source,
            description = description,
            dayOfMonth = dayOfMonth,
            confirmed = confirmed,
            effectiveDate = effectiveDate,
            version = version,
            syncStatus = syncStatus,
            recordStatus = recordStatus,
            createdAtEpochMillis = createdAt ?: now,
            updatedAtEpochMillis = now,
            deletedAtEpochMillis = deletedAt,
        )
    }

    private fun PlanningAllocation.toEntity(
        userId: String,
        localId: String,
        serverId: String?,
        planLocalId: String,
        planServerId: String?,
        syncStatus: String,
        recordStatus: String,
        now: Long,
        createdAt: Long? = null,
        deletedAt: Long? = null,
    ): LocalPlanningAllocationEntity {
        return LocalPlanningAllocationEntity(
            localId = localId,
            userId = userId,
            serverId = serverId,
            planLocalId = planLocalId,
            planServerId = planServerId,
            targetType = targetType,
            targetId = targetId,
            targetSnapshot = targetSnapshot,
            requiresAttention = requiresAttention,
            attentionReason = attentionReason,
            comment = comment,
            allocationMode = allocationMode,
            allocationValue = allocationValue,
            calculatedAmount = calculatedAmount,
            recurrenceType = recurrenceType,
            isSavingsGoal = isSavingsGoal,
            goalTargetAmount = goalTargetAmount,
            goalDueMonth = goalDueMonth,
            goalMonthlyAmount = goalMonthlyAmount,
            actualAmount = actualAmount,
            varianceAmount = varianceAmount,
            progressPercent = progressPercent,
            progressStatus = progressStatus,
            status = status,
            version = version,
            syncStatus = syncStatus,
            recordStatus = recordStatus,
            createdAtEpochMillis = createdAt ?: now,
            updatedAtEpochMillis = now,
            deletedAtEpochMillis = deletedAt,
        )
    }

    private companion object {
        const val LOCAL_ID_PREFIX = "local-"
        const val SYNC_STATUS_PENDING = "pending"
        const val SYNC_STATUS_SYNCED = "synced"
        const val RECORD_STATUS_ACTIVE = "active"
        const val RECORD_STATUS_DELETED = "deleted"
        const val MUTATION_STATUS_QUEUED = "queued"
        const val MUTATION_STATUS_RETRY = "retry"
    }
}
