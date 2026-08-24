import SwiftUI

struct ScreenshotAggregateDraftList: View {
    let drafts: [ScreenshotAggregateDraftUi]
    let categories: [Category]
    let isLoading: Bool
    let onCategorySelected: (String, String) -> Void
    let onIncludedChanged: (String, Bool) -> Void
    let onCreateCategory: (String, String) -> Void
    let onConfirm: () -> Void
    let onClear: () -> Void

    private var expenseCategories: [Category] {
        categories
            .filter { $0.status == .active && $0.type == .expense && !$0.id.isEmpty }
            .sorted { $0.name < $1.name }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Категории на скриншоте")
                .font(.headline)

            ForEach(drafts) { draft in
                aggregateRow(draft)
            }

            HStack(spacing: 8) {
                Button {
                    onClear()
                } label: {
                    Text("Отмена")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(isLoading)

                Button {
                    onConfirm()
                } label: {
                    Text("Создать \(selectedCount)")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(isLoading || selectedCount == 0)
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

    private var selectedCount: Int {
        drafts.filter { $0.include && !$0.selectedCategoryId.isEmpty }.count
    }

    @ViewBuilder
    private func aggregateRow(_ draft: ScreenshotAggregateDraftUi) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(draft.candidate.externalLabel)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .lineLimit(2)
                    Text("\(draft.candidate.operationCount) операций")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Text("-\(MoneyHelpers.formatShort(draft.candidate.amount, currency: draft.candidate.currency)) \(MoneyHelpers.currencySymbol(draft.candidate.currency))")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(FinanceColors.expense)
            }

            HStack(spacing: 8) {
                Button {
                    onIncludedChanged(draft.candidate.idempotencyKey, !draft.include)
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: draft.include ? "checkmark.circle.fill" : "circle")
                            .foregroundColor(draft.include ? FinanceColors.primary : .secondary)
                        Text(draft.include ? "Включено" : "Пропустить")
                            .font(.caption)
                    }
                }
                .disabled(isLoading)

                let matched = expenseCategories.first(where: { $0.id == draft.selectedCategoryId })
                if matched == nil && !draft.candidate.externalLabel.isEmpty {
                    Button {
                        onCreateCategory(draft.candidate.idempotencyKey, draft.candidate.externalLabel)
                    } label: {
                        Text("Новая")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .buttonStyle(.bordered)
                    .disabled(isLoading)
                }
            }

            SearchableCategoryPickerControl(
                title: "Категория",
                emptyMessage: "Нет активных категорий расходов",
                categories: expenseCategories,
                selectedCategoryId: draft.selectedCategoryId,
                isDisabled: isLoading,
                onSelected: { onCategorySelected(draft.candidate.idempotencyKey, $0) }
            )
        }
    }
}
