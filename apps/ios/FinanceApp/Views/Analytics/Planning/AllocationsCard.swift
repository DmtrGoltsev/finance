import SwiftUI

struct AllocationsCard: View {
    let plan: PlanningPlan
    let dashboard: FinanceDashboard?
    let pendingOverlay: FinanceDashboard.MonthlyPendingOverlay
    let isLoading: Bool
    let onCreate: (PlanningAllocationCreateRequest) async -> Void
    let onUpdate: (PlanningAllocation, PlanningAllocationUpdateRequest) async -> Void
    let onDelete: (PlanningAllocation) async -> Void

    @State private var draft = PlanningAllocationDraft()

    private var categories: [Category] {
        (dashboard?.categories ?? [])
            .filter { $0.status == .active && $0.type == .expense && $0.scope == .personal }
    }

    private var investments: [AssetCategory] {
        (dashboard?.assetCategories ?? [])
            .filter { $0.recordStatus == .active && $0.isInvestment && $0.scopeType == .personal }
    }

    private var usedTargetIds: Set<String> {
        Set(plan.allocations.compactMap { $0.targetId })
    }

    private var targetOptions: [PlanningTargetOption] {
        let all = draft.targetType == .expense_category
            ? categories.map { PlanningTargetOption(id: $0.id, title: $0.name) }
            : investments.map { PlanningTargetOption(id: $0.id, title: $0.name) }
        return all.filter { !usedTargetIds.contains($0.id) }
    }

    private var canCreate: Bool {
        !isLoading &&
        !draft.targetId.isEmpty &&
        normalizePlanningAmount(draft.allocationValue) != nil &&
        draft.hasValidSavingsGoalState
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Распределения")
                .font(.headline)

            PlanningAllocationEditor(
                draft: $draft,
                currency: plan.currency,
                targetOptions: targetOptions,
                usedTargetIds: usedTargetIds
            )

            Button {
                guard let request = draft.toCreateRequest() else { return }
                Task { await onCreate(request) }
                draft = PlanningAllocationDraft()
            } label: {
                Text("Добавить распределение")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(FinanceColors.planningPrimary)
            .disabled(!canCreate)

            if !canCreate {
                Text("Чтобы добавить распределение, выберите цель и укажите сумму или процент.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if plan.allocations.isEmpty {
                Text("В плане пока нет распределений. Добавьте расходную или инвестиционную цель.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                ForEach(plan.allocations) { allocation in
                    let displayedAllocation = applyingPendingActual(to: allocation)
                    PlanningAllocationRow(
                        allocation: displayedAllocation,
                        currency: plan.currency,
                        categories: categories,
                        investments: investments,
                        isLoading: isLoading,
                        onUpdate: { _, request in await onUpdate(allocation, request) },
                        onDelete: { _ in await onDelete(allocation) }
                    )
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func applyingPendingActual(to allocation: PlanningAllocation) -> PlanningAllocation {
        guard let targetId = allocation.targetId else { return allocation }
        let delta: Decimal
        switch allocation.targetType {
        case .expense_category:
            delta = pendingOverlay.expensesByCategory[targetId, default: .zero]
        case .investment_asset_category:
            delta = pendingOverlay.investmentsByAssetCategory[targetId, default: .zero]
        default:
            delta = .zero
        }
        guard delta != .zero else { return allocation }
        let actual = (Decimal(string: allocation.actualAmount ?? "0") ?? .zero) + delta
        let planned = Decimal(string: allocation.calculatedAmount) ?? .zero
        let variance = actual - planned
        let requiresAttention: Bool
        switch allocation.targetType {
        case .expense_category:
            requiresAttention = actual > planned
        case .investment_asset_category:
            requiresAttention = actual < planned
        default:
            requiresAttention = allocation.requiresAttention
        }
        let progressPercent = planned > .zero
            ? MoneyHelpers.decimalToString(actual / planned * 100)
            : allocation.progressPercent
        return PlanningAllocation(
            id: allocation.id,
            planId: allocation.planId,
            targetType: allocation.targetType,
            targetId: allocation.targetId,
            targetSnapshot: allocation.targetSnapshot,
            requiresAttention: requiresAttention,
            attentionReason: allocation.attentionReason,
            comment: allocation.comment,
            allocationMode: allocation.allocationMode,
            allocationValue: allocation.allocationValue,
            recurrenceType: allocation.recurrenceType,
            isSavingsGoal: allocation.isSavingsGoal,
            goalTargetAmount: allocation.goalTargetAmount,
            goalDueMonth: allocation.goalDueMonth,
            goalMonthlyAmount: allocation.goalMonthlyAmount,
            calculatedAmount: allocation.calculatedAmount,
            actualAmount: MoneyHelpers.decimalToString(actual),
            varianceAmount: MoneyHelpers.decimalToString(variance),
            progressPercent: progressPercent,
            progressStatus: requiresAttention ? .needs_attention : .on_track,
            status: allocation.status,
            version: allocation.version
        )
    }
}
struct PlanningTargetOption: Identifiable {
    let id: String
    let title: String
}

struct PlanningAllocationDraft {
    var targetType: AllocationTargetType = .expense_category
    var targetId: String = ""
    var allocationMode: AllocationMode = .amount
    var allocationValue: String = ""
    var recurrenceType: AllocationRecurrenceType = .regular
    var isSavingsGoal: Bool = false
    var goalTargetAmount: String = ""
    var goalDueMonth: String = nextPlanningMonth()
    var comment: String = ""

    var hasValidSavingsGoalState: Bool {
        if !isSavingsGoal { return true }
        if targetType != .investment_asset_category { return false }
        return normalizePlanningAmount(goalTargetAmount) != nil
    }

    func toCreateRequest() -> PlanningAllocationCreateRequest? {
        guard let value = normalizePlanningAmount(allocationValue) else { return nil }
        let savingsEnabled = isSavingsGoal && targetType == .investment_asset_category
        return PlanningAllocationCreateRequest(
            targetType: targetType,
            targetId: targetId.trimmingCharacters(in: .whitespaces),
            comment: comment.trimmingCharacters(in: .whitespaces).isEmpty ? nil : comment.trimmingCharacters(in: .whitespaces),
            allocationMode: allocationMode,
            allocationValue: value,
            recurrenceType: recurrenceType,
            isSavingsGoal: savingsEnabled,
            goalTargetAmount: savingsEnabled ? normalizePlanningAmount(goalTargetAmount) : nil,
            goalDueMonth: savingsEnabled ? goalDueMonth : nil
        )
    }

    func toUpdateRequest(version: Int?) -> PlanningAllocationUpdateRequest? {
        guard let value = normalizePlanningAmount(allocationValue) else { return nil }
        let savingsEnabled = isSavingsGoal && targetType == .investment_asset_category
        return PlanningAllocationUpdateRequest(
            targetType: targetType,
            targetId: targetId.isEmpty ? nil : targetId.trimmingCharacters(in: .whitespaces),
            comment: comment.trimmingCharacters(in: .whitespaces).isEmpty ? nil : comment.trimmingCharacters(in: .whitespaces),
            allocationMode: allocationMode,
            allocationValue: value,
            recurrenceType: recurrenceType,
            isSavingsGoal: savingsEnabled,
            goalTargetAmount: savingsEnabled ? normalizePlanningAmount(goalTargetAmount) : nil,
            goalDueMonth: savingsEnabled ? goalDueMonth : nil,
            version: version
        )
    }
}
