import SwiftUI

struct PlanningScopeCard: View {
    let selectedMode: FinanceMode
    let hasHousehold: Bool
    let month: String
    let currency: CurrencyCode
    let onModeSelected: (FinanceMode) -> Void
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

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(writableModes(hasHousehold: hasHousehold), id: \.self) { mode in
                        Button {
                            onModeSelected(mode)
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: mode.sfSymbol)
                                    .font(.system(size: 12))
                                Text(mode.title)
                                    .font(.subheadline)
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(selectedMode == mode ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                            .foregroundColor(selectedMode == mode ? .white : .primary)
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

private func writableModes(hasHousehold: Bool) -> [FinanceMode] {
    if hasHousehold {
        return [.personal, .shared]
    }
    return [.personal]
}
