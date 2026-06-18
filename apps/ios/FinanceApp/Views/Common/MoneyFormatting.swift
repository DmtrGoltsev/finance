import SwiftUI

extension View {
    func moneyForeground(_ type: TransactionType) -> some View {
        switch type {
        case .income: return self.foregroundColor(FinanceColors.income)
        case .expense: return self.foregroundColor(FinanceColors.expense)
        case .transfer: return self.foregroundColor(FinanceColors.transfer)
        default: return self.foregroundColor(.primary)
        }
    }
}

struct MoneyText: View {
    let amount: String
    let currency: CurrencyCode
    let type: TransactionType?
    let font: Font
    let showSign: Bool

    init(
        amount: String,
        currency: CurrencyCode,
        type: TransactionType? = nil,
        font: Font = .body,
        showSign: Bool = false
    ) {
        self.amount = amount
        self.currency = currency
        self.type = type
        self.font = font
        self.showSign = showSign
    }

    var body: some View {
        Text(formatted)
            .font(font)
            .fontWeight(.semibold)
            .foregroundColor(color)
    }

    private var formatted: String {
        let base = MoneyHelpers.format(amount, currency: currency)
        guard showSign, let t = type else { return base }
        let dec = Decimal(string: amount) ?? .zero
        if dec == .zero { return base }
        switch t {
        case .income: return "+\(base)"
        case .expense: return "\u{2212}\(base)"
        case .transfer: return base
        default: return base
        }
    }

    private var color: Color {
        guard let t = type else { return .primary }
        switch t {
        case .income: return FinanceColors.income
        case .expense: return FinanceColors.expense
        case .transfer: return FinanceColors.transfer
        default: return .primary
        }
    }
}
