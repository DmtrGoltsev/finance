import XCTest
@testable import FinanceApp

@MainActor
final class IOSUXParityTests: XCTestCase {
    func testCategoryPickerSearchIsCaseInsensitivePartialAndAlphabetical() {
        let categories = [
            TestFixtures.category(id: "taxi"),
            FinanceCategory(
                id: "cafe",
                name: "Кафе и рестораны",
                type: .expense,
                scope: .personal,
                ownerUserId: "user-a",
                householdId: nil,
                iconKey: nil,
                color: nil,
                status: .active,
                version: 1
            ),
            FinanceCategory(
                id: "coffee",
                name: "Кофе",
                type: .expense,
                scope: .personal,
                ownerUserId: "user-a",
                householdId: nil,
                iconKey: nil,
                color: nil,
                status: .active,
                version: 1
            ),
        ]

        XCTAssertEqual(CategoryPickerSearch.filtered(categories, query: "ФЕ").map(\.id), ["cafe", "coffee"])
        XCTAssertEqual(Set(CategoryPickerSearch.filtered(categories, query: "  ").map(\.id)), Set(["taxi", "cafe", "coffee"]))
    }

    func testCategoryPickerContractIsModalAndVertical() {
        XCTAssertTrue(CategoryPickerSearch.usesModalVerticalList)
        XCTAssertEqual(CategoryPickerSearch.openAccessibilityIdentifier, "categoryPicker.open")
        XCTAssertEqual(CategoryPickerSearch.verticalListAccessibilityIdentifier, "categoryPicker.verticalList")
    }

    func testExpenseEditorAllowsOnlyPersonalPaymentAccountsAndExpenseCategories() {
        let transaction = TestFixtures.transaction(id: "expense", accountId: "payment", type: .expense)
        let dashboard = FinanceDashboard(
            accounts: [
                TestFixtures.account(id: "payment", payment: true),
                TestFixtures.account(id: "not-payment", payment: false),
                TestFixtures.account(id: "shared", ownership: .shared, householdId: "h", payment: true),
            ],
            categories: [
                TestFixtures.category(id: "expense"),
                TestFixtures.category(id: "income", type: .income),
                TestFixtures.category(id: "shared-category", scope: .household, householdId: "h"),
            ]
        )

        XCTAssertEqual(TransactionEditPolicy.accounts(for: transaction, in: dashboard).map(\.id), ["payment"])
        XCTAssertEqual(TransactionEditPolicy.categories(for: transaction, in: dashboard).map(\.id), ["expense"])
    }

    func testHistoricalMonthShowsCurrentMonthShortcut() {
        XCTAssertTrue(ReportMonthSwitcher.showsCurrentMonthButton("2020-01"))
        XCTAssertFalse(ReportMonthSwitcher.showsCurrentMonthButton(DateHelpers.currentYearMonth()))
    }
}
