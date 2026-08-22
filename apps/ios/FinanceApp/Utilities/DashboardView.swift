import Foundation
import SwiftUI

extension FinanceDashboard {
    struct DashboardViewData {
        let visibleAccounts: [Account]
        let visibleTransactions: [Transaction]
        let primaryCurrency: CurrencyCode
        let capital: String
        let accountCount: Int
        let operationCount: Int
        let monthIncome: String
        let monthExpenses: String
        let transferTotal: String
        let topCategories: [CategorySpend]
        let recentTransactions: [Transaction]
        let assetSummaries: [AssetSummary]
    }

    struct CategorySpend {
        let categoryId: String
        let name: String
        let amount: String
        let currency: CurrencyCode
        let sfSymbol: String
        let color: Color
    }

    struct AssetSummary {
        let accountType: AccountType
        let currency: CurrencyCode
        let balance: String
        let count: Int
        let sfSymbol: String
        let color: Color
        let title: String
    }

    struct MonthlyPendingOverlay {
        let income: Decimal
        let expenses: Decimal
        let investments: Decimal
        let expensesByCategory: [String: Decimal]
        let investmentsByAssetCategory: [String: Decimal]

        static let empty = MonthlyPendingOverlay(
            income: .zero,
            expenses: .zero,
            investments: .zero,
            expensesByCategory: [:],
            investmentsByAssetCategory: [:]
        )
    }

    func personalView() -> DashboardViewData {
        let visibleAccounts = personalAccounts
        let visibleTransactions = personalTransactions
        let currency = visibleAccounts.first?.currency ?? .RUB

        let capital = visibleAccounts
            .filter { $0.status == .active }
            .reduce(Decimal.zero) { sum, acc in
                guard acc.currency == currency else { return sum }
                return sum + (Decimal(string: acc.currentBalance) ?? .zero)
            }

        let incomeTotal = visibleTransactions
            .filter { $0.transactionType == .income }
            .reduce(Decimal.zero) { sum, t in
                guard t.currency == currency else { return sum }
                return sum + (Decimal(string: t.amount) ?? .zero)
            }

        let expenseTotal = visibleTransactions
            .filter { $0.transactionType == .expense }
            .reduce(Decimal.zero) { sum, t in
                guard t.currency == currency else { return sum }
                return sum + (Decimal(string: t.amount) ?? .zero)
            }

        let transferTotal = visibleTransactions
            .filter { $0.transactionType == .transfer }
            .reduce(Decimal.zero) { sum, t in
                guard t.currency == currency else { return sum }
                return sum + (Decimal(string: t.amount) ?? .zero)
            }

        let topCategories = serverCategorySpends(currency: currency) ?? topCategorySpends(
            transactions: visibleTransactions,
            allCategories: categories,
            currency: currency
        )

        let recent = visibleTransactions.sorted(by: transactionComesBefore).prefix(4)

        return DashboardViewData(
            visibleAccounts: visibleAccounts,
            visibleTransactions: visibleTransactions,
            primaryCurrency: currency,
            capital: MoneyHelpers.decimalToString(capital),
            accountCount: visibleAccounts.filter { $0.status == .active }.count,
            operationCount: visibleTransactions.count,
            monthIncome: MoneyHelpers.decimalToString(incomeTotal),
            monthExpenses: MoneyHelpers.decimalToString(expenseTotal),
            transferTotal: MoneyHelpers.decimalToString(transferTotal),
            topCategories: topCategories,
            recentTransactions: Array(recent),
            assetSummaries: assetSummaries(accounts: visibleAccounts, currency: currency)
        )
    }

    var personalAccounts: [Account] {
        accounts.filter { $0.ownershipType == .personal && $0.status == .active }
    }

    var personalTransactions: [Transaction] {
        let accountIds = Set(personalAccounts.map(\.id))
        return transactions.filter { accountIds.contains($0.accountId) }
    }

    func sortDateKey(_ transaction: Transaction) -> String {
        transaction.effectiveTransactionDate
    }

    func transactionComesBefore(_ lhs: Transaction, _ rhs: Transaction) -> Bool {
        Transaction.newestFirst(lhs, rhs)
    }

    func pendingMonthlyOverlay(yearMonth: String, currency: CurrencyCode) -> MonthlyPendingOverlay {
        let accountIds = Set(personalAccounts.map(\.id))
        let investmentCategoryIds = Set(assetCategories.filter {
            $0.scopeType == .personal && $0.recordStatus == .active && $0.isInvestment
        }.map(\.id))
        let investmentAccountIds = Set(personalAccounts.compactMap { account in
            account.assetCategoryId.map(investmentCategoryIds.contains) == true ? account.id : nil
        })
        let investmentCategoryByAccount: [String: String] = Dictionary(
            uniqueKeysWithValues: personalAccounts.compactMap { account -> (String, String)? in
            guard let categoryId = account.assetCategoryId,
                  investmentCategoryIds.contains(categoryId) else { return nil }
            return (account.id, categoryId)
            }
        )
        var income = Decimal.zero
        var expenses = Decimal.zero
        var investments = Decimal.zero
        var expensesByCategory: [String: Decimal] = [:]
        var investmentsByAssetCategory: [String: Decimal] = [:]

        let pendingByEntity = Dictionary(grouping: pendingMutations.filter {
            $0.entityType == .transactions && $0.canPush
        }, by: \.entityId)

        for (entityId, mutations) in pendingByEntity {
            let baseline = mutations.compactMap { mutation in
                mutation.analyticsBasePayload.flatMap(decodeTransaction)
            }.first
            let latest = mutations.last
            let current = latest?.operation == .delete
                ? nil
                : personalTransactions.first(where: { $0.id == entityId })
            let baselineContribution = monthlyContribution(
                baseline,
                yearMonth: yearMonth,
                currency: currency,
                accountIds: accountIds,
                investmentAccountIds: investmentAccountIds,
                investmentCategoryByAccount: investmentCategoryByAccount
            )
            let currentContribution = monthlyContribution(
                current,
                yearMonth: yearMonth,
                currency: currency,
                accountIds: accountIds,
                investmentAccountIds: investmentAccountIds,
                investmentCategoryByAccount: investmentCategoryByAccount
            )
            income += currentContribution.income - baselineContribution.income
            expenses += currentContribution.expenses - baselineContribution.expenses
            investments += currentContribution.investments - baselineContribution.investments
            let categoryIds = Set(baselineContribution.expensesByCategory.keys)
                .union(currentContribution.expensesByCategory.keys)
            for categoryId in categoryIds {
                expensesByCategory[categoryId, default: .zero] +=
                    currentContribution.expensesByCategory[categoryId, default: .zero] -
                    baselineContribution.expensesByCategory[categoryId, default: .zero]
            }
            let investmentCategoryIds = Set(baselineContribution.investmentsByAssetCategory.keys)
                .union(currentContribution.investmentsByAssetCategory.keys)
            for categoryId in investmentCategoryIds {
                investmentsByAssetCategory[categoryId, default: .zero] +=
                    currentContribution.investmentsByAssetCategory[categoryId, default: .zero] -
                    baselineContribution.investmentsByAssetCategory[categoryId, default: .zero]
            }
        }

        return MonthlyPendingOverlay(
            income: income,
            expenses: expenses,
            investments: investments,
            expensesByCategory: expensesByCategory,
            investmentsByAssetCategory: investmentsByAssetCategory
        )
    }

    private func decodeTransaction(_ payload: [String: SyncJSONValue]) -> Transaction? {
        guard let data = try? SyncJSONValue.data(from: payload) else { return nil }
        return try? JSONDecoder().decode(Transaction.self, from: data)
    }

    private func monthlyContribution(
        _ transaction: Transaction?,
        yearMonth: String,
        currency: CurrencyCode,
        accountIds: Set<String>,
        investmentAccountIds: Set<String>,
        investmentCategoryByAccount: [String: String]
    ) -> MonthlyPendingOverlay {
        guard let transaction,
              transaction.currency == currency,
              transaction.belongs(toYearMonth: yearMonth),
              accountIds.contains(transaction.accountId) else {
            return .empty
        }
        let amount = Decimal(string: transaction.amount) ?? .zero
        switch transaction.transactionType {
        case .income:
            return MonthlyPendingOverlay(income: amount, expenses: .zero, investments: .zero, expensesByCategory: [:], investmentsByAssetCategory: [:])
        case .expense:
            let byCategory = transaction.categoryId.map { [$0: amount] } ?? [:]
            return MonthlyPendingOverlay(income: .zero, expenses: amount, investments: .zero, expensesByCategory: byCategory, investmentsByAssetCategory: [:])
        case .transfer:
            let investment = transaction.transferStatus != .voided &&
                transaction.counterpartyAccountId.map(investmentAccountIds.contains) == true
                ? amount
                : .zero
            let byAssetCategory = transaction.counterpartyAccountId
                .flatMap { investmentCategoryByAccount[$0] }
                .map { [$0: investment] } ?? [:]
            return MonthlyPendingOverlay(income: .zero, expenses: .zero, investments: investment, expensesByCategory: [:], investmentsByAssetCategory: byAssetCategory)
        default:
            return .empty
        }
    }
}

private extension FinanceDashboard {
    func serverCategorySpends(currency: CurrencyCode) -> [CategorySpend]? {
        let matching = categoryBreakdown.filter {
            $0.currency == currency &&
            ($0.categoryType == .expense || $0.categoryType == nil) &&
            $0.categoryScope != .household
        }
        guard !matching.isEmpty else { return nil }

        return matching
            .map { item in
                let category = item.categoryId.flatMap { categoryId in
                    categories.first { $0.id == categoryId }
                }
                return CategorySpend(
                    categoryId: item.categoryId ?? "uncategorized",
                    name: item.categoryName ?? "Без категории",
                    amount: item.amount,
                    currency: item.currency,
                    sfSymbol: categoryIcon(category),
                    color: categoryColor(category)
                )
            }
            .sorted(by: categorySpendComesBefore)
    }

    func topCategorySpends(
        transactions: [Transaction],
        allCategories: [Category],
        currency: CurrencyCode
    ) -> [CategorySpend] {
        let expenseTxs = transactions.filter { $0.transactionType == .expense && $0.currency == currency }
        var map: [String: Decimal] = [:]
        for tx in expenseTxs {
            guard let catId = tx.categoryId else { continue }
            let amount = Decimal(string: tx.amount) ?? .zero
            map[catId, default: .zero] += amount
        }
        return map
            .map { catId, total in
                let cat = allCategories.first { $0.id == catId }
                return CategorySpend(
                    categoryId: catId,
                    name: cat?.name ?? "Без категории",
                    amount: MoneyHelpers.decimalToString(total),
                    currency: currency,
                    sfSymbol: categoryIcon(cat),
                    color: categoryColor(cat)
                )
            }
            .sorted(by: categorySpendComesBefore)
    }

    func categorySpendComesBefore(_ lhs: CategorySpend, _ rhs: CategorySpend) -> Bool {
        let lhsAmount = Decimal(string: lhs.amount) ?? .zero
        let rhsAmount = Decimal(string: rhs.amount) ?? .zero
        if lhsAmount != rhsAmount { return lhsAmount > rhsAmount }
        if lhs.name != rhs.name { return lhs.name.localizedCaseInsensitiveCompare(rhs.name) == .orderedAscending }
        return lhs.categoryId < rhs.categoryId
    }

    func categoryIcon(_ category: Category?) -> String {
        switch category?.type {
        case .expense: return "tag"
        case .income: return "plus.circle"
        default: return "tag"
        }
    }

    func categoryColor(_ category: Category?) -> Color {
        switch category?.type {
        case .expense: return FinanceColors.expense
        case .income: return FinanceColors.income
        default: return .secondary
        }
    }

    func assetSummaries(accounts: [Account], currency: CurrencyCode) -> [AssetSummary] {
        let active = accounts.filter { $0.status == .active }
        return AccountType.allCases.compactMap { type in
            let filtered = active.filter { $0.accountType == type && $0.currency == currency }
            let balance = filtered.reduce(Decimal.zero) { sum, acc in
                sum + (Decimal(string: acc.currentBalance) ?? .zero)
            }
            return AssetSummary(
                accountType: type,
                currency: currency,
                balance: MoneyHelpers.decimalToString(balance),
                count: filtered.count,
                sfSymbol: type.sfSymbol,
                color: type.color,
                title: type.title
            )
        }
    }
}

extension AccountType {
    var sfSymbol: String {
        switch self {
        case .cash: return "banknote"
        case .bank: return "building.columns"
        case .card: return "creditcard"
        case .deposit: return "piggybank"
        case .brokerage: return "chart.line.uptrend.xyaxis"
        case .metal: return "bitcoinsign.bank"
        case .other: return "centsign.circle"
        }
    }

    var color: Color {
        switch self {
        case .cash: return FinanceColors.income
        case .bank: return FinanceColors.primary
        case .card: return FinanceColors.planningPrimary
        case .deposit: return FinanceColors.investment
        case .brokerage: return FinanceColors.investment
        case .metal: return Color.orange
        case .other: return .secondary
        }
    }

    var title: String {
        switch self {
        case .cash: return "Наличные"
        case .bank: return "Банк"
        case .card: return "Карты"
        case .deposit: return "Вклады"
        case .brokerage: return "Брокер"
        case .metal: return "Металлы"
        case .other: return "Другое"
        }
    }
}
