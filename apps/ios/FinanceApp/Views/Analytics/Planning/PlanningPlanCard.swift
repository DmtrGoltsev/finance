import SwiftUI

struct PlanningPlanCard: View {
    let plan: PlanningPlan?
    let month: String
    let currency: CurrencyCode
    let isLoading: Bool
    let onRefresh: () async -> Void
    let onCreatePlan: () async -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Текущий план")
                        .font(.headline)
                    if let plan = plan {
                        Text("\(localizedPlanningMonth(plan.month)) • \(plan.currency.rawValue)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("План на \(localizedPlanningMonth(month)) ещё не создан")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                Button {
                    Task { await onRefresh() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(FinanceColors.planningPrimary)
                }
                .disabled(isLoading)
            }

            if plan == nil {
                Button {
                    Task { await onCreatePlan() }
                } label: {
                    Text("Создать план на \(localizedPlanningMonth(month))")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(FinanceColors.planningPrimary)
                .disabled(isLoading)
            } else {
                let summary = plan!.summary
                HStack(spacing: 8) {
                    PlanningMetricTile(
                        label: "Доход",
                        value: MoneyHelpers.format(summary.totalPlannedIncome, currency: currency)
                    )
                    PlanningMetricTile(
                        label: "Распределено",
                        value: MoneyHelpers.format(summary.totalAllocatedAmount, currency: currency)
                    )
                }

                let surplus = Decimal(string: summary.previousMonthSurplus) ?? .zero
                if surplus > .zero {
                    PlanningBanner(
                        text: "Предложение к учёту из прошлого месяца: \(MoneyHelpers.format(summary.previousMonthSurplus, currency: currency)). Это подсказка, не перенос денег.",
                        color: FinanceColors.warning
                    )
                }

                HStack(spacing: 8) {
                    PlanningMetricTile(
                        label: "Осталось",
                        value: MoneyHelpers.format(summary.unallocatedAmount, currency: currency)
                    )
                    let overallocated = Decimal(string: summary.totalPlannedIncome) ?? .zero
                    let allocated = Decimal(string: summary.totalAllocatedAmount) ?? .zero
                    let over = allocated - overallocated
                    PlanningMetricTile(
                        label: "Сверх",
                        value: over > .zero ? MoneyHelpers.format(MoneyHelpers.decimalToString(over), currency: currency) : "0 \(MoneyHelpers.currencySymbol(currency))"
                    )
                }

                if summary.underallocated {
                    PlanningBanner(
                        text: "Есть доход без распределений. Добавьте распределение или уменьшите плановый доход.",
                        color: FinanceColors.warning
                    )
                }
                if summary.overallocated {
                    PlanningBanner(
                        text: "Распределения выше планового дохода. Исправьте распределения, чтобы снять предупреждение.",
                        color: FinanceColors.expense
                    )
                }

                let highlights = buildHighlights(plan!)
                if highlights.isEmpty {
                    PlanningBanner(
                        text: "Статусы появятся в строках распределений после расчёта плана.",
                        color: FinanceColors.analyticsAccent
                    )
                }
                ForEach(Array(highlights.prefix(3)), id: \.self) { highlight in
                    let color = highlight.hasPrefix("Расходы") ? FinanceColors.expense : FinanceColors.warning
                    PlanningBanner(text: highlight, color: color)
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func buildHighlights(_ plan: PlanningPlan) -> [String] {
        plan.allocations.compactMap { allocation in
            if allocation.targetType == .investment_asset_category &&
                (allocation.progressStatus?.rawValue == "under_plan" || allocation.requiresAttention) {
                let name = snapshotTitle(allocation.targetSnapshot) ?? localizedTargetType(allocation.targetType)
                return "Инвестиции ниже плана: \(name)"
            }
            if allocation.targetType == .expense_category &&
                (allocation.progressStatus?.rawValue == "over_plan" || allocation.requiresAttention) {
                let name = snapshotTitle(allocation.targetSnapshot) ?? localizedTargetType(allocation.targetType)
                return "Расходы выше плана: \(name)"
            }
            if let status = allocation.progressStatus?.rawValue, !status.isEmpty {
                return "\(localizedTargetType(allocation.targetType)): \(localizedPlanningStatus(status))"
            }
            return nil
        }
    }
}

struct PlanningMetricTile: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Color(UIColor.tertiarySystemBackground).opacity(0.45))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
