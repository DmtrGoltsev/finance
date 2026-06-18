package com.finance.mvp.sync

import com.finance.mvp.api.ApiFailureKind
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.PlanningAllocation
import com.finance.mvp.api.PlanningAllocationCreateRequest
import com.finance.mvp.api.PlanningAllocationUpdateRequest
import com.finance.mvp.api.PlanningIncomeSource
import com.finance.mvp.api.PlanningIncomeSourceCreateRequest
import com.finance.mvp.api.PlanningIncomeSourceUpdateRequest
import com.finance.mvp.api.PlanningPlan
import com.finance.mvp.api.PlanningPlanCopyRequest
import com.finance.mvp.api.PlanningPlanCreateRequest
import com.finance.mvp.local.FinanceLocalDatabase
import com.finance.mvp.local.PlanningStore

class PlanningRepository(
    database: FinanceLocalDatabase,
    private val apiClient: FinanceApiClient,
    private val syncManager: SyncManager,
    nowEpochMillis: () -> Long = { System.currentTimeMillis() },
) {
    private val store = PlanningStore(database = database, nowEpochMillis = nowEpochMillis)

    suspend fun cachedState(
        userId: String,
        scope: String,
        month: String,
        householdId: String?,
    ): PlanningRepositoryState {
        return PlanningRepositoryState(
            plan = store.findPlan(userId, scope, month, householdId),
            history = store.history(userId, scope, householdId),
            pendingCount = store.pendingPlanningCount(userId, SyncManager.PLANNING_ENTITY_TYPES),
        )
    }

    suspend fun refreshPlan(
        userId: String,
        scope: String,
        month: String,
        householdId: String?,
    ): ApiResult<PlanningPlan?> {
        return when (val currentResult = apiClient.listPlanningPlans(scope, month, householdId)) {
            is ApiResult.Success -> {
                val current = currentResult.value
                if (current == null) {
                    ApiResult.Success(null)
                } else {
                    when (val full = apiClient.getPlanningPlan(current.id)) {
                        is ApiResult.Success -> {
                            ApiResult.Success(
                                store.cachePlan(
                                    userId = userId,
                                    plan = full.value,
                                    replaceChildren = true,
                                ),
                            )
                        }
                        is ApiResult.Failure -> full
                    }
                }
            }
            is ApiResult.Failure -> currentResult
        }
    }

    suspend fun refreshHistory(
        userId: String,
        scope: String,
        householdId: String?,
    ): ApiResult<List<PlanningPlan>> {
        return when (val result = apiClient.listPlanningPlanHistory(scope, householdId)) {
            is ApiResult.Success -> {
                store.cachePlanSummaries(userId = userId, plans = result.value)
                ApiResult.Success(store.history(userId, scope, householdId))
            }
            is ApiResult.Failure -> result
        }
    }

    suspend fun createPlan(
        userId: String,
        request: PlanningPlanCreateRequest,
    ): PlanningMutationOutcome<PlanningPlan> {
        return when (val result = apiClient.createPlanningPlan(request)) {
            is ApiResult.Success -> {
                PlanningMutationOutcome.Applied(store.cachePlan(userId, result.value, replaceChildren = true))
            }
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                syncManager.enqueuePlanningPlanCreate(userId = userId, request = request)
                PlanningMutationOutcome.Queued("Сохранено на устройстве. План синхронизируется позже.")
            }
        }
    }

    suspend fun createIncomeSource(
        userId: String,
        plan: PlanningPlan,
        request: PlanningIncomeSourceCreateRequest,
    ): PlanningMutationOutcome<PlanningIncomeSource> {
        return when (val result = apiClient.createPlanningIncomeSource(plan.id, request)) {
            is ApiResult.Success -> PlanningMutationOutcome.Applied(store.cacheIncomeSource(userId, result.value))
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                syncManager.enqueuePlanningIncomeSourceCreate(userId = userId, planId = plan.id, request = request)
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Источник дохода синхронизируется позже.")
            }
        }
    }

    suspend fun updateIncomeSource(
        userId: String,
        source: PlanningIncomeSource,
        request: PlanningIncomeSourceUpdateRequest,
    ): PlanningMutationOutcome<PlanningIncomeSource> {
        return when (val result = apiClient.updatePlanningIncomeSource(source.id, request)) {
            is ApiResult.Success -> PlanningMutationOutcome.Applied(store.cacheIncomeSource(userId, result.value))
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                val version = source.version ?: return PlanningMutationOutcome.Failed(missingVersionFailure())
                syncManager.enqueuePlanningIncomeSourceUpdate(
                    userId = userId,
                    entityId = source.id,
                    baseVersion = version,
                    request = request,
                )
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Изменения источника синхронизируются позже.")
            }
        }
    }

    suspend fun confirmIncomeSource(
        userId: String,
        source: PlanningIncomeSource,
    ): PlanningMutationOutcome<PlanningIncomeSource> {
        return when (val result = apiClient.confirmPlanningIncomeSource(source.id)) {
            is ApiResult.Success -> PlanningMutationOutcome.Applied(store.cacheIncomeSource(userId, result.value))
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                val version = source.version ?: return PlanningMutationOutcome.Failed(missingVersionFailure())
                syncManager.enqueuePlanningIncomeSourceConfirm(userId = userId, entityId = source.id, baseVersion = version)
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Подтверждение дохода синхронизируется позже.")
            }
        }
    }

    suspend fun deleteIncomeSource(
        userId: String,
        source: PlanningIncomeSource,
    ): PlanningMutationOutcome<Unit> {
        return when (val result = apiClient.deletePlanningIncomeSource(source.id)) {
            is ApiResult.Success -> {
                store.markIncomeSourceDeleted(userId, source)
                PlanningMutationOutcome.Applied(Unit)
            }
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                val version = source.version ?: return PlanningMutationOutcome.Failed(missingVersionFailure())
                syncManager.enqueuePlanningIncomeSourceDelete(userId = userId, entityId = source.id, baseVersion = version)
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Удаление источника синхронизируется позже.")
            }
        }
    }

    suspend fun createAllocation(
        userId: String,
        plan: PlanningPlan,
        request: PlanningAllocationCreateRequest,
    ): PlanningMutationOutcome<PlanningAllocation> {
        return when (val result = apiClient.createPlanningAllocation(plan.id, request)) {
            is ApiResult.Success -> PlanningMutationOutcome.Applied(store.cacheAllocation(userId, result.value))
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                syncManager.enqueuePlanningAllocationCreate(userId = userId, planId = plan.id, request = request)
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Распределение синхронизируется позже.")
            }
        }
    }

    suspend fun updateAllocation(
        userId: String,
        allocation: PlanningAllocation,
        request: PlanningAllocationUpdateRequest,
    ): PlanningMutationOutcome<PlanningAllocation> {
        return when (val result = apiClient.updatePlanningAllocation(allocation.id, request)) {
            is ApiResult.Success -> PlanningMutationOutcome.Applied(store.cacheAllocation(userId, result.value))
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                val version = allocation.version ?: return PlanningMutationOutcome.Failed(missingVersionFailure())
                syncManager.enqueuePlanningAllocationUpdate(
                    userId = userId,
                    entityId = allocation.id,
                    baseVersion = version,
                    request = request,
                )
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Изменения распределения синхронизируются позже.")
            }
        }
    }

    suspend fun deleteAllocation(
        userId: String,
        allocation: PlanningAllocation,
    ): PlanningMutationOutcome<Unit> {
        return when (val result = apiClient.deletePlanningAllocation(allocation.id)) {
            is ApiResult.Success -> {
                store.markAllocationDeleted(userId, allocation)
                PlanningMutationOutcome.Applied(Unit)
            }
            is ApiResult.Failure -> {
                if (!result.isRetriableForPlanningQueue()) return PlanningMutationOutcome.Failed(result)
                val version = allocation.version ?: return PlanningMutationOutcome.Failed(missingVersionFailure())
                syncManager.enqueuePlanningAllocationDelete(userId = userId, entityId = allocation.id, baseVersion = version)
                PlanningMutationOutcome.Queued("Сохранено на устройстве. Удаление распределения синхронизируется позже.")
            }
        }
    }

    suspend fun copyPlan(
        userId: String,
        sourcePlanId: String,
        request: PlanningPlanCopyRequest,
    ): PlanningMutationOutcome<PlanningPlan> {
        return when (val result = apiClient.copyPlanningPlan(sourcePlanId, request)) {
            is ApiResult.Success -> {
                PlanningMutationOutcome.Applied(store.cachePlan(userId, result.value, replaceChildren = true))
            }
            is ApiResult.Failure -> {
                if (result.isRetriableForPlanningQueue()) {
                    PlanningMutationOutcome.Failed(
                        ApiResult.Failure(
                            message = "Копирование плана требует подключения к интернету.",
                            cause = result.cause,
                            statusCode = result.statusCode,
                            kind = result.kind,
                        ),
                    )
                } else {
                    PlanningMutationOutcome.Failed(result)
                }
            }
        }
    }

    private fun missingVersionFailure(): ApiResult.Failure {
        return ApiResult.Failure(
            message = "Нужна актуальная версия записи. Обновите план и повторите действие.",
            kind = ApiFailureKind.CONTRACT,
        )
    }
}

data class PlanningRepositoryState(
    val plan: PlanningPlan?,
    val history: List<PlanningPlan>,
    val pendingCount: Int,
)

sealed interface PlanningMutationOutcome<out T> {
    data class Applied<T>(val value: T) : PlanningMutationOutcome<T>
    data class Queued(val message: String) : PlanningMutationOutcome<Nothing>
    data class Failed(val failure: ApiResult.Failure) : PlanningMutationOutcome<Nothing>
}

private fun ApiResult.Failure.isRetriableForPlanningQueue(): Boolean {
    val code = statusCode
    return isNetworkFailure || code == 408 || code == 429 || (code != null && code >= 500)
}
