import SwiftUI

struct SearchableCategoryPickerButton: View {
    let title: String
    let emptyMessage: String
    let categories: [Category]
    @Binding var selectedCategoryId: String

    @State private var isPresented = false

    private var selectedCategory: Category? {
        categories.first { $0.id == selectedCategoryId }
    }

    var body: some View {
        SearchableCategoryPickerControl(
            title: title,
            emptyMessage: emptyMessage,
            categories: categories,
            selectedCategoryId: selectedCategoryId,
            isDisabled: false,
            onSelected: { selectedCategoryId = $0 }
        )
    }
}

struct SearchableCategoryPickerControl: View {
    let title: String
    let emptyMessage: String
    let categories: [Category]
    let selectedCategoryId: String
    let isDisabled: Bool
    let onSelected: (String) -> Void

    @State private var isPresented = false

    private var selectedCategory: Category? {
        categories.first { $0.id == selectedCategoryId }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .fontWeight(.medium)
            if categories.isEmpty {
                Text(emptyMessage)
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Button { isPresented = true } label: {
                    HStack {
                        Image(systemName: "tag")
                        Text(selectedCategory?.name ?? "Выбрать категорию")
                            .lineLimit(1)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .background(Color(UIColor.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)
                .disabled(isDisabled)
                .sheet(isPresented: $isPresented) {
                    SearchableCategoryPickerSheet(
                        categories: categories,
                        selectedCategoryId: selectedCategoryId,
                        onSelected: {
                            onSelected($0)
                            isPresented = false
                        },
                        isPresented: $isPresented
                    )
                }
            }
        }
    }
}

private struct SearchableCategoryPickerSheet: View {
    let categories: [Category]
    let selectedCategoryId: String
    let onSelected: (String) -> Void
    @Binding var isPresented: Bool
    @State private var query = ""

    private var filteredCategories: [Category] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        let sorted = categories.sorted {
            $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending
        }
        guard !trimmed.isEmpty else { return sorted }
        return sorted.filter { $0.name.localizedCaseInsensitiveContains(trimmed) }
    }

    var body: some View {
        NavigationStack {
            List(filteredCategories) { category in
                Button {
                    onSelected(category.id)
                } label: {
                    HStack {
                        Text(category.name)
                            .foregroundColor(.primary)
                        Spacer()
                        if selectedCategoryId == category.id {
                            Image(systemName: "checkmark")
                                .foregroundColor(FinanceColors.primary)
                        }
                    }
                }
                .buttonStyle(.plain)
            }
            .searchable(text: $query, prompt: "Поиск категории")
            .navigationTitle("Категория")
            .navigationBarTitleDisplayMode(.inline)
            .overlay {
                if filteredCategories.isEmpty {
                    ContentUnavailableView.search(text: query)
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена") { isPresented = false }
                }
            }
        }
    }
}
