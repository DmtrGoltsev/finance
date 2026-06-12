import SwiftUI

struct AccountEditDialog: View {
    let account: Account
    let assetCategories: [AssetCategory]
    let onSave: (String, AccountUpdateRequest) async -> Void
    let onArchive: () async -> Void
    let onDismiss: () -> Void

    @State private var name: String = ""
    @State private var balance: String = ""
    @State private var currency: CurrencyCode = .RUB
    @State private var assetCategoryId: String?
    @State private var isPaymentAccount: Bool = false
    @State private var isLoading = false
    @State private var errorMessage: String?

    private var canSave: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && Decimal(string: balance) != nil
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Название", text: $name)
                    TextField("Баланс", text: $balance)
                        .keyboardType(.decimalPad)
                } header: {
                    Text("Основное")
                }

                Section {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(CurrencyCode.allCases, id: \.self) { cur in
                                Button {
                                    currency = cur
                                } label: {
                                    Text(MoneyHelpers.currencyLabel(cur))
                                        .font(.subheadline)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 6)
                                        .background(currency == cur ? FinanceColors.primary : FinanceColors.primaryContainer)
                                        .foregroundColor(currency == cur ? FinanceColors.onPrimary : FinanceColors.primary)
                                        .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                } header: {
                    Text("Валюта")
                }

                Section {
                    Picker("Категория активов", selection: $assetCategoryId) {
                        Text("Без категории").tag(String?.none)
                        ForEach(assetCategories.filter { $0.recordStatus == .active }) { cat in
                            Text(cat.name).tag(String?.some(cat.id))
                        }
                    }

                    Toggle("Счёт для оплаты", isOn: $isPaymentAccount)
                }

                if let msg = errorMessage {
                    Section {
                        Text(msg)
                            .foregroundColor(FinanceColors.error)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("Редактировать счёт")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена", action: onDismiss)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Сохранить") {
                        Task { await save() }
                    }
                    .disabled(!canSave || isLoading)
                }
            }
            .toolbar {
                ToolbarItemGroup(placement: .bottomBar) {
                    Button(role: .destructive) {
                        Task { await performArchive() }
                    } label: {
                        Label("Архивировать", systemImage: "archivebox")
                    }
                    Spacer()
                }
            }
            .onAppear {
                name = account.name
                balance = account.currentBalance
                currency = account.currency
                assetCategoryId = account.assetCategoryId
                isPaymentAccount = account.isPaymentAccount
            }
        }
    }

    private func save() async {
        let trimmedName = name.trimmingCharacters(in: .whitespaces)
        guard !trimmedName.isEmpty, let _ = Decimal(string: balance) else {
            errorMessage = "Введите название и корректный баланс"
            return
        }
        isLoading = true
        errorMessage = nil
        let request = AccountUpdateRequest(
            name: trimmedName,
            currentBalance: balance,
            currency: currency,
            accountType: nil,
            assetCategoryId: assetCategoryId,
            isPaymentAccount: isPaymentAccount,
            version: account.version
        )
        await onSave(account.id, request)
        isLoading = false
    }

    private func performArchive() async {
        isLoading = true
        await onArchive()
        isLoading = false
    }
}
