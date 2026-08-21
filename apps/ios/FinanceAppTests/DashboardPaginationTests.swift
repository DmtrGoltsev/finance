import XCTest
@testable import FinanceApp

final class DashboardPaginationTests: XCTestCase {
    func testCollectAllPagesLoadsMoreThanTwoHundredAndDeduplicatesIds() async throws {
        var requestedCursors: [String?] = []

        let items: [String] = try await LiveApiClient.collectAllPages(
            pageSize: 100,
            id: { $0 }
        ) { limit, cursor in
            XCTAssertEqual(limit, 100)
            requestedCursors.append(cursor)
            switch cursor {
            case nil:
                return (
                    (0..<100).map { "tx-\($0)" },
                    PageInfo(limit: limit, nextCursor: "page-2", hasMore: true)
                )
            case "page-2":
                return (
                    ["tx-50"] + (100..<200).map { "tx-\($0)" },
                    PageInfo(limit: limit, nextCursor: "page-3", hasMore: true)
                )
            case "page-3":
                return (
                    ["tx-199"] + (200..<250).map { "tx-\($0)" },
                    PageInfo(limit: limit, nextCursor: nil, hasMore: false)
                )
            default:
                XCTFail("Unexpected cursor: \(cursor ?? "nil")")
                return ([], PageInfo(limit: limit, nextCursor: nil, hasMore: false))
            }
        }

        XCTAssertEqual(items.count, 250)
        XCTAssertEqual(Set(items).count, 250)
        XCTAssertEqual(requestedCursors.count, 3)
        XCTAssertNil(requestedCursors[0])
        XCTAssertEqual(requestedCursors[1], "page-2")
        XCTAssertEqual(requestedCursors[2], "page-3")
    }

    func testCollectAllPagesRejectsRepeatedCursorWithoutLoopingForever() async {
        var requestCount = 0

        do {
            let _: [String] = try await LiveApiClient.collectAllPages(id: { $0 }) { limit, cursor in
                requestCount += 1
                return (
                    [cursor ?? "first"],
                    PageInfo(limit: limit, nextCursor: "repeat", hasMore: true)
                )
            }
            XCTFail("Expected repeated cursor to fail")
        } catch {
            XCTAssertEqual(requestCount, 2)
        }
    }

    func testNewestFirstOrderingIsStableAfterPaginatedDedupe() async throws {
        let first = TestFixtures.transaction(
            id: "same-v2-z",
            accountId: "personal",
            transactionDate: "2026-08-20",
            version: 2
        )
        let duplicate = TestFixtures.transaction(
            id: "same-v2-z",
            accountId: "personal",
            transactionDate: "2026-08-20",
            version: 1
        )
        let tied = TestFixtures.transaction(
            id: "same-v2-a",
            accountId: "personal",
            transactionDate: "2026-08-20",
            version: 2
        )
        let olderVersion = TestFixtures.transaction(
            id: "same-v1",
            accountId: "personal",
            transactionDate: "2026-08-20",
            version: 1
        )
        let olderDate = TestFixtures.transaction(
            id: "older",
            accountId: "personal",
            transactionDate: "2026-08-19",
            version: 99
        )

        let deduplicated: [Transaction] = try await LiveApiClient.collectAllPages(id: \.id) { limit, cursor in
            if cursor == nil {
                return ([olderDate, first, tied], PageInfo(limit: limit, nextCursor: "next", hasMore: true))
            }
            return ([duplicate, olderVersion], PageInfo(limit: limit, nextCursor: nil, hasMore: false))
        }
        let dashboard = FinanceDashboard(
            accounts: [TestFixtures.account(id: "personal")],
            transactions: deduplicated
        )

        XCTAssertEqual(
            deduplicated.sorted(by: dashboard.transactionComesBefore).map(\.id),
            ["same-v2-z", "same-v2-a", "same-v1", "older"]
        )
    }

    func testServerExpenseCategoryBreakdownDrivesAllCategoriesSortedByAmount() {
        let dashboard = FinanceDashboard(
            accounts: [TestFixtures.account(id: "personal")],
            categories: [
                TestFixtures.category(id: "food"),
                TestFixtures.category(id: "taxi"),
            ],
            transactions: [
                TestFixtures.transaction(id: "local-stale", accountId: "personal", categoryId: "taxi", amount: "9999"),
            ],
            categoryBreakdown: [
                breakdownItem(id: "taxi", name: "Такси", amount: "125.50"),
                breakdownItem(id: "food", name: "Еда", amount: "500"),
                CategoryBreakdownItem(
                    categoryId: nil,
                    categoryName: nil,
                    categoryType: nil,
                    categoryScope: nil,
                    currency: .RUB,
                    amount: "50",
                    transactionCount: 1,
                    shareOfVisibleTotal: "0.1"
                ),
                breakdownItem(id: "shared", name: "Общая", amount: "900", scope: .household),
                breakdownItem(id: "salary", name: "Зарплата", amount: "800", type: .income),
            ]
        )

        let top = dashboard.personalView().topCategories
        XCTAssertEqual(top.map(\.categoryId), ["food", "taxi", "uncategorized"])
        XCTAssertEqual(top.map(\.amount), ["500", "125.50", "50"])
    }

    func testCategoryBreakdownReportQueryIsPersonalExpenseForSelectedMonth() {
        let client = LiveApiClient(baseURL: "http://127.0.0.1:8000/finance-api")
        let query = client.reportQuery(
            reportMode: .shared_family_report,
            householdId: "legacy-household",
            startDate: "2026-07-01",
            endDate: "2026-07-31",
            timezone: "Europe/Moscow",
            transactionTypes: [.expense],
            currency: .RUB
        )

        XCTAssertEqual(query["reportMode"], "personal")
        XCTAssertNil(query["householdId"])
        XCTAssertEqual(query["startDate"], "2026-07-01")
        XCTAssertEqual(query["endDate"], "2026-07-31")
        XCTAssertEqual(query["transactionTypes"], "expense")
    }

    private func breakdownItem(
        id: String,
        name: String,
        amount: String,
        type: CategoryType = .expense,
        scope: CategoryScope = .personal
    ) -> CategoryBreakdownItem {
        CategoryBreakdownItem(
            categoryId: id,
            categoryName: name,
            categoryType: type,
            categoryScope: scope,
            currency: .RUB,
            amount: amount,
            transactionCount: 1,
            shareOfVisibleTotal: "0.5"
        )
    }
}
