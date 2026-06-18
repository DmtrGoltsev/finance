import SwiftUI

struct CategoryManagementCard: View {
    let categories: [Category]
    let hasHousehold: Bool
    let apiClient: FinanceApiClient
    let onRefresh: () async -> Void

    @State private var selectedType: CategoryType = .expense
    @State private var selectedScope: CategoryScope = .personal
    @State private var newCategoryName = ""
    @State private var showArchived = false
    @State private var message: String?
    @State private var isLoading = false

    private var activeCategories: [Category] {
        categories
            .filter { $0.type == selectedType && $0.status == .active }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    private var archivedCategories: [Category] {
        categories
            .filter { $0.type == selectedType && $0.status == .archived }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                IconBubble(systemName: "tag", color: FinanceColors.analyticsAccent, size: 36)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Категории")
                        .font(.headline)
                    Text("Добавление, список и быстрые правки")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Тип")
                    .font(.caption)
                    .foregroundColor(.secondary)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach([CategoryType.expense, .income], id: \.self) { type in
                            Button {
                                selectedType = type
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: type == .expense ? "minus.circle" : "plus.circle")
                                        .font(.system(size: 12))
                                    Text(type == .expense ? "Расходы" : "Доходы")
                                        .font(.subheadline)
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(selectedType == type ? FinanceColors.primary : FinanceColors.primaryContainer)
                                .foregroundColor(selectedType == type ? FinanceColors.onPrimary : FinanceColors.primary)
                                .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Режим")
                    .font(.caption)
                    .foregroundColor(.secondary)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        let scopes: [CategoryScope] = hasHousehold ? [.personal, .household] : [.personal]
                        ForEach(scopes, id: \.self) { scope in
                            Button {
                                selectedScope = scope
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: scope == .personal ? "person" : "person.2")
                                        .font(.system(size: 12))
                                    Text(scope == .personal ? "Личное" : "Общее")
                                        .font(.subheadline)
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(selectedScope == scope ? FinanceColors.primary : FinanceColors.primaryContainer)
                                .foregroundColor(selectedScope == scope ? FinanceColors.onPrimary : FinanceColors.primary)
                                .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }

            HStack(spacing: 8) {
                TextField("Название категории", text: $newCategoryName)
                    .textFieldStyle(.roundedBorder)

                Button {
                    Task { await addCategory() }
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(width: 32, height: 32)
                        .background(FinanceColors.primary)
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
                .disabled(newCategoryName.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)
            }

            if activeCategories.isEmpty {
                Text("Категорий пока нет")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(activeCategories) { category in
                    CategoryManagementRow(
                        category: category,
                        onUpdate: { name in await updateCategory(category, name) },
                        onArchive: { await archiveCategory(category.id) }
                    )
                }
            }

            if !archivedCategories.isEmpty {
                DisclosureGroup(isExpanded: $showArchived) {
                    ForEach(archivedCategories) { category in
                        HStack {
                            Image(systemName: categoryIcon(category))
                                .foregroundColor(.secondary)
                            Text(category.name)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            Spacer()
                            Button {
                                Task { await restoreCategory(category.id) }
                            } label: {
                                Text("Восстановить")
                                    .font(.caption)
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                        }
                        .padding(.vertical, 2)
                    }
                } label: {
                    Text("Архивированные (\(archivedCategories.count))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
    }

    private func categoryIcon(_ category: Category) -> String {
        switch category.type {
        case .expense: return "tag"
        case .income: return "plus.circle"
        }
    }

    private func addCategory() async {
        let trimmed = newCategoryName.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        isLoading = true
        do {
            _ = try await apiClient.createCategory(CategoryCreateRequest(
                name: trimmed,
                type: selectedType,
                scope: selectedScope,
                householdId: selectedScope == .household ? nil : nil,
                iconKey: nil,
                color: nil
            ))
            newCategoryName = ""
            await onRefresh()
            message = "Категория добавлена"
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func updateCategory(_ category: Category, _ newName: String) async {
        do {
            _ = try await apiClient.updateCategory(
                categoryId: category.id,
                CategoryUpdateRequest(
                    name: newName,
                    iconKey: category.iconKey,
                    color: category.color,
                    version: category.version
                )
            )
            await onRefresh()
        } catch {
            message = error.localizedDescription
        }
    }

    private func archiveCategory(_ id: String) async {
        do {
            _ = try await apiClient.archiveCategory(categoryId: id)
            await onRefresh()
        } catch {
            message = error.localizedDescription
        }
    }

    private func restoreCategory(_ id: String) async {
        do {
            _ = try await apiClient.restoreCategory(categoryId: id)
            await onRefresh()
        } catch {
            message = error.localizedDescription
        }
    }
}

private struct CategoryManagementRow: View {
    let category: Category
    let onUpdate: (String) async -> Void
    let onArchive: () async -> Void

    @State private var isEditing = false
    @State private var editName = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                IconBubble(
                    systemName: category.type == .expense ? "tag" : "plus.circle",
                    color: category.type == .expense ? FinanceColors.expense : FinanceColors.income,
                    size: 32
                )

                if isEditing {
                    TextField("Название", text: $editName)
                        .textFieldStyle(.roundedBorder)
                        .font(.subheadline)
                } else {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(category.name)
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .lineLimit(1)
                        Text("\(category.type == .expense ? "Расходы" : "Доходы")")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()

                if isEditing {
                    Button {
                        Task {
                            if !editName.trimmingCharacters(in: .whitespaces).isEmpty {
                                await onUpdate(editName.trimmingCharacters(in: .whitespaces))
                            }
                            isEditing = false
                        }
                    } label: {
                        Text("Сохранить")
                            .font(.caption)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .tint(FinanceColors.primary)
                    .disabled(editName.trimmingCharacters(in: .whitespaces).isEmpty)

                    Button(role: .destructive) {
                        Task {
                            await onArchive()
                            isEditing = false
                        }
                    } label: {
                        Image(systemName: "archivebox")
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)

                    Button {
                        isEditing = false
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 14))
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                } else {
                    Button {
                        editName = category.name
                        isEditing = true
                    } label: {
                        Image(systemName: "pencil")
                            .font(.system(size: 14))
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 6)

            if isEditing {
                Divider()
            }
        }
    }
}
