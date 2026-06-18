import SwiftUI

struct InvestmentsCard: View {
    let investmentsTotal: MoneyAmount?
    let investmentsByCurrency: [MoneyAmount]

    private var hasData: Bool {
        if let total = investmentsTotal, Decimal(string: total.amount) ?? .zero != .zero {
            return true
        }
        return investmentsByCurrency.contains { Decimal(string: $0.amount) ?? .zero != .zero }
    }

    var body: some View {
        if hasData {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    IconBubble(systemName: "chart.line.uptrend.xyaxis", color: FinanceColors.investment, size: 36)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Инвестиции")
                            .font(.headline)
                        if let total = investmentsTotal {
                            Text(MoneyHelpers.format(total.amount, currency: total.currency))
                                .font(.title2)
                                .fontWeight(.bold)
                        }
                    }
                    Spacer()
                }

                ForEach(investmentsByCurrency) { item in
                    HStack {
                        Text(item.currency.rawValue)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(MoneyHelpers.format(item.amount, currency: item.currency))
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(FinanceColors.investment)
                    }
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(FinanceColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
        }
    }
}
