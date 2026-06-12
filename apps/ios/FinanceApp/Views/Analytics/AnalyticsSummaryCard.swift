import SwiftUI

struct AnalyticsSummaryCard: View {
    let totals: [MoneyTotal]
    let transferCount: Int
    let currency: CurrencyCode

    var body: some View {
        let total = totals.first { $0.currency == currency }

        VStack(spacing: 12) {
            Text("Сводка")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)

            HStack(spacing: 8) {
                SummaryMetricTile(
                    title: "Доходы",
                    value: MoneyHelpers.format(total?.incomeTotal ?? "0", currency: currency),
                    color: FinanceColors.income,
                    icon: "arrow.up.circle"
                )
                SummaryMetricTile(
                    title: "Расходы",
                    value: MoneyHelpers.format(total?.expenseTotal ?? "0", currency: currency),
                    color: FinanceColors.expense,
                    icon: "arrow.down.circle"
                )
            }

            HStack(spacing: 8) {
                SummaryMetricTile(
                    title: "Итог",
                    value: MoneyHelpers.format(total?.netTotal ?? "0", currency: currency),
                    color: FinanceColors.primary,
                    icon: "equal.circle"
                )
                SummaryMetricTile(
                    title: "Переводы",
                    value: "\(transferCount)",
                    color: FinanceColors.transfer,
                    icon: "arrow.right.arrow.left.circle"
                )
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private struct SummaryMetricTile: View {
    let title: String
    let value: String
    let color: Color
    let icon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundColor(color)
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
