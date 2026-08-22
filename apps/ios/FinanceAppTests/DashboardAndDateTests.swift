import XCTest
@testable import FinanceApp

final class DashboardAndDateTests: XCTestCase {
    func testDashboardFiltersPersonalDataAndSortsNewestFirstWithStableTiebreakers() {
        let dashboard = FinanceDashboard(
            accounts: [
                TestFixtures.account(id: "personal", payment: true, balance: "100"),
                TestFixtures.account(id: "shared", ownership: .shared, householdId: "h", payment: true, balance: "900"),
            ],
            categories: [TestFixtures.category(id: "food")],
            transactions: [
                TestFixtures.transaction(id: "older", accountId: "personal", occurredAt: "2026-08-19T10:00:00.000Z", transactionDate: "2026-08-19", version: 99),
                TestFixtures.transaction(id: "same-v1", accountId: "personal", transactionDate: "2026-08-20", version: 1),
                TestFixtures.transaction(id: "same-v2-a", accountId: "personal", transactionDate: "2026-08-20", version: 2),
                TestFixtures.transaction(id: "same-v2-z", accountId: "personal", transactionDate: "2026-08-20", version: 2),
                TestFixtures.transaction(id: "shared-tx", accountId: "shared", transactionDate: "2026-08-21", version: 9),
            ]
        )

        let view = dashboard.personalView()

        XCTAssertEqual(view.visibleAccounts.map(\.id), ["personal"])
        XCTAssertFalse(view.visibleTransactions.map(\.id).contains("shared-tx"))
        XCTAssertEqual(
            view.recentTransactions.map(\.id),
            ["same-v2-z", "same-v2-a", "same-v1", "older"]
        )
        XCTAssertEqual(view.capital, "100")
    }

    func testNewestFirstUsesOccurredAtThenCreatedAtThenId() {
        let transactions = [
            TestFixtures.transaction(id: "id-z", accountId: "a", occurredAt: "2026-08-20T10:00:00Z", createdAt: "2026-08-20T10:01:00Z"),
            TestFixtures.transaction(id: "id-a", accountId: "a", occurredAt: "2026-08-20T11:00:00Z", createdAt: "2026-08-20T10:00:00Z"),
            TestFixtures.transaction(id: "id-b", accountId: "a", occurredAt: "2026-08-20T11:00:00Z", createdAt: "2026-08-20T10:00:00Z"),
        ]

        XCTAssertEqual(transactions.sorted(by: Transaction.newestFirst).map(\.id), ["id-b", "id-a", "id-z"])
    }

    func testTransactionDecodesCreatedAtForStableSorting() throws {
        let payload = """
        {
          "id":"tx","transactionType":"expense","accountId":"a","counterpartyAccountId":null,
          "categoryId":"food","amount":"10","currency":"RUB","occurredAt":"2026-08-20T10:00:00Z",
          "transactionDate":"2026-08-20","description":null,"sourceType":"manual","transferScope":null,
          "transferStatus":null,"createdAt":"2026-08-20T10:00:01Z","version":1
        }
        """

        let transaction = try JSONDecoder().decode(Transaction.self, from: Data(payload.utf8))

        XCTAssertEqual(transaction.createdAt, "2026-08-20T10:00:01Z")
    }

    func testPendingOverlayIncludesOnlySelectedMonthAndInvestmentDestinations() {
        let investmentCategory = AssetCategory(
            id: "broker-category",
            name: "Broker",
            scopeType: .personal,
            ownerUserId: "user-a",
            householdId: nil,
            currency: .RUB,
            assetType: .brokerage,
            iconKey: nil,
            manualAmount: "0",
            isInvestment: true,
            recordStatus: .active,
            version: 1
        )
        let dashboard = FinanceDashboard(
            accounts: [
                TestFixtures.account(id: "card", payment: true),
                TestFixtures.account(id: "broker", assetCategoryId: "broker-category"),
            ],
            categories: [TestFixtures.category(id: "food")],
            transactions: [
                TestFixtures.transaction(id: "expense-aug", accountId: "card", categoryId: "food", amount: "250", transactionDate: "2026-08-03", version: nil),
                TestFixtures.transaction(id: "expense-jul", accountId: "card", categoryId: "food", amount: "900", transactionDate: "2026-07-31", version: nil),
                TestFixtures.transaction(id: "investment-aug", accountId: "card", type: .transfer, amount: "1000", transactionDate: "2026-08-10", counterpartyAccountId: "broker", transferStatus: .posted, version: nil),
                TestFixtures.transaction(id: "ordinary-transfer", accountId: "card", type: .transfer, amount: "500", transactionDate: "2026-08-10", counterpartyAccountId: "card", transferStatus: .posted, version: nil),
                TestFixtures.transaction(id: "synced-expense", accountId: "card", categoryId: "food", amount: "700", transactionDate: "2026-08-03", version: 2),
            ],
            assetCategories: [investmentCategory]
        )

        let august = dashboard.pendingMonthlyOverlay(yearMonth: "2026-08", currency: .RUB)
        let july = dashboard.pendingMonthlyOverlay(yearMonth: "2026-07", currency: .RUB)

        XCTAssertEqual(august.expenses, Decimal(250))
        XCTAssertEqual(august.expensesByCategory["food"], Decimal(250))
        XCTAssertEqual(august.investments, Decimal(1000))
        XCTAssertEqual(july.expenses, Decimal(900))
        XCTAssertEqual(july.investments, .zero)
    }

    func testTopExpenseCategoriesAreAggregatedAndSortedDescending() {
        let dashboard = FinanceDashboard(
            accounts: [TestFixtures.account(id: "personal", payment: true)],
            categories: [
                TestFixtures.category(id: "food"),
                TestFixtures.category(id: "taxi"),
            ],
            transactions: [
                TestFixtures.transaction(id: "f1", accountId: "personal", categoryId: "food", amount: "70"),
                TestFixtures.transaction(id: "f2", accountId: "personal", categoryId: "food", amount: "30"),
                TestFixtures.transaction(id: "t1", accountId: "personal", categoryId: "taxi", amount: "40"),
                TestFixtures.transaction(id: "income", accountId: "personal", type: .income, categoryId: "food", amount: "999"),
            ]
        )

        let top = dashboard.personalView().topCategories
        XCTAssertEqual(top.map(\.categoryId), ["food", "taxi"])
        XCTAssertEqual(top.map(\.amount), ["100", "40"])
    }

    func testTransactionCreateSerializesDateOnlyWithoutSyntheticTimestamp() throws {
        let request = TransactionCreateRequest(
            transactionType: .expense,
            accountId: "account",
            counterpartyAccountId: nil,
            categoryId: "food",
            amount: "42.50",
            currency: .RUB,
            occurredAt: nil,
            transactionDate: "2026-02-28",
            description: nil,
            sourceType: "manual"
        )
        let json = try TestFixtures.jsonObject(request)

        XCTAssertEqual(json["transactionDate"] as? String, "2026-02-28")
        XCTAssertNil(json["occurredAt"])
        XCTAssertEqual(DateHelpers.monthEndDate("2024-02"), "2024-02-29")
    }

    func testSelectedMonthReportDecodesInvestmentTransfersTotal() throws {
        let payload = """
        {
          "scope": {"viewerUserId":"user-a","householdId":null,"reportMode":"personal","includedAccountIds":null,"generatedAt":"2026-07-31T23:59:59Z"},
          "period": {"startDate":"2026-07-01","endDate":"2026-07-31","timezone":"Europe/Moscow"},
          "totalsByCurrency": [{"currency":"RUB","incomeTotal":"0","expenseTotal":"0","transferTotal":"12500","netCashFlow":"0","netTotal":"0","investmentsTotal":"12500"}]
        }
        """
        let report = try JSONDecoder().decode(ReportSummary.self, from: Data(payload.utf8))

        XCTAssertEqual(report.period?.startDate, "2026-07-01")
        XCTAssertEqual(report.period?.endDate, "2026-07-31")
        XCTAssertEqual(report.totalsByCurrency.first?.investmentsTotal, "12500")
    }
}
