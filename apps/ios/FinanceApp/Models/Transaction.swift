import Foundation

enum TransactionType: String, Codable, Sendable {
    case income, expense, transfer, brokerage, asset_buy, asset_sell, interest, dividend, adjustment
}

enum TransferScope: String, Codable, Sendable {
    case personal_same_owner, household_same_household
}

enum TransferStatus: String, Codable, Sendable {
    case posted, voided
}

struct Transaction: Codable, Identifiable, Sendable {
    let id: String
    let transactionType: TransactionType
    let accountId: String
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String
    let currency: CurrencyCode
    let occurredAt: String
    let transactionDate: String?
    let description: String?
    let sourceType: String
    let transferScope: TransferScope?
    let transferStatus: TransferStatus?
    let createdAt: String?
    let version: Int?

    init(
        id: String,
        transactionType: TransactionType,
        accountId: String,
        counterpartyAccountId: String?,
        categoryId: String?,
        amount: String,
        currency: CurrencyCode,
        occurredAt: String,
        transactionDate: String?,
        description: String?,
        sourceType: String,
        transferScope: TransferScope?,
        transferStatus: TransferStatus?,
        createdAt: String? = nil,
        version: Int?
    ) {
        self.id = id
        self.transactionType = transactionType
        self.accountId = accountId
        self.counterpartyAccountId = counterpartyAccountId
        self.categoryId = categoryId
        self.amount = amount
        self.currency = currency
        self.occurredAt = occurredAt
        self.transactionDate = transactionDate
        self.description = description
        self.sourceType = sourceType
        self.transferScope = transferScope
        self.transferStatus = transferStatus
        self.createdAt = createdAt
        self.version = version
    }

    var effectiveTransactionDate: String {
        transactionDate ?? String(occurredAt.prefix(10))
    }

    var isPendingLocalMutation: Bool {
        version == nil
    }

    func belongs(toYearMonth yearMonth: String) -> Bool {
        effectiveTransactionDate.hasPrefix("\(yearMonth)-")
    }

    static func newestFirst(_ lhs: Transaction, _ rhs: Transaction) -> Bool {
        if lhs.effectiveTransactionDate != rhs.effectiveTransactionDate {
            return lhs.effectiveTransactionDate > rhs.effectiveTransactionDate
        }
        if lhs.occurredAt != rhs.occurredAt {
            return lhs.occurredAt > rhs.occurredAt
        }
        let lhsCreatedAt = lhs.createdAt ?? ""
        let rhsCreatedAt = rhs.createdAt ?? ""
        if lhsCreatedAt != rhsCreatedAt {
            return lhsCreatedAt > rhsCreatedAt
        }
        return lhs.id > rhs.id
    }
}

struct TransactionCreateRequest: Codable, Sendable {
    let transactionType: TransactionType
    let accountId: String
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String
    let currency: CurrencyCode
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String
}

struct TransactionUpdateRequest: Codable, Sendable {
    let transactionType: TransactionType?
    let accountId: String?
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String?
    let currency: CurrencyCode?
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String?
    let version: Int?
}

struct TransactionOfflineUpdateRequest: Codable, Sendable {
    let transactionType: TransactionType?
    let accountId: String?
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String?
    let currency: CurrencyCode?
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String?

    init(_ request: TransactionUpdateRequest) {
        transactionType = request.transactionType
        accountId = request.accountId
        counterpartyAccountId = request.counterpartyAccountId
        categoryId = request.categoryId
        amount = request.amount
        currency = request.currency
        occurredAt = request.occurredAt
        transactionDate = request.transactionDate
        description = request.description
        sourceType = request.sourceType
    }
}
