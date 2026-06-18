import SwiftUI

struct AccountRow: View {
    let account: Account
    let assetCategories: [AssetCategory]
    let onUpdate: (String, AccountUpdateRequest) async -> Void
    let onArchive: (String) async -> Void
    let onRestore: (String) async -> Void

    @State private var isEditing = false

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(account.name)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(1)
                    if account.isPaymentAccount {
                        Text("Оплата")
                            .font(.caption2)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(FinanceColors.planningPrimary.opacity(0.15))
                            .foregroundColor(FinanceColors.planningPrimary)
                            .clipShape(Capsule())
                    }
                }
                Text(MoneyHelpers.format(account.currentBalance, currency: account.currency))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Button {
                isEditing = true
            } label: {
                Image(systemName: "pencil")
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)

            if account.status == .active {
                Button {
                    Task { await onArchive(account.id) }
                } label: {
                    Image(systemName: "archivebox")
                        .font(.system(size: 14))
                        .foregroundColor(FinanceColors.expense)
                }
                .buttonStyle(.plain)
            } else if account.status == .archived {
                Button {
                    Task { await onRestore(account.id) }
                } label: {
                    Image(systemName: "arrow.uturn.backward")
                        .font(.system(size: 14))
                        .foregroundColor(FinanceColors.income)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, 4)
        .sheet(isPresented: $isEditing) {
            AccountEditDialog(
                account: account,
                assetCategories: assetCategories,
                onSave: { accountId, request in
                    await onUpdate(accountId, request)
                    isEditing = false
                },
                onArchive: {
                    await onArchive(account.id)
                    isEditing = false
                },
                onDismiss: { isEditing = false }
            )
        }
    }
}
