import SwiftUI

struct QuickAddSheet: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let errorMessage: String?
    let onDismiss: () -> Void
    let onSubmit: (QuickAddDraft) -> Void

    @State private var amount = ""
    @State private var type: QuickEntryType = .expense
    @State private var accountId = ""
    @State private var destinationAccountId = ""
    @State private var categoryId = ""
    @State private var transactionDate: String = DateHelpers.todayDateOnly()
    @State private var visibility: FinanceMode?

    enum QuickEntryType: String, CaseIterable {
        case expense, income, transfer

        var title: String {
            switch self {
            case .expense: return "Расход"
            case .income: return "Доход"
            case .transfer: return "Перевод"
            }
        }

        var sfSymbol: String {
            switch self {
            case .expense: return "minus.circle"
            case .income: return "plus.circle"
            case .transfer: return "arrow.left.arrow.right"
            }
        }

        var apiValue: TransactionType {
            switch self {
            case .expense: return .expense
            case .income: return .income
            case .transfer: return .transfer
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

                    if selectedMode == .overview {
                        Text("Мой обзор read-only: перед сохранением выберите Личное или Общее.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Text("Куда сохранить")
                        .font(.caption)
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    writableModeChips

                    if type != .transfer {
                        accountPicker
                        categoryPicker
                    } else {
                        transferSourcePicker
                        transferDestinationPicker
                    }

                    if type == .expense || type == .income {
                        DatePickerField(label: "Дата операции", date: $transactionDate)
                    }

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
        .onAppear {
            if visibility == nil {
                let writableModes = Self.writableModes(hasHousehold: !(dashboard?.session.householdId?.isEmpty ?? true))
                visibility = writableModes.contains(selectedMode) ? selectedMode : writableModes.first
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

    private var writableModeChips: some View {
        let modes = Self.writableModes(hasHousehold: !(dashboard?.session.householdId?.isEmpty ?? true))
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(modes, id: \.self) { mode in
                    Button {
                        visibility = mode
                        accountId = ""
                        destinationAccountId = ""
                        categoryId = ""
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: mode.sfSymbol)
                                .font(.system(size: 12))
                            Text(mode.title)
                                .font(.subheadline)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(visibility == mode ? FinanceColors.primary : FinanceColors.primaryContainer)
                        .foregroundColor(visibility == mode ? .white : FinanceColors.primary)
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
                Text("Нет активных счетов в выбранном scope")
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
        let cats = filteredCategories
        return VStack(alignment: .leading, spacing: 6) {
            Text("Категория")
                .font(.caption)
                .fontWeight(.medium)
            if cats.isEmpty {
                Text("Нет категории в выбранном scope. Создайте её в разделе «Категории».")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(cats) { cat in
                            Button {
                                categoryId = cat.id
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: "tag")
                                        .font(.system(size: 10))
                                    Text(cat.name)
                                        .font(.caption)
                                        .lineLimit(1)
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(categoryId == cat.id ? FinanceColors.primary : FinanceColors.primaryContainer)
                                .foregroundColor(categoryId == cat.id ? .white : FinanceColors.primary)
                                .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }

    private var transferSourcePicker: some View {
        let accounts = scopedAccounts
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
            Text("На счёт")
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
        }
    }

    private var disabledReason: String? {
        let normalizedAmount = amount.trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: ",", with: ".")
        guard Decimal(string: normalizedAmount) != nil else {
            return "Укажите сумму перед сохранением."
        }
        guard let vis = visibility, vis != .overview else {
            return "Мой обзор read-only. Выберите Личное или Общее."
        }
        if type != .transfer {
            if operationAccounts.isEmpty {
                return "В режиме \(vis.title) нет активного счёта. Создайте счёт в «Активы»."
            }
            if filteredCategories.isEmpty {
                return "В режиме \(vis.title) нет категории для \(type.title.lowercased()). Создайте категорию."
            }
        } else {
            if scopedAccounts.isEmpty {
                return "В режиме \(vis.title) нет активного счёта для перевода."
            }
        }
        return nil
    }

    private var scopedAccounts: [Account] {
        guard let vis = visibility else { return [] }
        let all = dashboard?.accounts ?? []
        return all.filter { $0.status == .active && !$0.id.isEmpty }
            .filteredByMode(vis, householdId: dashboard?.session.householdId)
    }

    private var operationAccounts: [Account] {
        let scoped = scopedAccounts
        if type == .expense {
            return scoped.filter { $0.isPaymentAccount }
        }
        return scoped
    }

    private var filteredCategories: [Category] {
        guard let vis = visibility else { return [] }
        let all = dashboard?.categories ?? []
        return all
            .filter { $0.type.rawValue == type.apiValue.rawValue && $0.status == .active }
            .filteredByMode(vis, householdId: dashboard?.session.householdId)
    }

    private var compatibleDestinations: [Account] {
        let source = scopedAccounts.first { $0.id == accountId }
        guard let src = source else { return [] }
        return scopedAccounts.filter { candidate in
            candidate.id != src.id &&
            candidate.currency == src.currency &&
            candidate.ownershipType == src.ownershipType
        }
    }

    private func submit() {
        let normalizedAmount = amount.trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: ",", with: ".")
        let firstAccountId = operationAccounts.first?.id ?? ""
        let firstCategoryId = filteredCategories.first?.id ?? ""

        let draft = QuickAddDraft(
            amount: normalizedAmount,
            type: type,
            accountId: accountId.isEmpty ? firstAccountId : accountId,
            destinationAccountId: destinationAccountId,
            categoryId: categoryId.isEmpty ? firstCategoryId : categoryId,
            visibility: visibility ?? selectedMode,
            transactionDate: transactionDate
        )
        onSubmit(draft)
    }

    static func writableModes(hasHousehold: Bool) -> [FinanceMode] {
        hasHousehold ? [.personal, .shared] : [.personal]
    }
}

struct QuickAddDraft {
    let amount: String
    let type: QuickAddSheet.QuickEntryType
    let accountId: String
    let destinationAccountId: String
    let categoryId: String
    let visibility: FinanceMode
    let transactionDate: String
}

extension Array where Element == Account {
    func filteredByMode(_ mode: FinanceMode, householdId: String?) -> [Account] {
        switch mode {
        case .personal:
            return filter { $0.ownershipType == .personal }
        case .shared:
            return filter { $0.ownershipType == .shared && $0.householdId == householdId }
        case .overview:
            return self
        }
    }
}

extension Array where Element == Category {
    func filteredByMode(_ mode: FinanceMode, householdId: String?) -> [Category] {
        switch mode {
        case .personal:
            return filter { $0.scope == .personal }
        case .shared:
            return filter { $0.scope == .household && $0.householdId == householdId }
        case .overview:
            return self
        }
    }
}
