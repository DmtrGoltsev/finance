import Foundation

enum AssetCategoryScope: String, Codable, Sendable {
    case personal, household
}

struct AssetCategory: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let scopeType: AssetCategoryScope
    let ownerUserId: String?
    let householdId: String?
    let currency: CurrencyCode
    let assetType: AccountType
    let iconKey: String?
    let manualAmount: String
    let isInvestment: Bool
    let recordStatus: RecordStatus
    let version: Int?
}

struct AssetCategoryCreateRequest: Codable, Sendable {
    let name: String
    let scopeType: AssetCategoryScope
    let householdId: String?
    let currency: CurrencyCode
    let assetType: AccountType?
    let iconKey: String?
    let manualAmount: String?
    let isInvestment: Bool?
}

struct AssetCategoryUpdateRequest: Codable, Sendable {
    let name: String?
    let manualAmount: String?
    let assetType: AccountType?
    let iconKey: String?
    let isInvestment: Bool?
    let version: Int?
}

struct InvestmentMigrationCreateRequest: Codable, Sendable {
    let assetCategoryId: String
    let name: String
    let icon: String?
    let color: String?
    let assetType: AccountType
    let currency: CurrencyCode
    let scope: AssetCategoryScope?
    let householdId: String?
    let accountIds: [String]
    let accountVersions: [String: Int]
}

struct AssetCategoryOfflineUpdateRequest: Codable, Sendable {
    let name: String?
    let manualAmount: String?
    let assetType: AccountType?
    let iconKey: String?
    let isInvestment: Bool?

    init(_ request: AssetCategoryUpdateRequest) {
        name = request.name
        manualAmount = request.manualAmount
        assetType = request.assetType
        iconKey = request.iconKey
        isInvestment = request.isInvestment
    }
}

struct AssetCategoryGroup: Codable, Identifiable, Sendable {
    var id: String { assetCategoryId }
    let assetCategoryId: String
    let name: String
    let scopeType: AssetCategoryScope
    let householdId: String?
    let currency: CurrencyCode
    let manualAmount: String
    let accountsTotal: String
    let totalAmount: String
    let isInvestment: Bool
    let assetType: AccountType
    let iconKey: String?
    let accountCount: Int?

    enum CodingKeys: String, CodingKey {
        case assetCategoryId, scopeType, householdId, currency, manualAmount
        case isInvestment, assetType, iconKey, accountCount
        case name = "assetCategoryName"
        case accountsTotal = "linkedAccountsTotal"
        case totalAmount = "currentBalanceTotal"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        assetCategoryId = try c.decode(String.self, forKey: .assetCategoryId)
        name = try c.decode(String.self, forKey: .name)
        scopeType = try c.decode(AssetCategoryScope.self, forKey: .scopeType)
        householdId = try c.decodeIfPresent(String.self, forKey: .householdId)
        currency = try c.decode(CurrencyCode.self, forKey: .currency)
        manualAmount = try c.decodeStringDecimal(forKey: .manualAmount)
        accountsTotal = try c.decodeStringDecimal(forKey: .accountsTotal)
        totalAmount = try c.decodeStringDecimal(forKey: .totalAmount)
        isInvestment = try c.decode(Bool.self, forKey: .isInvestment)
        assetType = try c.decode(AccountType.self, forKey: .assetType)
        iconKey = try c.decodeIfPresent(String.self, forKey: .iconKey)
        accountCount = try c.decodeIfPresent(Int.self, forKey: .accountCount)
    }

    init(
        assetCategoryId: String, name: String, scopeType: AssetCategoryScope,
        householdId: String?, currency: CurrencyCode, manualAmount: String,
        accountsTotal: String, totalAmount: String, isInvestment: Bool,
        assetType: AccountType, iconKey: String?, accountCount: Int?
    ) {
        self.assetCategoryId = assetCategoryId
        self.name = name
        self.scopeType = scopeType
        self.householdId = householdId
        self.currency = currency
        self.manualAmount = manualAmount
        self.accountsTotal = accountsTotal
        self.totalAmount = totalAmount
        self.isInvestment = isInvestment
        self.assetType = assetType
        self.iconKey = iconKey
        self.accountCount = accountCount
    }
}

private extension KeyedDecodingContainer {
    func decodeStringDecimal(forKey key: Key) throws -> String {
        if let s = try? decode(String.self, forKey: key) { return s }
        if let d = try? decode(Double.self, forKey: key) { return String(d) }
        if let i = try? decode(Int.self, forKey: key) { return String(i) }
        return "0"
    }
}
