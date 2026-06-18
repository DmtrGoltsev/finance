import Foundation

enum MoneyHelpers {
    static let rubFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.numberStyle = .decimal
        f.minimumFractionDigits = 2
        f.maximumFractionDigits = 2
        return f
    }()

    static func format(_ decimalString: String, currency: CurrencyCode) -> String {
        let decimal = Decimal(string: decimalString) ?? .zero
        let formatted = rubFormatter.string(from: decimal as NSDecimalNumber) ?? decimalString
        return "\(formatted) \(currencySymbol(currency))"
    }

    static func formatShort(_ decimalString: String, currency: CurrencyCode) -> String {
        let decimal = Decimal(string: decimalString) ?? .zero
        let formatted = rubFormatter.string(from: decimal as NSDecimalNumber) ?? decimalString
        return formatted
    }

    static func currencySymbol(_ currency: CurrencyCode) -> String {
        switch currency {
        case .RUB: return "₽"
        case .USD: return "$"
        case .EUR: return "€"
        case .XAU: return "граммы"
        }
    }

    static func currencyLabel(_ currency: CurrencyCode) -> String {
        switch currency {
        case .RUB: return "₽ RUB"
        case .USD: return "$ USD"
        case .EUR: return "€ EUR"
        case .XAU: return "граммы XAU"
        }
    }

    static func parseDecimal(_ string: String) -> Decimal {
        Decimal(string: string) ?? .zero
    }

    static func decimalToString(_ decimal: Decimal) -> String {
        let ns = decimal as NSDecimalNumber
        let rounded = ns.rounding(accordingToBehavior: NSDecimalNumberHandler(roundingMode: .plain, scale: 4, raiseOnExactness: false, raiseOnOverflow: false, raiseOnUnderflow: false, raiseOnDivideByZero: false))
        return rounded.stringValue
    }
}
