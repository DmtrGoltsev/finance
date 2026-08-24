import XCTest
import Security
@testable import FinanceApp

@MainActor
final class PersonalOnlyContractTests: XCTestCase {
    func testKeychainUsesDeviceBoundAccessibility() {
        XCTAssertTrue(CFEqual(
            DeviceBoundKeychain.accessibility,
            kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ))
        XCTAssertTrue(CFEqual(
            CategoryAggregateMappingStore.keychainAccessibility,
            kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ))
    }

    func testDeviceBoundKeychainPersistsThisDeviceOnlyAttribute() throws {
        let service = "com.finance.tests.\(UUID().uuidString)"
        let account = "device-bound"
        defer { DeviceBoundKeychain.delete(service: service, account: account) }

        XCTAssertEqual(
            DeviceBoundKeychain.saveString("secret", service: service, account: account),
            errSecSuccess
        )

        var result: AnyObject?
        let status = SecItemCopyMatching([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnAttributes as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ] as CFDictionary, &result)
        XCTAssertEqual(status, errSecSuccess)
        let attributes = try XCTUnwrap(result as? [String: Any])
        let accessibility = try XCTUnwrap(attributes[kSecAttrAccessible as String])
        XCTAssertTrue(CFEqual(accessibility as CFTypeRef, kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly))
    }

    func testPersonalCreatePayloadsNeverCarryHousehold() throws {
        let account = AccountCreateRequest(
            name: "Card",
            accountType: .card,
            ownershipType: .personal,
            householdId: nil,
            assetCategoryId: nil,
            currency: .RUB,
            initialBalance: "100",
            isPaymentAccount: true
        )
        let category = CategoryCreateRequest(
            name: "Food",
            type: .expense,
            scope: .personal,
            householdId: nil,
            iconKey: nil,
            color: nil
        )
        let asset = AssetCategoryCreateRequest(
            name: "Broker",
            scopeType: .personal,
            householdId: nil,
            currency: .RUB,
            assetType: .brokerage,
            iconKey: nil,
            manualAmount: "0",
            isInvestment: true
        )

        let accountJSON = try TestFixtures.jsonObject(account)
        let categoryJSON = try TestFixtures.jsonObject(category)
        let assetJSON = try TestFixtures.jsonObject(asset)

        XCTAssertEqual(accountJSON["ownershipType"] as? String, "personal")
        XCTAssertNil(accountJSON["householdId"])
        XCTAssertEqual(categoryJSON["scope"] as? String, "personal")
        XCTAssertNil(categoryJSON["householdId"])
        XCTAssertEqual(assetJSON["scopeType"] as? String, "personal")
        XCTAssertNil(assetJSON["householdId"])
    }

    func testReportQueryForcesPersonalModeAndSelectedMonth() {
        let client = LiveApiClient(baseURL: "http://127.0.0.1:8000/finance-api")
        let query = client.reportQuery(
            reportMode: .combined_viewer_overview,
            householdId: "legacy-household",
            startDate: "2026-07-01",
            endDate: "2026-07-31",
            timezone: "Europe/Moscow",
            accountIds: nil,
            categoryIds: nil,
            transactionTypes: [.transfer],
            currency: .RUB
        )

        XCTAssertEqual(query["reportMode"], "personal")
        XCTAssertNil(query["householdId"])
        XCTAssertEqual(query["startDate"], "2026-07-01")
        XCTAssertEqual(query["endDate"], "2026-07-31")
        XCTAssertEqual(query["transactionTypes"], "transfer")
    }

    func testQuickExpenseUsesOnlyPersonalPaymentAccountsAndExpenseCategories() {
        let dashboard = FinanceDashboard(
            accounts: [
                TestFixtures.account(id: "payment", payment: true),
                TestFixtures.account(id: "not-payment", payment: false),
                TestFixtures.account(id: "shared", ownership: .shared, householdId: "h", payment: true),
                TestFixtures.account(id: "archived", payment: true, status: .archived),
            ],
            categories: [
                TestFixtures.category(id: "expense"),
                TestFixtures.category(id: "income", type: .income),
                TestFixtures.category(id: "household", scope: .household, householdId: "h"),
                TestFixtures.category(id: "archived-expense", status: .archived),
            ]
        )
        let sheet = QuickAddSheet(
            dashboard: dashboard,
            errorMessage: nil,
            onDismiss: {},
            onSubmit: { _ in }
        )

        XCTAssertEqual(sheet.operationAccounts.map(\.id), ["payment"])
        XCTAssertEqual(sheet.filteredCategories.map(\.id), ["expense"])
    }
}
