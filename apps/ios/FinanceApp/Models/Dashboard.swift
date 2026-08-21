import Foundation

@Observable
final class FinanceDashboard: @unchecked Sendable {
    var session: SessionStatus
    var accounts: [Account]
    var categories: [Category]
    var transactions: [Transaction]
    var totals: [MoneyTotal]
    var reportTransferCount: Int
    var assetCategories: [AssetCategory]
    var assetCategoryGroups: [AssetCategoryGroup]
    var investmentsByCurrency: [MoneyAmount]
    var investmentsTotal: MoneyAmount?
    var categoryBreakdown: [CategoryBreakdownItem]

    init(
        session: SessionStatus = SessionStatus(isAuthenticated: false, displayName: nil, householdId: nil),
        accounts: [Account] = [],
        categories: [Category] = [],
        transactions: [Transaction] = [],
        totals: [MoneyTotal] = [],
        reportTransferCount: Int = 0,
        assetCategories: [AssetCategory] = [],
        assetCategoryGroups: [AssetCategoryGroup] = [],
        investmentsByCurrency: [MoneyAmount] = [],
        investmentsTotal: MoneyAmount? = nil,
        categoryBreakdown: [CategoryBreakdownItem] = []
    ) {
        self.session = session
        self.accounts = accounts
        self.categories = categories
        self.transactions = transactions
        self.totals = totals
        self.reportTransferCount = reportTransferCount
        self.assetCategories = assetCategories
        self.assetCategoryGroups = assetCategoryGroups
        self.investmentsByCurrency = investmentsByCurrency
        self.investmentsTotal = investmentsTotal
        self.categoryBreakdown = categoryBreakdown
    }
}
