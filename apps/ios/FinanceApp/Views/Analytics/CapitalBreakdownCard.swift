import SwiftUI

struct CapitalBreakdownCard: View {
    let groups: [AssetCategoryGroup]
    let currency: CurrencyCode

    var body: some View {
        let filtered = groups.filter { $0.currency == currency }
        let total = filtered.reduce(Decimal.zero) { sum, g in
            sum + (Decimal(string: g.totalAmount) ?? .zero)
        }

        VStack(spacing: 12) {
            Text("Капитал по типам активов")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)

            if filtered.isEmpty {
                Text("Нет активов")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                let maxAmount = filtered.map { Decimal(string: $0.totalAmount) ?? .zero }.max() ?? .zero

                ForEach(filtered) { group in
                    let amount = Decimal(string: group.totalAmount) ?? .zero
                    let ratio = maxAmount > .zero ? amount / maxAmount : .zero
                    let pct = total > .zero ? amount / total * 100 : .zero

                    CapitalBreakdownRow(
                        name: group.name,
                        amount: MoneyHelpers.format(group.totalAmount, currency: currency),
                        percent: String(format: "%.1f%%", NSDecimalNumber(decimal: pct).doubleValue),
                        barRatio: CGFloat(truncating: NSDecimalNumber(decimal: ratio)),
                        isInvestment: group.isInvestment,
                        sfSymbol: group.assetType.sfSymbol
                    )
                }

                Divider()

                HStack {
                    Text("Итого")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Spacer()
                    Text(MoneyHelpers.format(MoneyHelpers.decimalToString(total), currency: currency))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private struct CapitalBreakdownRow: View {
    let name: String
    let amount: String
    let percent: String
    let barRatio: CGFloat
    let isInvestment: Bool
    let sfSymbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: sfSymbol)
                    .font(.system(size: 12))
                    .foregroundColor(isInvestment ? FinanceColors.investment : FinanceColors.primary)
                Text(name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)
                Spacer()
                Text(percent)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Text(amount)
                .font(.caption)
                .foregroundColor(.secondary)
            GeometryReader { geo in
                RoundedRectangle(cornerRadius: 3)
                    .fill((isInvestment ? FinanceColors.investment : FinanceColors.primary).opacity(0.2))
                    .frame(height: 6)
                    .overlay(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(isInvestment ? FinanceColors.investment : FinanceColors.primary)
                            .frame(width: geo.size.width * min(max(barRatio, 0), 1), height: 6)
                    }
            }
            .frame(height: 6)
        }
        .padding(.vertical, 2)
    }
}
