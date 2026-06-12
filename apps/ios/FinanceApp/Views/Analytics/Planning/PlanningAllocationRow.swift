import SwiftUI

struct PlanningAllocationRow: View {
    let allocation: PlanningAllocation
    let currency: CurrencyCode
    let categories: [Category]
    let investments: [AssetCategory]
    let isLoading: Bool
    let onUpdate: (PlanningAllocation, PlanningAllocationUpdateRequest) async -> Void
    let onDelete: (PlanningAllocation) async -> Void

    @State private var isEditing = false
    @State private var draft = PlanningAllocationDraft()

    private var targetName: String {
        let options = allocation.targetType == .expense_category
            ? categories.map { PlanningTargetOption(id: $0.id, title: $0.name) }
            : investments.map { PlanningTargetOption(id: $0.id, title: $0.name) }
        if let found = options.first(where: { $0.id == allocation.targetId }) {
            return found.title
        }
        if let name = snapshotTitle(allocation.targetSnapshot) {
            return name
        }
        return localizedTargetType(allocation.targetType)
    }

    private var statusText: String {
        if let progress = allocation.progressStatus?.rawValue, !progress.isEmpty {
            return localizedPlanningStatus(progress)
        }
        if allocation.targetType == .investment_asset_category && allocation.requiresAttention {
            return "Инвестиции ниже плана"
        }
        if allocation.targetType == .expense_category && allocation.requiresAttention {
            return "Расходы выше плана"
        }
        if allocation.requiresAttention { return "Нужно внимание" }
        return "Статус allocation ожидает факта"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(targetName)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(1)

                    Text(allocationSubtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    if let actual = allocation.actualAmount, !actual.isEmpty {
                        let percentSuffix = allocation.progressPercent.map { " • \($0)%" } ?? ""
                        Text("Факт: \(MoneyHelpers.format(actual, currency: currency))\(percentSuffix)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("Факт появится после операций в этой категории")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    if allocation.isSavingsGoal {
                        let goalText = allocation.goalTargetAmount.map { MoneyHelpers.format($0, currency: currency) } ?? "не задана"
                        let dueText = allocation.goalDueMonth.map { localizedPlanningMonth($0) } ?? "срок не задан"
                        let monthlyText = allocation.goalMonthlyAmount.map { MoneyHelpers.format($0, currency: currency) } ?? "ожидает расчёта"
                        Text("Цель накопления: \(goalText) к \(dueText) • в месяц \(monthlyText)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    if let comment = allocation.comment, !comment.isEmpty {
                        Text(comment)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                Button(isEditing ? "Закрыть" : "Править") {
                    if !isEditing {
                        draft = PlanningAllocationDraft(
                            targetType: allocation.targetType,
                            targetId: allocation.targetId ?? "",
                            allocationMode: allocation.allocationMode,
                            allocationValue: allocation.allocationValue,
                            recurrenceType: allocation.recurrenceType ?? .regular,
                            isSavingsGoal: allocation.isSavingsGoal && allocation.targetType == .investment_asset_category,
                            goalTargetAmount: allocation.goalTargetAmount ?? "",
                            goalDueMonth: allocation.goalDueMonth ?? nextPlanningMonth(),
                            comment: allocation.comment ?? ""
                        )
                    }
                    isEditing.toggle()
                }
                .font(.caption)
                .foregroundColor(FinanceColors.planningPrimary)
            }

            if allocation.requiresAttention {
                PlanningBanner(
                    text: allocation.attentionReason ?? "Эта цель требует внимания",
                    color: FinanceColors.warning
                )
            }

            if isEditing {
                let editOptions = draft.targetType == .expense_category
                    ? categories.map { PlanningTargetOption(id: $0.id, title: $0.name) }
                    : investments.map { PlanningTargetOption(id: $0.id, title: $0.name) }

                PlanningAllocationEditor(
                    draft: $draft,
                    currency: currency,
                    targetOptions: editOptions,
                    usedTargetIds: []
                )

                HStack(spacing: 8) {
                    Button("Удалить", role: .destructive) {
                        Task { await onDelete(allocation) }
                    }
                    .buttonStyle(.bordered)
                    .disabled(isLoading)
                    .frame(maxWidth: .infinity)

                    Button("Сохранить") {
                        guard let request = draft.toUpdateRequest(version: allocation.version) else { return }
                        Task { await onUpdate(allocation, request) }
                        isEditing = false
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FinanceColors.planningPrimary)
                    .disabled(isLoading || normalizePlanningAmount(draft.allocationValue) == nil || !draft.hasValidSavingsGoalState)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(10)
        .background(Color(UIColor.tertiarySystemBackground).opacity(0.35))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var allocationSubtitle: String {
        let typeLabel = localizedTargetType(allocation.targetType)
        let recurrenceLabel = localizedRecurrenceType(allocation.recurrenceType ?? .regular)
        let valuePart: String
        if allocation.allocationMode == .percent {
            valuePart = "\(localizedAllocationMode(.percent)): \(allocation.allocationValue)% = \(MoneyHelpers.format(allocation.calculatedAmount, currency: currency))"
        } else {
            valuePart = MoneyHelpers.format(allocation.calculatedAmount, currency: currency)
        }
        return "\(typeLabel) • \(recurrenceLabel) • \(valuePart) • \(statusText)"
    }
}
