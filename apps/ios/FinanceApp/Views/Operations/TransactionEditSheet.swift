import SwiftUI

enum TransactionEditPolicy {
    static func accounts(for transaction: Transaction, in dashboard: FinanceDashboard?) -> [Account] {
        let accounts = (dashboard?.accounts ?? []).filter {
            $0.status == .active &&
            $0.ownershipType == .personal &&
            $0.currency == transaction.currency
        }
        switch transaction.transactionType {
        case .expense:
            return accounts.filter(\.isPaymentAccount)
        case .transfer:
            return accounts.filter { $0.id != transaction.counterpartyAccountId }
        default:
            return accounts
        }
    }

    static func categories(for transaction: Transaction, in dashboard: FinanceDashboard?) -> [Category] {
        let expectedType: CategoryType?
        switch transaction.transactionType {
        case .expense: expectedType = .expense
        case .income: expectedType = .income
        default: expectedType = nil
        }
        guard let expectedType else { return [] }
        return (dashboard?.categories ?? []).filter {
            $0.status == .active && $0.scope == .personal && $0.type == expectedType
        }
    }
}

struct TransactionEditSheet: View {
    let transaction: Transaction
    let dashboard: FinanceDashboard?
    let onSave: (TransactionUpdateRequest) async throws -> Void
    let onDismiss: () -> Void

    @State private var amount: String
    @State private var transactionDate: String
    @State private var accountId: String
    @State private var categoryId: String
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(
        transaction: Transaction,
        dashboard: FinanceDashboard?,
        onSave: @escaping (TransactionUpdateRequest) async throws -> Void,
        onDismiss: @escaping () -> Void
    ) {
        self.transaction = transaction
        self.dashboard = dashboard
        self.onSave = onSave
        self.onDismiss = onDismiss
        _amount = State(initialValue: transaction.amount)
        _transactionDate = State(initialValue: transaction.effectiveTransactionDate)
        _accountId = State(initialValue: transaction.accountId)
        _categoryId = State(initialValue: transaction.categoryId ?? "")
    }

    private var eligibleAccounts: [Account] {
        TransactionEditPolicy.accounts(for: transaction, in: dashboard)
    }

    private var eligibleCategories: [Category] {
        TransactionEditPolicy.categories(for: transaction, in: dashboard)
    }

    private var normalizedAmount: String {
        amount.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: ",", with: ".")
    }

    private var canSave: Bool {
        guard let value = Decimal(string: normalizedAmount), value > .zero else { return false }
        guard !transactionDate.isEmpty, eligibleAccounts.contains(where: { $0.id == accountId }) else { return false }
        if transaction.transactionType == .expense || transaction.transactionType == .income {
            return eligibleCategories.contains { $0.id == categoryId }
        }
        return true
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Операция") {
                    TextField("Сумма", text: $amount)
                        .keyboardType(.decimalPad)
                    DatePickerField(label: "Дата операции", date: $transactionDate)
                }

                Section("Счёт") {
                    if eligibleAccounts.isEmpty {
                        Text("Нет допустимых личных счетов")
                            .foregroundColor(.secondary)
                    } else {
                        Picker("Счёт", selection: $accountId) {
                            ForEach(eligibleAccounts) { account in
                                Text(account.name).tag(account.id)
                            }
                        }
                    }
                }

                if transaction.transactionType == .expense || transaction.transactionType == .income {
                    Section("Категория") {
                        SearchableCategoryPickerButton(
                            title: "Категория",
                            emptyMessage: "Нет доступных категорий",
                            categories: eligibleCategories,
                            selectedCategoryId: $categoryId
                        )
                    }
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundColor(FinanceColors.error)
                    }
                }
            }
            .navigationTitle("Редактировать операцию")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена", action: onDismiss)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Сохранить") {
                        Task { await save() }
                    }
                    .disabled(!canSave || isSaving)
                }
            }
            .onAppear {
                if !eligibleAccounts.contains(where: { $0.id == accountId }) {
                    accountId = eligibleAccounts.first?.id ?? ""
                }
                if (transaction.transactionType == .expense || transaction.transactionType == .income),
                   !eligibleCategories.contains(where: { $0.id == categoryId }) {
                    categoryId = eligibleCategories.first?.id ?? ""
                }
            }
        }
    }

    @MainActor
    private func save() async {
        guard canSave else { return }
        isSaving = true
        errorMessage = nil
        do {
            try await onSave(TransactionUpdateRequest(
                transactionType: nil,
                accountId: accountId,
                counterpartyAccountId: nil,
                categoryId: eligibleCategories.isEmpty ? nil : categoryId,
                amount: normalizedAmount,
                currency: nil,
                occurredAt: nil,
                transactionDate: transactionDate,
                description: nil,
                sourceType: nil,
                version: transaction.version
            ))
            onDismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
        isSaving = false
    }
}
