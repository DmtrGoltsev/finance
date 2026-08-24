import Foundation

enum AccountType: String, Codable, CaseIterable, Sendable {
    case cash, bank, card, deposit, brokerage, metal, other
}

enum OwnershipType: String, Codable, Sendable {
    case personal, shared
}

enum RecordStatus: String, Codable, Sendable {
    case active, archived, deleted
}

struct Account: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let accountType: AccountType
    let ownershipType: OwnershipType
    let ownerUserId: String?
    let householdId: String?
    let assetCategoryId: String?
    let currency: CurrencyCode
    let initialBalance: String
    let currentBalance: String
    let isPaymentAccount: Bool
    let status: RecordStatus
    let version: Int?
}

struct AccountCreateRequest: Codable, Sendable {
    let name: String
    let accountType: AccountType
    let ownershipType: OwnershipType
    let householdId: String?
    let assetCategoryId: String?
    let currency: CurrencyCode
    let initialBalance: String
    let isPaymentAccount: Bool?
}

struct AccountUpdateRequest: Codable, Sendable {
    let name: String?
    let currentBalance: String?
    let currency: CurrencyCode?
    let accountType: AccountType?
    let assetCategoryId: String?
    let isPaymentAccount: Bool?
    let version: Int?

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encodeIfPresent(name, forKey: .name)
        try c.encodeIfPresent(currentBalance, forKey: .currentBalance)
        try c.encodeIfPresent(currency, forKey: .currency)
        try c.encodeIfPresent(accountType, forKey: .accountType)
        try c.encodeIfPresent(isPaymentAccount, forKey: .isPaymentAccount)
        try c.encodeIfPresent(version, forKey: .version)
        try c.encode(assetCategoryId, forKey: .assetCategoryId)
    }
}

struct AccountOfflineUpdateRequest: Codable, Sendable {
    let name: String?
    let currency: CurrencyCode?
    let accountType: AccountType?
    let assetCategoryId: String?
    let isPaymentAccount: Bool?

    init(_ request: AccountUpdateRequest) {
        name = request.name
        currency = request.currency
        accountType = request.accountType
        assetCategoryId = request.assetCategoryId
        isPaymentAccount = request.isPaymentAccount
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(name, forKey: .name)
        try container.encodeIfPresent(currency, forKey: .currency)
        try container.encodeIfPresent(accountType, forKey: .accountType)
        try container.encode(assetCategoryId, forKey: .assetCategoryId)
        try container.encodeIfPresent(isPaymentAccount, forKey: .isPaymentAccount)
    }
}
