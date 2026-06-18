import SwiftUI

struct TopCategoriesCard: View {
    let categories: [FinanceDashboard.CategorySpend]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Топ категории")
                .font(.headline)

            if categories.isEmpty {
                Text("В выбранном scope расходов пока нет. Добавьте расход или переключитесь на другой scope.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(categories.prefix(3), id: \.categoryId) { category in
                    categoryRow(category)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
    }

    private func categoryRow(_ category: FinanceDashboard.CategorySpend) -> some View {
        HStack(spacing: 10) {
            IconBubble(systemName: category.sfSymbol, color: category.color, size: 34)
            Text(category.name)
                .font(.body)
                .lineLimit(1)
            Spacer()
            Text(MoneyHelpers.format(category.amount, currency: category.currency))
                .font(.body)
                .fontWeight(.medium)
        }
    }
}
