import SwiftUI

struct CaptureDraftRow: View {
    let draft: CaptureDraft
    let accounts: [Account]
    let categories: [Category]
    let isLoading: Bool
    let onConfirm: (CaptureDraft, String, String, String, String) -> Void
    let onDiscard: (CaptureDraft) -> Void

    @State private var selectedAccountId: String
    @State private var selectedCategoryId: String
    @State private var amount: String
    @State private var occurredDate: String

    init(
        draft: CaptureDraft,
        accounts: [Account],
        categories: [Category],
        isLoading: Bool,
        onConfirm: @escaping (CaptureDraft, String, String, String, String) -> Void,
        onDiscard: @escaping (CaptureDraft) -> Void
    ) {
        self.draft = draft
        self.accounts = accounts
        self.categories = categories
        self.isLoading = isLoading
        self.onConfirm = onConfirm
        self.onDiscard = onDiscard
        _selectedAccountId = State(initialValue: draft.accountId ?? "")
        _selectedCategoryId = State(initialValue: draft.categoryId ?? "")
        _amount = State(initialValue: draft.amount)
        let rawDate = draft.occurredDate ?? String(draft.capturedAt.prefix(10))
        _occurredDate = State(initialValue: rawDate.isEmpty ? DateHelpers.todayDateOnly() : rawDate)
    }

    private var activeAccounts: [Account] {
        accounts
            .filter { $0.status == .active && !$0.id.isEmpty && $0.isPaymentAccount }
    }

    private var expenseCategories: [Category] {
        categories
            .filter { $0.status == .active && $0.type == .expense && !$0.id.isEmpty }
            .sorted { $0.name < $1.name }
    }

    private var confidencePercent: String {
        guard let c = draft.confidence, let d = Decimal(string: c) else { return "?" }
        let percent = d * Decimal(100)
        return "\(NSDecimalNumber(decimal: percent).intValue)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(draft.merchantName ?? (draft.description.isEmpty ? "Распознанный платёж" : draft.description))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .lineLimit(1)
                    Text("скриншот \(occurredDate)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Text("-\(MoneyHelpers.formatShort(amount, currency: draft.currency)) \(MoneyHelpers.currencySymbol(draft.currency))")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(FinanceColors.expense)
            }

            Text("Точность \(confidencePercent)%")
                .font(.caption2)
                .foregroundColor(.secondary)

            HStack(spacing: 8) {
                TextField("Сумма", text: $amount)
                    .keyboardType(.decimalPad)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 120)
            }

            DatePickerField(label: "Дата операции", date: $occurredDate)

            Text("Счёт")
                .font(.caption)
                .fontWeight(.medium)

            if activeAccounts.isEmpty {
                Text("Нет активных счетов")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(activeAccounts) { account in
                            Button {
                                selectedAccountId = account.id
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: account.accountType.sfSymbol)
                                        .font(.caption2)
                                    Text(account.name)
                                        .font(.caption)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(
                                    selectedAccountId == account.id
                                        ? FinanceColors.primary.opacity(0.15)
                                        : Color.secondary.opacity(0.08)
                                )
                                .foregroundColor(
                                    selectedAccountId == account.id
                                        ? FinanceColors.primary
                                        : .primary
                                )
                                .clipShape(Capsule())
                                .overlay(
                                    Capsule()
                                        .stroke(
                                            selectedAccountId == account.id
                                                ? FinanceColors.primary
                                                : Color.secondary.opacity(0.2),
                                            lineWidth: 1
                                        )
                                )
                            }
                        }
                    }
                }
            }

            Text("Категория")
                .font(.caption)
                .fontWeight(.medium)

            if expenseCategories.isEmpty {
                Text("Нет активных категорий расходов")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(expenseCategories) { category in
                            Button {
                                selectedCategoryId = category.id
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: "tag")
                                        .font(.caption2)
                                    Text(category.name)
                                        .font(.caption)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(
                                    selectedCategoryId == category.id
                                        ? FinanceColors.expense.opacity(0.15)
                                        : Color.secondary.opacity(0.08)
                                )
                                .foregroundColor(
                                    selectedCategoryId == category.id
                                        ? FinanceColors.expense
                                        : .primary
                                )
                                .clipShape(Capsule())
                                .overlay(
                                    Capsule()
                                        .stroke(
                                            selectedCategoryId == category.id
                                                ? FinanceColors.expense
                                                : Color.secondary.opacity(0.2),
                                            lineWidth: 1
                                        )
                                )
                            }
                        }
                    }
                }
            }

            HStack(spacing: 8) {
                Button {
                    onDiscard(draft)
                } label: {
                    Text("Отклонить")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(isLoading || draft.id.isEmpty)

                Button {
                    onConfirm(draft, selectedAccountId, selectedCategoryId, amount, occurredDate)
                } label: {
                    Text("Подтвердить")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(isLoading || !canConfirm)
            }
        }
        .padding(12)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
        )
    }

    private var canConfirm: Bool {
        !draft.id.isEmpty
            && !selectedAccountId.isEmpty
            && !selectedCategoryId.isEmpty
            && Decimal(string: amount) != nil
            && !occurredDate.isEmpty
    }
}
