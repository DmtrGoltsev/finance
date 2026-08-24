import SwiftUI

struct CategoryBreakdownCard: View {
    let breakdown: ReportCategoryBreakdown?
    let transactions: [Transaction]
    let categories: [Category]
    let pendingOverlay: FinanceDashboard.MonthlyPendingOverlay
    let currency: CurrencyCode

    var body: some View {
        let expenseItems = buildBreakdown()

        VStack(spacing: 12) {
            Text("Разбивка по категориям")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)

            if expenseItems.isEmpty {
                Text("Нет расходов за период")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                let maxAmount = expenseItems.map { $0.amount }.max() ?? Decimal.zero

                ForEach(expenseItems, id: \.categoryId) { item in
                    CategoryBreakdownRow(
                        name: item.name,
                        amount: item.amount,
                        percent: item.percent,
                        barRatio: maxAmount > .zero ? item.amount / maxAmount : .zero,
                        currency: currency
                    )
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private struct BreakdownItem {
        let categoryId: String
        let name: String
        let amount: Decimal
        let percent: String
    }

    private func buildBreakdown() -> [BreakdownItem] {
        if let breakdown {
            return buildReportBreakdown(breakdown)
        }

        let expenseTxs = transactions.filter { $0.transactionType == .expense && $0.currency == currency }
        var map: [String: Decimal] = [:]
        for tx in expenseTxs {
            guard let catId = tx.categoryId else { continue }
            let amount = Decimal(string: tx.amount) ?? .zero
            map[catId, default: .zero] += amount
        }
        let total = map.values.reduce(Decimal.zero, +)
        return map
            .map { catId, amount -> BreakdownItem in
                let cat = categories.first { $0.id == catId }
                let pct = total > .zero ? (amount / total * 100) : .zero
                return BreakdownItem(
                    categoryId: catId,
                    name: cat?.name ?? "Без категории",
                    amount: amount,
                    percent: String(format: "%.1f%%", NSDecimalNumber(decimal: pct).doubleValue)
                )
            }
            .sorted { $0.amount > $1.amount }
    }

    private func buildReportBreakdown(_ report: ReportCategoryBreakdown) -> [BreakdownItem] {
        let filtered = report.items.filter { item in
            item.currency == currency && (item.categoryType == nil || item.categoryType == .expense)
        }
        var amountsByCategory: [String: Decimal] = [:]
        var namesByCategory: [String: String] = [:]
        for item in filtered {
            let key = item.categoryId ?? "uncategorized"
            amountsByCategory[key, default: .zero] += Decimal(string: item.amount) ?? .zero
            namesByCategory[key] = item.categoryName
        }
        for (categoryId, delta) in pendingOverlay.expensesByCategory {
            amountsByCategory[categoryId, default: .zero] += delta
        }
        amountsByCategory = amountsByCategory.filter { $0.value > .zero }
        let total = amountsByCategory.values.reduce(Decimal.zero, +)

        return amountsByCategory
            .map { categoryId, amount -> BreakdownItem in
                let pct = total > .zero ? (amount / total * 100) : .zero
                let fallbackName = categories.first { $0.id == categoryId }?.name
                return BreakdownItem(
                    categoryId: categoryId,
                    name: namesByCategory[categoryId] ?? fallbackName ?? "Без категории",
                    amount: amount,
                    percent: String(format: "%.1f%%", NSDecimalNumber(decimal: pct).doubleValue)
                )
            }
            .sorted { $0.amount > $1.amount }
    }
}

private struct CategoryBreakdownRow: View {
    let name: String
    let amount: Decimal
    let percent: String
    let barRatio: Decimal
    let currency: CurrencyCode

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)
                Spacer()
                Text(percent)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            HStack {
                Text(MoneyHelpers.format(MoneyHelpers.decimalToString(amount), currency: currency))
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
            }
            GeometryReader { geo in
                RoundedRectangle(cornerRadius: 3)
                    .fill(FinanceColors.expense.opacity(0.25))
                    .frame(height: 6)
                    .overlay(alignment: .leading) {
                        let ratio = CGFloat(truncating: NSDecimalNumber(decimal: barRatio))
                        RoundedRectangle(cornerRadius: 3)
                            .fill(FinanceColors.expense)
                            .frame(width: geo.size.width * min(max(ratio, 0), 1), height: 6)
                    }
            }
            .frame(height: 6)
        }
        .padding(.vertical, 4)
    }
}
