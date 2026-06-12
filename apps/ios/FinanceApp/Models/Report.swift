import Foundation

enum ReportMode: String, Codable, Sendable {
    case personal
    case shared_family_report
    case combined_viewer_overview
}

enum ReportBucket: String, Codable, Sendable {
    case day, month
}

struct ReportScope: Codable, Sendable {
    let viewerUserId: String
    let householdId: String?
    let reportMode: ReportMode
    let includedAccountIds: [String]?
    let generatedAt: String
}

struct ReportPeriod: Codable, Sendable {
    let startDate: String
    let endDate: String
    let timezone: String
}

struct ReportSummary: Codable, Sendable {
    let scope: ReportScope?
    let period: ReportPeriod?
    let totalsByCurrency: [MoneyTotal]
}

struct CategoryBreakdownItem: Codable, Identifiable, Sendable {
    var id: String { categoryId ?? UUID().uuidString }
    let categoryId: String?
    let categoryName: String?
    let categoryType: CategoryType?
    let categoryScope: CategoryScope?
    let currency: CurrencyCode
    let amount: String
    let transactionCount: Int
    let shareOfVisibleTotal: String
}

struct ReportCategoryBreakdown: Codable, Sendable {
    let scope: ReportScope?
    let period: ReportPeriod?
    let items: [CategoryBreakdownItem]
}

struct AccountBalance: Codable, Identifiable, Sendable {
    let accountId: String
    let accountName: String
    let accountType: AccountType
    let ownershipType: OwnershipType
    let householdId: String?
    let ownerUserId: String?
    let assetCategoryId: String?
    let currency: CurrencyCode
    let currentBalance: String
    let balanceAsOf: String
}

struct AccountBalanceGroup: Codable, Sendable {
    let accountType: AccountType
    let currency: CurrencyCode
    let currentBalanceTotal: String
    let accountCount: Int
}

struct NetWorthTotal: Codable, Sendable {
    let currency: CurrencyCode
    let netWorthTotal: String
}

struct InvestmentTotal: Codable, Sendable {
    let currency: CurrencyCode
    let investmentsTotal: String
}

struct ReportAccountBalances: Codable, Sendable {
    let scope: ReportScope?
    let asOfDate: String?
    let timezone: String?
    let items: [AccountBalance]
    let balanceGroups: [AccountBalanceGroup]
    let assetsByType: [AccountBalanceGroup]
    let assetCategoryGroups: [AssetCategoryGroup]
    let legacyAssetTypeGroups: [AccountBalanceGroup]
    let totalsByCurrency: [NetWorthTotal]
    let investmentsByCurrency: [InvestmentTotal]
}

struct CashFlowPoint: Codable, Identifiable, Sendable {
    var id: String { "\(periodStartDate)-\(periodEndDate)" }
    let periodStartDate: String
    let periodEndDate: String
    let totalsByCurrency: [MoneyTotal]
}

struct ReportCashFlow: Codable, Sendable {
    let scope: ReportScope?
    let period: ReportPeriod?
    let bucket: ReportBucket
    let points: [CashFlowPoint]
}

struct ReportTransactionDrillDown: Codable, Sendable {
    let scope: ReportScope?
    let period: ReportPeriod?
    let items: [Transaction]
    let page: PageInfo
}

struct PageInfo: Codable, Sendable {
    let limit: Int
    let nextCursor: String?
    let hasMore: Bool
}
