import Foundation
import XCTest
@testable import FinanceApp

enum TestFixtures {
    static func account(
        id: String,
        ownership: OwnershipType = .personal,
        householdId: String? = nil,
        payment: Bool = false,
        status: RecordStatus = .active,
        balance: String = "0"
    ) -> Account {
        Account(
            id: id,
            name: id,
            accountType: .card,
            ownershipType: ownership,
            ownerUserId: ownership == .personal ? "user-a" : nil,
            householdId: householdId,
            assetCategoryId: nil,
            currency: .RUB,
            initialBalance: balance,
            currentBalance: balance,
            isPaymentAccount: payment,
            status: status,
            version: 1
        )
    }

    static func category(
        id: String,
        type: CategoryType = .expense,
        scope: CategoryScope = .personal,
        householdId: String? = nil,
        status: RecordStatus = .active
    ) -> FinanceCategory {
        FinanceCategory(
            id: id,
            name: id,
            type: type,
            scope: scope,
            ownerUserId: scope == .personal ? "user-a" : nil,
            householdId: householdId,
            iconKey: nil,
            color: nil,
            status: status,
            version: 1
        )
    }

    static func transaction(
        id: String,
        accountId: String,
        type: TransactionType = .expense,
        categoryId: String? = nil,
        amount: String = "1",
        occurredAt: String = "2026-08-20T10:00:00.000Z",
        transactionDate: String? = "2026-08-20",
        version: Int? = 1
    ) -> Transaction {
        Transaction(
            id: id,
            transactionType: type,
            accountId: accountId,
            counterpartyAccountId: nil,
            categoryId: categoryId,
            amount: amount,
            currency: .RUB,
            occurredAt: occurredAt,
            transactionDate: transactionDate,
            description: nil,
            sourceType: "manual",
            transferScope: nil,
            transferStatus: nil,
            version: version
        )
    }

    static func jsonObject<T: Encodable>(_ value: T) throws -> [String: Any] {
        let data = try JSONEncoder().encode(value)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }
}
