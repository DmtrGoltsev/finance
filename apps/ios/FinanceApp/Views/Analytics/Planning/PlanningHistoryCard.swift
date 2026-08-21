import SwiftUI

struct PlanningHistoryCard: View {
    let history: [PlanningPlan]
    let currentMonth: String
    let isLoading: Bool
    let onCopy: (PlanningPlan) async -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("История")
                .font(.headline)

            if history.isEmpty {
                Text("Истории планов пока нет")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                let otherPlans = history.filter { $0.month != currentMonth }
                if otherPlans.isEmpty {
                    Text("Истории планов пока нет")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                } else {
                    ForEach(Array(otherPlans.prefix(6))) { plan in
                        HStack(alignment: .center) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(localizedPlanningMonth(plan.month))
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                Text(plan.currency.rawValue)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Button("Копировать") {
                                Task { await onCopy(plan) }
                            }
                            .font(.caption)
                            .foregroundColor(FinanceColors.planningPrimary)
                            .disabled(isLoading)
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
