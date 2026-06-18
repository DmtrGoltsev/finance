import SwiftUI

struct TransactionRow: View {
    let transaction: Transaction
    let categories: [Category]
    let onDelete: () -> Void
    let onEdit: (() -> Void)?

    init(transaction: Transaction, categories: [Category], onDelete: @escaping () -> Void, onEdit: (() -> Void)? = nil) {
        self.transaction = transaction
        self.categories = categories
        self.onDelete = onDelete
        self.onEdit = onEdit
    }

    var body: some View {
        HStack(spacing: 12) {
            IconBubble(systemName: transaction.sfSymbol, color: transaction.tintColor)

            VStack(alignment: .leading, spacing: 2) {
                Text(transaction.displayDescription(categories: categories))
                    .font(.body)
                    .fontWeight(.medium)
                    .lineLimit(1)
                Text("\(DateHelpers.displayDate(transaction.sortDateKey)) \u{2022} \(transaction.displayDescription(categories: categories))")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            MoneyText(
                amount: transaction.amount,
                currency: transaction.currency,
                type: transaction.transactionType,
                font: .body,
                showSign: true
            )

            Menu {
                Button {
                    onEdit?()
                } label: {
                    Label("Редактировать", systemImage: "pencil")
                }
                Button(role: .destructive) {
                    onDelete()
                } label: {
                    Label("Удалить", systemImage: "trash")
                }
            } label: {
                Image(systemName: "ellipsis")
                    .foregroundColor(.secondary)
                    .padding(4)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .shadow(color: .black.opacity(0.03), radius: 3, y: 1)
        .contextMenu {
            Button {
                onEdit?()
            } label: {
                Label("Редактировать", systemImage: "pencil")
            }
            Button(role: .destructive) {
                onDelete()
            } label: {
                Label("Удалить", systemImage: "trash")
            }
        }
    }
}
