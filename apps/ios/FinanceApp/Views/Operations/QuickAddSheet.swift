import SwiftUI

struct QuickAddSheet: View {
    let dashboard: FinanceDashboard?
    let errorMessage: String?
    let onDismiss: () -> Void
    let onSubmit: (QuickAddDraft) -> Void

    @State private var amount = ""
    @State private var type: QuickEntryType = .expense
    @State private var accountId = ""
    @State private var destinationAccountId = ""
    @State private var categoryId = ""
    @State private var transactionDate: String = DateHelpers.todayDateOnly()

    enum QuickEntryType: String, CaseIterable {
        case expense, income, transfer, investment

        var title: String {
            switch self {
            case .expense: return "Расход"
            case .income: return "Доход"
            case .transfer: return "Перевод"
            case .investment: return "Инвестиция"
            }
        }

        var sfSymbol: String {
            switch self {
            case .expense: return "minus.circle"
            case .income: return "plus.circle"
            case .transfer: return "arrow.left.arrow.right"
            case .investment: return "chart.line.uptrend.xyaxis"
            }
        }

        var apiValue: TransactionType {
            switch self {
            case .expense: return .expense
            case .income: return .income
            case .transfer: return .transfer
            case .investment: return .transfer
            }
        }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    TextField("Сумма", text: $amount)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.decimalPad)
                        .font(.title3)

                    typeChips

                    if let msg = errorMessage, !msg.isEmpty {
                        Text(msg)
                            .font(.caption)
                            .foregroundColor(FinanceColors.error)
                    }

                    if type == .expense || type == .income {
                        accountPicker
                        categoryPicker
                    } else {
                        transferSourcePicker
                        transferDestinationPicker
                    }

                    DatePickerField(label: "Дата операции", date: $transactionDate)

                    if let reason = disabledReason {
                        Text(reason)
                            .font(.caption)
                            .foregroundColor(FinanceColors.error)
                    }
                }
                .padding(16)
            }
            .navigationTitle("Быстрое добавление")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена") { onDismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(submitLabel) {
                        submit()
                    }
                    .disabled(disabledReason != nil)
                }
            }
        }
    }

    private var typeChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(QuickEntryType.allCases, id: \.self) { t in
                    Button {
                        type = t
                        categoryId = ""
                        destinationAccountId = ""
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: t.sfSymbol)
                                .font(.system(size: 12))
                            Text(t.title)
                                .font(.subheadline)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(type == t ? FinanceColors.primary : FinanceColors.primaryContainer)
                        .foregroundColor(type == t ? .white : FinanceColors.primary)
                        .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var accountPicker: some View {
        let accounts = operationAccounts
        return VStack(alignment: .leading, spacing: 6) {
            Text("Счёт")
                .font(.caption)
                .fontWeight(.medium)
            if accounts.isEmpty {
                Text("Нет активных счетов")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(accounts) { account in
                            Button {
                                accountId = account.id
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: account.accountType.sfSymbol)
                                        .font(.system(size: 10))
                                    Text(account.name)
                                        .font(.caption)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(accountId == account.id ? FinanceColors.primary : FinanceColors.primaryContainer)
                                .foregroundColor(accountId == account.id ? .white : FinanceColors.primary)
                                .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }

    private var categoryPicker: some View {
        SearchableCategoryPickerButton(
            title: "Категория",
            emptyMessage: "Нет подходящих категорий. Создайте расходную категорию в разделе «Категории расходов».",
            categories: filteredCategories,
            selectedCategoryId: $categoryId
        )
    }

    private var transferSourcePicker: some View {
        let accounts = sourceAccounts
        return VStack(alignment: .leading, spacing: 6) {
            Text("Со счёта")
                .font(.caption)
                .fontWeight(.medium)
            if accounts.isEmpty {
                Text("Нет активных счетов")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(accounts) { account in
                            Button {
                                accountId = account.id
                                destinationAccountId = ""
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: account.accountType.sfSymbol)
                                        .font(.system(size: 10))
                                    Text(account.name)
                                        .font(.caption)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(accountId == account.id ? FinanceColors.primary : FinanceColors.primaryContainer)
                                .foregroundColor(accountId == account.id ? .white : FinanceColors.primary)
                                .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }

    private var transferDestinationPicker: some View {
        let destinations = compatibleDestinations
        return VStack(alignment: .leading, spacing: 6) {
            Text(type == .investment ? "На инвестиционный счёт" : "На счёт")
                .font(.caption)
                .fontWeight(.medium)
            if destinations.isEmpty {
                Text("Нет совместимых счетов для перевода")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(destinations) { account in
                            Button {
                                destinationAccountId = account.id
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: account.accountType.sfSymbol)
                                        .font(.system(size: 10))
                                    Text(account.name)
                                        .font(.caption)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(destinationAccountId == account.id ? FinanceColors.primary : FinanceColors.primaryContainer)
                                .foregroundColor(destinationAccountId == account.id ? .white : FinanceColors.primary)
                                .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }

    private var submitLabel: String {
        switch type {
        case .expense: return "Сохранить расход"
        case .income: return "Сохранить доход"
        case .transfer: return "Сохранить перевод"
        case .investment: return "Сохранить инвестицию"
        }
    }

    private var disabledReason: String? {
        let normalizedAmount = amount.trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: ",", with: ".")
        guard Decimal(string: normalizedAmount) != nil else {
            return "Укажите сумму перед сохранением."
        }
        if type == .expense || type == .income {
            if operationAccounts.isEmpty {
                return type == .expense
                    ? "Нет активного счёта, отмеченного для оплаты. Измените счёт в «Активы»."
                    : "Нет активного счёта. Создайте счёт в «Активы»."
            }
            if filteredCategories.isEmpty {
                return "Нет категории для \(type.title.lowercased()). Создайте категорию."
            }
        } else {
            if sourceAccounts.isEmpty {
                return "Нет активного счёта для перевода."
            }
            if type == .investment && investmentAccounts.isEmpty {
                return "Нет инвестиционного счёта. Отметьте категорию актива как инвестиционную и добавьте к ней счёт."
            }
        }
        return nil
    }

    private var personalAccounts: [Account] {
        let all = dashboard?.accounts ?? []
        return all.filter { $0.status == .active && !$0.id.isEmpty }
            .filter { $0.ownershipType == .personal }
    }

    private var operationAccounts: [Account] {
        let scoped = personalAccounts
        if type == .expense {
            return scoped.filter { $0.isPaymentAccount }
        }
        return scoped
    }

    private var filteredCategories: [Category] {
        let all = dashboard?.categories ?? []
        return all
            .filter { $0.type.rawValue == type.apiValue.rawValue && $0.status == .active }
            .filter { $0.scope == .personal }
    }

    private var investmentAccounts: [Account] {
        let investmentCategoryIds = Set((dashboard?.assetCategories ?? [])
            .filter { $0.scopeType == .personal && $0.recordStatus == .active && $0.isInvestment }
            .map(\.id))
        return personalAccounts.filter { account in
            account.assetCategoryId.map(investmentCategoryIds.contains) == true
        }
    }

    private var sourceAccounts: [Account] {
        type == .investment ? personalAccounts.filter(\.isPaymentAccount) : personalAccounts
    }

    private var compatibleDestinations: [Account] {
        let source = sourceAccounts.first { $0.id == accountId }
        guard let src = source else { return [] }
        let candidates = type == .investment ? investmentAccounts : personalAccounts
        return candidates.filter { candidate in
            candidate.id != src.id &&
            candidate.currency == src.currency
        }
    }

    private func submit() {
        let normalizedAmount = amount.trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: ",", with: ".")
        let firstAccountId = (type == .expense || type == .income
            ? operationAccounts.first
            : sourceAccounts.first)?.id ?? ""
        let firstCategoryId = filteredCategories.first?.id ?? ""

        let draft = QuickAddDraft(
            amount: normalizedAmount,
            type: type,
            accountId: accountId.isEmpty ? firstAccountId : accountId,
            destinationAccountId: destinationAccountId,
            categoryId: categoryId.isEmpty ? firstCategoryId : categoryId,
            transactionDate: transactionDate
        )
        onSubmit(draft)
    }
}

struct QuickAddDraft {
    let amount: String
    let type: QuickAddSheet.QuickEntryType
    let accountId: String
    let destinationAccountId: String
    let categoryId: String
    let transactionDate: String
}
