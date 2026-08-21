import SwiftUI

struct AssetCategorySheet: View {
    let onDismiss: () -> Void
    let onCreate: (AssetCategoryCreateRequest) async -> Void

    @State private var name = ""
    @State private var currency: CurrencyCode = .RUB
    @State private var assetType: AccountType = .bank
    @State private var manualAmount = "0"
    @State private var isInvestment = false
    @State private var iconKey = "wallet"
    @State private var isLoading = false
    @State private var errorMessage: String?

    private var canCreate: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && Decimal(string: manualAmount) != nil
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Название", text: $name)
                } header: {
                    Text("Новая категория активов")
                }

                Section {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(AccountType.allCases, id: \.self) { type in
                                Button {
                                    assetType = type
                                    iconKey = AssetCategoryIcons.icon(for: nil, assetType: type).key
                                } label: {
                                    HStack(spacing: 4) {
                                        Image(systemName: type.sfSymbol)
                                            .font(.system(size: 12))
                                        Text(type.title)
                                            .font(.caption)
                                    }
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .background(assetType == type ? FinanceColors.primary : FinanceColors.primaryContainer)
                                    .foregroundColor(assetType == type ? FinanceColors.onPrimary : FinanceColors.primary)
                                    .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                } header: {
                    Text("Тип актива")
                }

                Section {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(AssetCategoryIcons.options) { option in
                                Button {
                                    iconKey = option.key
                                } label: {
                                    Image(systemName: option.sfSymbol)
                                        .font(.system(size: 18))
                                        .foregroundColor(iconKey == option.key ? option.tint : .secondary)
                                        .frame(width: 40, height: 40)
                                        .background(iconKey == option.key ? option.tint.opacity(0.15) : Color.gray.opacity(0.08))
                                        .clipShape(Circle())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                } header: {
                    Text("Иконка")
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

                    TextField("Ручная сумма", text: $manualAmount)
                        .keyboardType(.decimalPad)

                    Toggle("Инвестиционная категория", isOn: $isInvestment)
                }

                if let msg = errorMessage {
                    Section {
                        Text(msg)
                            .foregroundColor(FinanceColors.error)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("Категория активов")
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
        let request = AssetCategoryCreateRequest(
            name: trimmed,
            scopeType: .personal,
            householdId: nil,
            currency: currency,
            assetType: assetType,
            iconKey: iconKey,
            manualAmount: manualAmount,
            isInvestment: isInvestment
        )
        await onCreate(request)
        isLoading = false
    }
}
