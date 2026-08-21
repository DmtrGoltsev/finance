import SwiftUI

struct PlanningView: View {
    let dashboard: FinanceDashboard?
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let localScope: LocalStoreScope?
    let onLocalSnapshotChanged: () async -> Void

    @State private var month = nextPlanningMonth()
    @State private var plan: PlanningPlan?
    @State private var history: [PlanningPlan] = []
    @State private var isLoading = false
    @State private var message: String?

    private var boundedMonth: String { coercePlanningMonth(month) }
    private let planningScope: PlanningScope = .personal
    private var currency: CurrencyCode { planningCurrency(dashboard) }

    var body: some View {
        VStack(spacing: 12) {
            PlanningScopeCard(
                month: boundedMonth,
                currency: currency,
                onMonthSelected: { month = coercePlanningMonth($0) }
            )

            if let msg = message, !msg.isEmpty {
                PlanningMessageCard(text: msg)
            }

            PlanningPlanCard(
                plan: plan,
                month: boundedMonth,
                currency: currency,
                isLoading: isLoading,
                onRefresh: { await loadPlanningState() },
                onCreatePlan: { await createPlan() }
            )

            if let currentPlan = plan {
                IncomeSourcesCard(
                    plan: currentPlan,
                    currency: currency,
                    isLoading: isLoading,
                    onCreate: { request in await createIncomeSource(planId: currentPlan.id, request: request) },
                    onUpdate: { source, request in await updateIncomeSource(source: source, request: request) },
                    onConfirm: { source in await confirmIncomeSource(source: source) },
                    onDelete: { source in await deleteIncomeSource(source: source) }
                )

                AllocationsCard(
                    plan: currentPlan,
                    dashboard: dashboard,
                    isLoading: isLoading,
                    onCreate: { request in await createAllocation(planId: currentPlan.id, request: request) },
                    onUpdate: { allocation, request in await updateAllocation(allocation: allocation, request: request) },
                    onDelete: { allocation in await deleteAllocation(allocation: allocation) }
                )
            }

            PlanningHistoryCard(
                history: history,
                currentMonth: boundedMonth,
                isLoading: isLoading,
                onCopy: { historyPlan in await copyPlan(historyPlan) }
            )
        }
        .onChange(of: boundedMonth) { _, _ in Task { await loadPlanningState() } }
        .task { await loadPlanningState() }
    }

    private func loadPlanningState(successMessage: String? = nil) async {
        isLoading = true
        message = nil
        do {
            let fetched = try await apiClient.getPlanningPlan(scope: planningScope, month: boundedMonth, householdId: nil)
            if let fetched = fetched {
                plan = try await apiClient.getPlanningPlan(planId: fetched.id)
            } else {
                plan = nil
            }
            history = (try? await apiClient.listPlanningPlanHistory(scope: planningScope, householdId: nil)) ?? []
            message = successMessage
        } catch {
            if OfflineMutationFallback.canQueue(after: error) {
                await loadLocalPlanningState(fallbackMessage: "Нет соединения. Показаны локальные изменения, если они есть.")
            } else {
                message = planningErrorMessage(error)
                plan = nil
            }
        }
        isLoading = false
    }

    private func createPlan() async {
        let request = PlanningPlanCreateRequest(scope: planningScope, month: boundedMonth, currency: currency, householdId: nil)
        isLoading = true
        do {
            _ = try await apiClient.createPlanningPlan(request)
            await loadPlanningState(successMessage: "План создан")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let localPlan = localPlanningPlan(from: request)
                try await enqueuePlanning(
                    entityType: .planningPlans,
                    entityId: localPlan.id,
                    operation: .create,
                    request: request,
                    optimisticEntity: localPlan,
                    planId: localPlan.id,
                    baseVersion: nil
                )
                plan = localPlan
                await onLocalSnapshotChanged()
                message = "План создан локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func createIncomeSource(planId: String, request: PlanningIncomeSourceCreateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.createPlanningIncomeSource(planId: planId, request)
            await loadPlanningState(successMessage: "Источник дохода добавлен")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let source = localIncomeSource(planId: planId, from: request)
                try await enqueuePlanning(
                    entityType: .planningIncomeSources,
                    entityId: source.id,
                    operation: .create,
                    request: request,
                    optimisticEntity: source,
                    planId: planId,
                    baseVersion: nil
                )
                upsertIncomeSource(source)
                await onLocalSnapshotChanged()
                message = "Источник дохода добавлен локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func updateIncomeSource(source: PlanningIncomeSource, request: PlanningIncomeSourceUpdateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.updatePlanningIncomeSource(incomeSourceId: source.id, request)
            await loadPlanningState(successMessage: "Источник дохода обновлён")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let updated = updatedIncomeSource(source, request: request)
                try await enqueuePlanning(
                    entityType: .planningIncomeSources,
                    entityId: updated.id,
                    operation: .update,
                    request: PlanningIncomeSourceOfflineUpdateRequest(request),
                    optimisticEntity: updated,
                    planId: updated.planId,
                    baseVersion: source.version
                )
                upsertIncomeSource(updated)
                await onLocalSnapshotChanged()
                message = "Источник дохода обновлён локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func confirmIncomeSource(source: PlanningIncomeSource) async {
        isLoading = true
        do {
            _ = try await apiClient.confirmPlanningIncomeSource(incomeSourceId: source.id)
            await loadPlanningState(successMessage: "Доход подтверждён")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let confirmed = confirmedIncomeSource(source)
                try await enqueuePlanningAction(
                    entityType: .planningIncomeSources,
                    entityId: confirmed.id,
                    operation: .confirm,
                    optimisticEntity: confirmed,
                    planId: confirmed.planId,
                    baseVersion: source.version
                )
                upsertIncomeSource(confirmed)
                await onLocalSnapshotChanged()
                message = "Доход подтверждён локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func deleteIncomeSource(source: PlanningIncomeSource) async {
        isLoading = true
        do {
            try await apiClient.deletePlanningIncomeSource(incomeSourceId: source.id)
            await loadPlanningState(successMessage: "Источник дохода удалён")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                try await enqueuePlanningDelete(
                    entityType: .planningIncomeSources,
                    entityId: source.id,
                    optimisticEntity: source,
                    planId: source.planId,
                    baseVersion: source.version
                )
                removeIncomeSource(source.id)
                await onLocalSnapshotChanged()
                message = "Источник дохода удалён локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func createAllocation(planId: String, request: PlanningAllocationCreateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.createPlanningAllocation(planId: planId, request)
            await loadPlanningState(successMessage: "Распределение добавлено")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let allocation = localAllocation(planId: planId, from: request)
                try await enqueuePlanning(
                    entityType: .planningAllocations,
                    entityId: allocation.id,
                    operation: .create,
                    request: request,
                    optimisticEntity: allocation,
                    planId: planId,
                    baseVersion: nil
                )
                upsertAllocation(allocation)
                await onLocalSnapshotChanged()
                message = "Распределение добавлено локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func updateAllocation(allocation: PlanningAllocation, request: PlanningAllocationUpdateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.updatePlanningAllocation(allocationId: allocation.id, request)
            await loadPlanningState(successMessage: "Распределение обновлено")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let updated = updatedAllocation(allocation, request: request)
                try await enqueuePlanning(
                    entityType: .planningAllocations,
                    entityId: updated.id,
                    operation: .update,
                    request: PlanningAllocationOfflineUpdateRequest(request),
                    optimisticEntity: updated,
                    planId: updated.planId,
                    baseVersion: allocation.version
                )
                upsertAllocation(updated)
                await onLocalSnapshotChanged()
                message = "Распределение обновлено локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func deleteAllocation(allocation: PlanningAllocation) async {
        isLoading = true
        do {
            try await apiClient.deletePlanningAllocation(allocationId: allocation.id)
            await loadPlanningState(successMessage: "Распределение удалено")
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                try await enqueuePlanningDelete(
                    entityType: .planningAllocations,
                    entityId: allocation.id,
                    optimisticEntity: allocation,
                    planId: allocation.planId,
                    baseVersion: allocation.version
                )
                removeAllocation(allocation.id)
                await onLocalSnapshotChanged()
                message = "Распределение удалено локально, ожидает синхронизации"
            } catch {
                message = SyncSafeMessage.describe(error.localizedDescription)
            }
            isLoading = false
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func copyPlan(_ historyPlan: PlanningPlan) async {
        isLoading = true
        do {
            _ = try await apiClient.copyPlanningPlan(planId: historyPlan.id, PlanningPlanCopyRequest(targetMonth: boundedMonth))
            await loadPlanningState(successMessage: "План \(localizedPlanningMonth(historyPlan.month)) скопирован на \(localizedPlanningMonth(boundedMonth))")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func loadLocalPlanningState(fallbackMessage: String) async {
        guard let localScope else {
            message = fallbackMessage
            return
        }
        do {
            let snapshot = try await syncService.localSnapshot(scope: localScope)
            if let localPlan = localPlanningPlan(from: snapshot) {
                plan = localPlan
            }
            history = localPlanningHistory(from: snapshot)
            message = fallbackMessage
        } catch {
            message = SyncSafeMessage.describe(error.localizedDescription)
        }
    }

    private func enqueuePlanning<Request: Encodable, OptimisticEntity: Encodable>(
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        request: Request,
        optimisticEntity: OptimisticEntity,
        planId: String?,
        baseVersion: Int?
    ) async throws {
        guard let localScope else { throw LocalOptimisticError.missingLocalScope }
        try await syncService.enqueueOptimisticPlanningMutation(
            scope: localScope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            request: request,
            optimisticEntity: optimisticEntity,
            ownershipContext: planningOwnershipContext,
            planId: planId,
            month: plan?.month ?? boundedMonth,
            planningScope: .personal
        )
    }

    private func enqueuePlanningAction<OptimisticEntity: Encodable>(
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        optimisticEntity: OptimisticEntity,
        planId: String?,
        baseVersion: Int?
    ) async throws {
        guard let localScope else { throw LocalOptimisticError.missingLocalScope }
        try await syncService.enqueueOptimisticPlanningMutation(
            scope: localScope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            optimisticEntity: optimisticEntity,
            ownershipContext: planningOwnershipContext,
            planId: planId,
            month: plan?.month ?? boundedMonth,
            planningScope: .personal
        )
    }

    private func enqueuePlanningDelete<OptimisticEntity: Encodable>(
        entityType: SyncEntityType,
        entityId: String,
        optimisticEntity: OptimisticEntity,
        planId: String?,
        baseVersion: Int?
    ) async throws {
        try await enqueuePlanningAction(
            entityType: entityType,
            entityId: entityId,
            operation: .delete,
            optimisticEntity: optimisticEntity,
            planId: planId,
            baseVersion: baseVersion
        )
    }

    private var planningOwnershipContext: PersonalOwnershipContext {
        PersonalOwnershipContext(
            viewerUserId: localScope?.viewerUserId,
            accounts: dashboard?.accounts ?? [],
            categories: dashboard?.categories ?? [],
            assetCategories: dashboard?.assetCategories ?? [],
            plans: plan.map { [$0] } ?? []
        )
    }

    private func localPlanningPlan(from request: PlanningPlanCreateRequest) -> PlanningPlan {
        PlanningPlan(
            id: UUID().uuidString,
            scope: request.scope,
            ownerUserId: localScope?.viewerUserId,
            month: request.month,
            currency: request.currency,
            householdId: nil,
            summary: planningSummary(incomeSources: [], allocations: [], previousMonthSurplus: "0"),
            incomeSources: [],
            allocations: [],
            version: nil
        )
    }

    private func localIncomeSource(planId: String, from request: PlanningIncomeSourceCreateRequest) -> PlanningIncomeSource {
        PlanningIncomeSource(
            id: UUID().uuidString,
            planId: planId,
            amount: request.amount,
            source: request.source,
            description: request.description,
            dayOfMonth: request.dayOfMonth,
            effectiveDate: planningEffectiveDate(month: plan?.month ?? boundedMonth, day: request.dayOfMonth),
            confirmationState: .planned,
            confirmedAt: nil,
            version: nil
        )
    }

    private func updatedIncomeSource(_ source: PlanningIncomeSource, request: PlanningIncomeSourceUpdateRequest) -> PlanningIncomeSource {
        PlanningIncomeSource(
            id: source.id,
            planId: source.planId,
            amount: request.amount ?? source.amount,
            source: request.source ?? source.source,
            description: request.description ?? source.description,
            dayOfMonth: request.dayOfMonth ?? source.dayOfMonth,
            effectiveDate: planningEffectiveDate(
                month: plan?.month ?? boundedMonth,
                day: request.dayOfMonth ?? source.dayOfMonth
            ),
            confirmationState: source.confirmationState,
            confirmedAt: source.confirmedAt,
            version: source.version
        )
    }

    private func confirmedIncomeSource(_ source: PlanningIncomeSource) -> PlanningIncomeSource {
        PlanningIncomeSource(
            id: source.id,
            planId: source.planId,
            amount: source.amount,
            source: source.source,
            description: source.description,
            dayOfMonth: source.dayOfMonth,
            effectiveDate: source.effectiveDate,
            confirmationState: .confirmed,
            confirmedAt: Date().ISO8601Format(),
            version: source.version
        )
    }

    private func localAllocation(planId: String, from request: PlanningAllocationCreateRequest) -> PlanningAllocation {
        PlanningAllocation(
            id: UUID().uuidString,
            planId: planId,
            targetType: request.targetType,
            targetId: request.targetId,
            targetSnapshot: targetSnapshot(type: request.targetType, id: request.targetId),
            requiresAttention: false,
            attentionReason: nil,
            comment: request.comment,
            allocationMode: request.allocationMode,
            allocationValue: request.allocationValue,
            recurrenceType: request.recurrenceType,
            isSavingsGoal: request.isSavingsGoal ?? false,
            goalTargetAmount: request.goalTargetAmount,
            goalDueMonth: request.goalDueMonth,
            goalMonthlyAmount: nil,
            calculatedAmount: request.allocationMode == .amount ? request.allocationValue : "0",
            actualAmount: nil,
            varianceAmount: nil,
            progressPercent: nil,
            progressStatus: nil,
            status: "planned",
            version: nil
        )
    }

    private func updatedAllocation(_ allocation: PlanningAllocation, request: PlanningAllocationUpdateRequest) -> PlanningAllocation {
        let targetType = request.targetType ?? allocation.targetType
        let targetId = request.targetId ?? allocation.targetId
        let allocationMode = request.allocationMode ?? allocation.allocationMode
        let allocationValue = request.allocationValue ?? allocation.allocationValue
        return PlanningAllocation(
            id: allocation.id,
            planId: allocation.planId,
            targetType: targetType,
            targetId: targetId,
            targetSnapshot: targetId.flatMap { targetSnapshot(type: targetType, id: $0) } ?? allocation.targetSnapshot,
            requiresAttention: allocation.requiresAttention,
            attentionReason: allocation.attentionReason,
            comment: request.comment,
            allocationMode: allocationMode,
            allocationValue: allocationValue,
            recurrenceType: request.recurrenceType ?? allocation.recurrenceType,
            isSavingsGoal: request.isSavingsGoal ?? allocation.isSavingsGoal,
            goalTargetAmount: request.goalTargetAmount ?? allocation.goalTargetAmount,
            goalDueMonth: request.goalDueMonth ?? allocation.goalDueMonth,
            goalMonthlyAmount: allocation.goalMonthlyAmount,
            calculatedAmount: allocationMode == .amount ? allocationValue : allocation.calculatedAmount,
            actualAmount: allocation.actualAmount,
            varianceAmount: allocation.varianceAmount,
            progressPercent: allocation.progressPercent,
            progressStatus: allocation.progressStatus,
            status: allocation.status,
            version: allocation.version
        )
    }

    private func upsertIncomeSource(_ source: PlanningIncomeSource) {
        guard let current = plan else { return }
        var sources = current.incomeSources
        if let index = sources.firstIndex(where: { $0.id == source.id }) {
            sources[index] = source
        } else {
            sources.append(source)
        }
        plan = planningPlan(current, incomeSources: sources, allocations: current.allocations)
    }

    private func removeIncomeSource(_ id: String) {
        guard let current = plan else { return }
        plan = planningPlan(current, incomeSources: current.incomeSources.filter { $0.id != id }, allocations: current.allocations)
    }

    private func upsertAllocation(_ allocation: PlanningAllocation) {
        guard let current = plan else { return }
        var allocations = current.allocations
        if let index = allocations.firstIndex(where: { $0.id == allocation.id }) {
            allocations[index] = allocation
        } else {
            allocations.append(allocation)
        }
        plan = planningPlan(current, incomeSources: current.incomeSources, allocations: allocations)
    }

    private func removeAllocation(_ id: String) {
        guard let current = plan else { return }
        plan = planningPlan(current, incomeSources: current.incomeSources, allocations: current.allocations.filter { $0.id != id })
    }

    private func localPlanningPlan(from snapshot: FinanceLocalSnapshot) -> PlanningPlan? {
        let tombstonedPlans = tombstonedIds(in: snapshot, entityType: .planningPlans)
        let localPlan = snapshot.planningPlans
            .map(\.entity)
            .first { $0.scope == planningScope && $0.month == boundedMonth && !tombstonedPlans.contains($0.id) }
        guard let base = localPlan ?? plan else { return nil }
        guard base.scope == planningScope && base.month == boundedMonth else { return nil }
        let incomeTombstones = tombstonedIds(in: snapshot, entityType: .planningIncomeSources)
        let allocationTombstones = tombstonedIds(in: snapshot, entityType: .planningAllocations)
        var incomeSources = base.incomeSources.filter { !incomeTombstones.contains($0.id) }
        var allocations = base.allocations.filter { !allocationTombstones.contains($0.id) }
        for record in snapshot.planningIncomeSources where record.entity.planId == base.id && !incomeTombstones.contains(record.entity.id) {
            upsert(record.entity, in: &incomeSources)
        }
        for record in snapshot.planningAllocations where record.entity.planId == base.id && !allocationTombstones.contains(record.entity.id) {
            upsert(record.entity, in: &allocations)
        }
        return planningPlan(base, incomeSources: incomeSources, allocations: allocations)
    }

    private func localPlanningHistory(from snapshot: FinanceLocalSnapshot) -> [PlanningPlan] {
        let tombstonedPlans = tombstonedIds(in: snapshot, entityType: .planningPlans)
        let localPlans = snapshot.planningPlans
            .map(\.entity)
            .filter { $0.scope == planningScope && $0.month != boundedMonth && !tombstonedPlans.contains($0.id) }
        var merged = history
        for plan in localPlans {
            upsert(plan, in: &merged)
        }
        return merged.sorted { $0.month > $1.month }
    }

    private func tombstonedIds(in snapshot: FinanceLocalSnapshot, entityType: SyncEntityType) -> Set<String> {
        Set(snapshot.tombstones.filter { $0.entityType == entityType }.map(\.entityId))
    }

    private func upsert<Entity: Identifiable>(_ entity: Entity, in list: inout [Entity]) where Entity.ID == String {
        if let index = list.firstIndex(where: { $0.id == entity.id }) {
            list[index] = entity
        } else {
            list.append(entity)
        }
    }

    private func planningPlan(
        _ current: PlanningPlan,
        incomeSources: [PlanningIncomeSource],
        allocations: [PlanningAllocation]
    ) -> PlanningPlan {
        PlanningPlan(
            id: current.id,
            scope: current.scope,
            ownerUserId: current.ownerUserId,
            month: current.month,
            currency: current.currency,
            householdId: nil,
            summary: planningSummary(
                incomeSources: incomeSources,
                allocations: allocations,
                previousMonthSurplus: current.summary.previousMonthSurplus
            ),
            incomeSources: incomeSources,
            allocations: allocations,
            version: current.version
        )
    }

    private func planningSummary(
        incomeSources: [PlanningIncomeSource],
        allocations: [PlanningAllocation],
        previousMonthSurplus: String
    ) -> PlanningSummary {
        let totalIncome = incomeSources.reduce(Decimal.zero) { $0 + (Decimal(string: $1.amount) ?? .zero) }
        let confirmedIncome = incomeSources
            .filter { $0.confirmationState == .confirmed }
            .reduce(Decimal.zero) { $0 + (Decimal(string: $1.amount) ?? .zero) }
        let totalAllocated = allocations.reduce(Decimal.zero) { total, allocation in
            if allocation.allocationMode == .percent, let percent = Decimal(string: allocation.allocationValue) {
                return total + totalIncome * percent / Decimal(100)
            }
            return total + (Decimal(string: allocation.calculatedAmount) ?? Decimal(string: allocation.allocationValue) ?? .zero)
        }
        let unallocated = totalIncome - totalAllocated
        return PlanningSummary(
            totalPlannedIncome: MoneyHelpers.decimalToString(totalIncome),
            totalConfirmedIncome: MoneyHelpers.decimalToString(confirmedIncome),
            totalAllocatedAmount: MoneyHelpers.decimalToString(totalAllocated),
            unallocatedAmount: MoneyHelpers.decimalToString(unallocated),
            previousMonthSurplus: previousMonthSurplus,
            underallocated: unallocated > .zero,
            overallocated: unallocated < .zero
        )
    }

    private func targetSnapshot(type: AllocationTargetType, id: String) -> [String: JSONValue]? {
        switch type {
        case .expense_category:
            return (dashboard?.categories.first { $0.id == id }).map { ["name": .string($0.name)] }
        case .investment_asset_category:
            return (dashboard?.assetCategories.first { $0.id == id }).map { ["name": .string($0.name)] }
        case .account:
            return (dashboard?.accounts.first { $0.id == id }).map { ["name": .string($0.name)] }
        case .asset:
            return nil
        }
    }
}

private func planningCurrency(_ dashboard: FinanceDashboard?) -> CurrencyCode {
    let accounts = dashboard?.personalAccounts ?? []
    return accounts.first?.currency
        ?? dashboard?.totals.first?.currency
        ?? .RUB
}

func nextPlanningMonth() -> String {
    let cal = Calendar.current
    let now = Date()
    guard let next = cal.date(byAdding: .month, value: 1, to: now) else { return DateHelpers.currentYearMonth() }
    let y = cal.component(.year, from: next)
    let m = cal.component(.month, from: next)
    return String(format: "%04d-%02d", y, m)
}

private func coercePlanningMonth(_ ym: String) -> String {
    let current = DateHelpers.currentYearMonth()
    let parts = ym.split(separator: "-")
    guard parts.count == 2,
          let year = Int(parts[0]),
          let month = Int(parts[1]) else { return current }
    let parsed = String(format: "%04d-%02d", year, month)
    return parsed >= current ? parsed : current
}

func localizedPlanningMonth(_ ym: String) -> String {
    DateHelpers.displayMonth(ym)
}

private func planningEffectiveDate(month: String, day: Int) -> String? {
    let parts = month.split(separator: "-")
    guard parts.count == 2,
          let year = Int(parts[0]),
          let monthNumber = Int(parts[1]),
          let firstDay = Calendar.current.date(from: DateComponents(year: year, month: monthNumber, day: 1)),
          let dayRange = Calendar.current.range(of: .day, in: .month, for: firstDay) else {
        return nil
    }
    return String(format: "%04d-%02d-%02d", year, monthNumber, min(max(day, 1), dayRange.count))
}

func localizedTargetType(_ type: AllocationTargetType) -> String {
    switch type {
    case .expense_category: return "Расходы"
    case .investment_asset_category: return "Инвестиции"
    case .account: return "Счёт"
    case .asset: return "Актив"
    }
}

func localizedAllocationMode(_ mode: AllocationMode) -> String {
    switch mode {
    case .amount: return "Сумма"
    case .percent: return "Процент"
    }
}

func localizedRecurrenceType(_ type: AllocationRecurrenceType) -> String {
    switch type {
    case .regular: return "Регулярная"
    case .one_off: return "Разовая"
    }
}

func localizedPlanningStatus(_ status: String?) -> String {
    switch status {
    case "active", "planned", "on_track": return "по плану"
    case "confirmed", "completed", "done": return "выполнено"
    case "needs_attention", "target_attention", "warning", "attention": return "требует внимания"
    case "no_actuals": return "Факт"
    case "not_applicable": return "не применяется"
    case "under_plan", "underplanned", "behind": return "ниже плана"
    case "over_plan", "overplanned", "ahead": return "выше плана"
    default: return "ожидает данных"
    }
}

private func planningErrorMessage(_ error: Error) -> String {
    let msg = error.localizedDescription
    if msg.contains("401") { return "Сессия истекла. Войдите снова." }
    if msg.contains("403") { return "Нет доступа к планированию." }
    if msg.contains("404") { return "План для выбранного месяца ещё не создан" }
    return msg
}

struct PlanningMessageCard: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.subheadline)
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(UIColor.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct PlanningBanner: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption)
            .fontWeight(.medium)
            .foregroundColor(color)
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(color.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

func planningMonthChoices() -> [PlanningMonthChoice] {
    let current = DateHelpers.currentYearMonth()
    let cal = Calendar.current
    let now = Date()
    let currentY = cal.component(.year, from: now)
    let currentM = cal.component(.month, from: now)

    return (0...12).compactMap { offset -> PlanningMonthChoice? in
        var comps = DateComponents()
        comps.year = currentY
        comps.month = currentM + offset
        comps.day = 1
        guard let date = cal.date(from: comps) else { return nil }
        let y = cal.component(.year, from: date)
        let m = cal.component(.month, from: date)
        let ym = String(format: "%04d-%02d", y, m)
        let title: String
        switch offset {
        case 0: title = "Текущий: \(DateHelpers.displayMonth(ym))"
        case 1: title = "Следующий: \(DateHelpers.displayMonth(ym))"
        default: title = DateHelpers.displayMonth(ym)
        }
        return PlanningMonthChoice(month: ym, title: title)
    }
}

func planningGoalMonthChoices() -> [PlanningMonthChoice] {
    let cal = Calendar.current
    let now = Date()
    let currentY = cal.component(.year, from: now)
    let currentM = cal.component(.month, from: now)

    return (1...36).compactMap { offset -> PlanningMonthChoice? in
        var comps = DateComponents()
        comps.year = currentY
        comps.month = currentM + offset
        comps.day = 1
        guard let date = cal.date(from: comps) else { return nil }
        let y = cal.component(.year, from: date)
        let m = cal.component(.month, from: date)
        let ym = String(format: "%04d-%02d", y, m)
        let prefix: String? = {
            switch offset {
            case 1: return "Следующий"
            case 6: return "6 мес."
            case 12: return "1 год"
            case 24: return "2 года"
            case 36: return "3 года"
            default: return nil
            }
        }()
        let title = prefix.map { "\($0): \(DateHelpers.displayMonth(ym))" } ?? DateHelpers.displayMonth(ym)
        return PlanningMonthChoice(month: ym, title: title)
    }
}

struct PlanningMonthChoice: Identifiable {
    let month: String
    let title: String
    var id: String { month }
}

func normalizePlanningAmount(_ string: String) -> String? {
    let normalized = string.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
    guard !normalized.isEmpty else { return nil }
    guard let value = Decimal(string: normalized), value > .zero else { return nil }
    let ns = value as NSDecimalNumber
    let rounded = ns.rounding(accordingToBehavior: NSDecimalNumberHandler(roundingMode: .plain, scale: 2, raiseOnExactness: false, raiseOnOverflow: false, raiseOnUnderflow: false, raiseOnDivideByZero: false))
    return rounded.stringValue
}

func planningDecimalInput(_ string: String) -> String {
    string.filter { $0.isNumber || $0 == "." || $0 == "," }.replacingOccurrences(of: ",", with: ".")
}

func toPlanningDay(_ string: String) -> Int? {
    guard let day = Int(string), (1...31).contains(day) else { return nil }
    return day
}

func snapshotTitle(_ snapshot: [String: JSONValue]?) -> String? {
    guard let snapshot = snapshot, !snapshot.isEmpty else { return nil }
    for key in ["name", "title", "displayName", "label"] {
        if let val = snapshot[key]?.stringValue, !val.isEmpty {
            return val
        }
    }
    return nil
}
