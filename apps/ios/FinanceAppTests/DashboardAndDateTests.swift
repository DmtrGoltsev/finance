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
