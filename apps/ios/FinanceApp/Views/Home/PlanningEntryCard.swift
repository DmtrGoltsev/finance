import SwiftUI

struct PlanningEntryCard: View {
    let onOpenPlanning: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            IconBubble(systemName: "chart.bar", color: FinanceColors.planningPrimary)
            VStack(alignment: .leading, spacing: 2) {
                Text("План месяца")
                    .font(.headline)
                Text("Доходы и распределения на месяц")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            Button("Открыть") {
                onOpenPlanning()
            }
            .buttonStyle(.bordered)
            .tint(FinanceColors.planningPrimary)
            .font(.caption)
        }
        .padding(16)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
    }
}
