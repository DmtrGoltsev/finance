import SwiftUI

struct PlanningScopeCard: View {
    let month: String
    let currency: CurrencyCode
    let onMonthSelected: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "chart.bar")
                    .font(.system(size: 16))
                    .foregroundColor(FinanceColors.planningPrimary)
                    .frame(width: 36, height: 36)
                    .background(FinanceColors.planningPrimary.opacity(0.14))
                    .clipShape(Circle())
                VStack(alignment: .leading, spacing: 2) {
                    Text("План месяца")
                        .font(.headline)
                    Text("План на \(localizedPlanningMonth(month))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Text(currency.rawValue)
                    .font(.subheadline)
                    .fontWeight(.semibold)
            }

            Text("Месяц плана")
                .font(.caption)
                .fontWeight(.semibold)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(planningMonthChoices()) { choice in
                        Button {
                            onMonthSelected(choice.month)
                        } label: {
                            Text(choice.title)
                                .font(.caption)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(month == choice.month ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                                .foregroundColor(month == choice.month ? .white : .primary)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
