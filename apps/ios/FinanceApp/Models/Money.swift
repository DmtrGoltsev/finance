import Foundation

enum CurrencyCode: String, Codable, CaseIterable, Sendable {
    case RUB, USD, EUR, XAU
}

struct MoneyAmount: Codable, Identifiable, Sendable {
    var id: String { currency.rawValue }
    let currency: CurrencyCode
    let amount: String
}

struct MoneyTotal: Codable, Sendable {
    let currency: CurrencyCode
    let incomeTotal: String
    let expenseTotal: String
    let transferTotal: String?
    let netCashFlow: String?
    let netTotal: String
    let investmentsTotal: String?

    enum CodingKeys: String, CodingKey {
        case currency, incomeTotal, expenseTotal, transferTotal
        case netCashFlow, netTotal, investmentsTotal
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        currency = try c.decode(CurrencyCode.self, forKey: .currency)
        incomeTotal = try c.decodeString(forKey: .incomeTotal)
        expenseTotal = try c.decodeString(forKey: .expenseTotal)
        transferTotal = try c.decodeIfPresent(String.self, forKey: .transferTotal)
        netCashFlow = try c.decodeIfPresent(String.self, forKey: .netCashFlow)
        netTotal = try c.decodeString(forKey: .netTotal)
        investmentsTotal = try c.decodeIfPresent(String.self, forKey: .investmentsTotal)
    }
}

private extension KeyedDecodingContainer {
    func decodeString(forKey key: Key) throws -> String {
        if let str = try? decode(String.self, forKey: key) {
            return str
        }
        if let num = try? decode(Double.self, forKey: key) {
            return String(num)
        }
        if let int = try? decode(Int.self, forKey: key) {
            return String(int)
        }
        return "0"
    }
}
