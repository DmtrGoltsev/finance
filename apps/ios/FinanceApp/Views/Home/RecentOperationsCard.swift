import SwiftUI

struct RecentOperationsCard: View {
    let transactions: [Transaction]
    let categories: [Category]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Последние операции")
                .font(.headline)

            if transactions.isEmpty {
                Text("Операций пока нет. Добавьте первую операцию кнопкой плюс.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(transactions.prefix(4)) { transaction in
                    compactRow(transaction)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
    }

    private func compactRow(_ transaction: Transaction) -> some View {
        HStack(spacing: 10) {
            IconBubble(
                systemName: transaction.sfSymbol,
                color: transaction.tintColor,
                size: 34
            )
            VStack(alignment: .leading, spacing: 2) {
                Text(transaction.displayDescription(categories: categories))
                    .font(.body)
                    .lineLimit(1)
                Text(DateHelpers.displayDate(transaction.sortDateKey))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            Spacer()
            MoneyText(
                amount: transaction.amount,
                currency: transaction.currency,
                type: transaction.transactionType,
                font: .body,
                showSign: true
            )
        }
    }
}

extension Transaction {
    var sfSymbol: String {
        switch transactionType {
        case .income: return "plus.circle"
        case .expense: return "minus.circle"
        case .transfer: return "arrow.left.arrow.right"
        case .brokerage: return "chart.line.uptrend.xyaxis"
        case .asset_buy: return "cart"
        case .asset_sell: return "cart"
        case .interest: return "percent"
        case .dividend: return "arrow.up.right"
        case .adjustment: return "arrow.clockwise"
        }
    }

    var tintColor: Color {
        switch transactionType {
        case .income: return FinanceColors.income
        case .expense: return FinanceColors.expense
        case .transfer: return FinanceColors.transfer
        case .brokerage, .asset_buy, .asset_sell, .interest, .dividend:
            return FinanceColors.investment
        case .adjustment: return .secondary
        }
    }

    var sortDateKey: String {
        transactionDate ?? String(occurredAt.prefix(10))
    }

    func displayDescription(categories: [Category]) -> String {
        if let catId = categoryId,
           let cat = categories.first(where: { $0.id == catId }) {
            return cat.name
        }
        if let desc = description, !desc.isEmpty {
            return desc
        }
        return localizedType
    }

    var localizedType: String {
        switch transactionType {
        case .income: return "Доход"
        case .expense: return "Расход"
        case .transfer: return "Перевод"
        case .brokerage: return "Брокер"
        case .asset_buy: return "Покупка актива"
        case .asset_sell: return "Продажа актива"
        case .interest: return "Проценты"
        case .dividend: return "Дивиденды"
        case .adjustment: return "Корректировка"
        }
    }

    var signedAmount: String {
        let dec = Decimal(string: amount) ?? .zero
        switch transactionType {
        case .income: return "+\(MoneyHelpers.format(amount, currency: currency))"
        case .expense: return "\u{2212}\(MoneyHelpers.format(amount, currency: currency))"
        default: return MoneyHelpers.format(amount, currency: currency)
        }
    }
}
