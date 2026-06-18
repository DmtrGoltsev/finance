import Foundation

enum TransactionType: String, Codable, Sendable {
    case income, expense, transfer, brokerage, asset_buy, asset_sell, interest, dividend, adjustment
}

enum TransferScope: String, Codable, Sendable {
    case personal_same_owner, household_same_household
}

enum TransferStatus: String, Codable, Sendable {
    case posted, voided
}

struct Transaction: Codable, Identifiable, Sendable {
    let id: String
    let transactionType: TransactionType
    let accountId: String
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String
    let currency: CurrencyCode
    let occurredAt: String
    let transactionDate: String?
    let description: String?
    let sourceType: String
    let transferScope: TransferScope?
    let transferStatus: TransferStatus?
    let version: Int?
}

struct TransactionCreateRequest: Codable, Sendable {
    let transactionType: TransactionType
    let accountId: String
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String
    let currency: CurrencyCode
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String
}

struct TransactionUpdateRequest: Codable, Sendable {
    let transactionType: TransactionType?
    let accountId: String?
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String?
    let currency: CurrencyCode?
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String?
    let version: Int?
}
