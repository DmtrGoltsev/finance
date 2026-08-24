import SwiftUI

struct AddAccountSheet: View {
    let assetCategoryId: String?
    let assetCategories: [AssetCategory]
    let onDismiss: () -> Void
    let onCreate: (AccountCreateRequest) async -> Void

    @State private var name = ""
    @State private var initialBalance = "0"
    @State private var currency: CurrencyCode = .RUB
    @State private var accountType: AccountType = .bank
    @State private var selectedAssetCategoryId: String?
    @State private var isPaymentAccount = false
    @State private var isLoading = false
    @State private var errorMessage: String?

    private var canCreate: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && Decimal(string: initialBalance) != nil
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Название", text: $name)
                    TextField("Начальный баланс", text: $initialBalance)
                        .keyboardType(.decimalPad)
                } header: {
                    Text("Новый счёт")
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
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(AccountType.allCases, id: \.self) { type in
                                Button {
                                    accountType = type
                                } label: {
                                    HStack(spacing: 4) {
                                        Image(systemName: type.sfSymbol)
                                            .font(.system(size: 11))
                                        Text(type.title)
                                            .font(.caption)
                                    }
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .background(accountType == type ? FinanceColors.primary : FinanceColors.primaryContainer)
                                    .foregroundColor(accountType == type ? FinanceColors.onPrimary : FinanceColors.primary)
                                    .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                } header: {
                    Text("Тип счёта")
                }

                Section {
                    Picker("Категория активов", selection: $selectedAssetCategoryId) {
                        Text("Без категории").tag(String?.none)
                        ForEach(assetCategories.filter { $0.recordStatus == .active && $0.scopeType == .personal }) { cat in
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
            .navigationTitle("Новый счёт")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена", action: onDismiss)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Создать") {
                        Task { await create() }
                    }
                    .disabled(!canCreate || isLoading)
                }
            }
            .onAppear {
                selectedAssetCategoryId = assetCategoryId
            }
        }
    }

    private func create() async {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            errorMessage = "Введите название"
            return
        }
        isLoading = true
        errorMessage = nil
        let request = AccountCreateRequest(
            name: trimmed,
            accountType: accountType,
            ownershipType: .personal,
            householdId: nil,
            assetCategoryId: selectedAssetCategoryId,
            currency: currency,
            initialBalance: initialBalance,
            isPaymentAccount: isPaymentAccount
        )
        await onCreate(request)
        isLoading = false
    }
}
