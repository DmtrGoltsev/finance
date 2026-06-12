import SwiftUI

struct AssetCategoryGroupCard: View {
    let group: AssetCategoryGroup
    let accounts: [Account]
    let assetCategories: [AssetCategory]
    let onUpdateCategory: (String, AssetCategoryUpdateRequest) async -> Void
    let onArchiveCategory: (String) async -> Void
    let onUpdateAccount: (String, AccountUpdateRequest) async -> Void
    let onArchiveAccount: (String) async -> Void
    let onRestoreAccount: (String) async -> Void
    let onAddAccount: () -> Void

    @State private var isExpanded = false
    @State private var isEditing = false
    @State private var editName = ""
    @State private var editManualAmount = ""
    @State private var editIsInvestment = false
    @State private var editError: String?
    @State private var confirmArchive = false
    @State private var isLoading = false

    private var iconOption: AssetCategoryIconOption {
        AssetCategoryIcons.icon(for: group.iconKey, assetType: group.assetType)
    }

    private var subtitle: String {
        if !accounts.isEmpty {
            return "\(accounts.count) \(pluralItems(accounts.count))"
        }
        return "Ручная \(MoneyHelpers.format(group.manualAmount, currency: group.currency))"
    }

    private var isManualOnly: Bool {
        accounts.isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Button {
                withAnimation { isExpanded.toggle() }
            } label: {
                HStack(spacing: 10) {
                    ZStack(alignment: .bottomTrailing) {
                        IconBubble(systemName: iconOption.sfSymbol, color: iconOption.tint, size: 40)
                        if group.isInvestment {
                            Circle()
                                .fill(FinanceColors.investment)
                                .frame(width: 16, height: 16)
                                .overlay(
                                    Image(systemName: "chart.line.uptrend.xyaxis")
                                        .font(.system(size: 8))
                                        .foregroundColor(.white)
                                )
                        }
                    }

                    VStack(alignment: .leading, spacing: 2) {
                        Text(group.name)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .lineLimit(1)
                            .foregroundColor(.primary)
                        Text(subtitle)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    Text(MoneyHelpers.format(group.totalAmount, currency: group.currency))
                        .font(.subheadline)
                        .fontWeight(.semibold)

                    Image(systemName: "chevron.down")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.secondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
            }
            .buttonStyle(.plain)

            if isExpanded {
                VStack(spacing: 6) {
                    if accounts.isEmpty {
                        Text("Счетов в этой категории нет")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 14)
                    } else {
                        ForEach(accounts) { account in
                            VStack(spacing: 0) {
                                AccountRow(
                                    account: account,
                                    assetCategories: assetCategories,
                                    onUpdate: onUpdateAccount,
                                    onArchive: onArchiveAccount,
                                    onRestore: onRestoreAccount
                                )
                                .padding(.horizontal, 14)
                                if account.id != accounts.last?.id {
                                    Divider()
                                        .padding(.leading, 14)
                                }
                            }
                        }
                    }

                    HStack(spacing: 8) {
                        Button {
                            editName = group.name
                            editManualAmount = group.manualAmount
                            editIsInvestment = group.isInvestment
                            editError = nil
                            isEditing = true
                        } label: {
                            Label("Править", systemImage: "pencil")
                                .font(.caption)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)

                        if accounts.isEmpty {
                            Button(role: .destructive) {
                                confirmArchive = true
                            } label: {
                                Label("Архивировать", systemImage: "archivebox")
                                    .font(.caption)
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                        }

                        Spacer()

                        Button {
                            onAddAccount()
                        } label: {
                            Label("Добавить счёт", systemImage: "plus")
                                .font(.caption)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .tint(FinanceColors.primary)
                    }
                    .padding(.horizontal, 14)
                    .padding(.bottom, 8)
                }
            }
        }
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
        .alert("Править категорию", isPresented: $isEditing) {
            TextField("Название", text: $editName)
            if isManualOnly {
                TextField("Ручная сумма", text: $editManualAmount)
                    .keyboardType(.decimalPad)
            }
            Toggle("Инвестиция", isOn: $editIsInvestment)
            Button("Сохранить") {
                Task { await saveEdit() }
            }
            .disabled(editName.trimmingCharacters(in: .whitespaces).isEmpty)
            Button("Отмена", role: .cancel) {}
        } message: {
            if let err = editError {
                Text(err)
            }
        }
        .alert("Архивировать категорию?", isPresented: $confirmArchive) {
            Button("Архивировать", role: .destructive) {
                Task { await onArchiveCategory(group.assetCategoryId) }
            }
            Button("Отмена", role: .cancel) {}
        } message: {
            Text("Категория «\(group.name)» будет архивирована.")
        }
    }

    private func saveEdit() async {
        let trimmed = editName.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            editError = "Введите название"
            return
        }
        isLoading = true
        editError = nil
        let request = AssetCategoryUpdateRequest(
            name: trimmed,
            manualAmount: isManualOnly ? editManualAmount : nil,
            assetType: nil,
            iconKey: nil,
            isInvestment: editIsInvestment,
            version: nil
        )
        await onUpdateCategory(group.assetCategoryId, request)
        isLoading = false
        isEditing = false
    }
}

func pluralItems(_ count: Int) -> String {
    let absCount = abs(count)
    let mod10 = absCount % 10
    let mod100 = absCount % 100
    if mod10 == 1 && mod100 != 11 { return "счёт" }
    if mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) { return "счёта" }
    return "счетов"
}
