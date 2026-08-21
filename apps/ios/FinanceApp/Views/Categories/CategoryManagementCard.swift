import SwiftUI

struct CategoryManagementCard: View {
    let categories: [Category]
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let localScope: LocalStoreScope?
    let onRefresh: () async -> Void
    let onLocalSnapshotChanged: () async -> Void

    @State private var newCategoryName = ""
    @State private var showArchived = false
    @State private var message: String?
    @State private var isLoading = false

    private var activeCategories: [Category] {
        categories
            .filter { $0.type == .expense && $0.scope == .personal && $0.status == .active }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    private var archivedCategories: [Category] {
        categories
            .filter { $0.type == .expense && $0.scope == .personal && $0.status == .archived }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                IconBubble(systemName: "tag", color: FinanceColors.analyticsAccent, size: 36)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Категории расходов")
                        .font(.headline)
                    Text("Добавление, список и быстрые правки")
                        .font(.caption)
                        .foregroundColor(.secondary)
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
        let request = CategoryCreateRequest(
            name: trimmed,
            type: .expense,
            scope: .personal,
            householdId: nil,
            iconKey: nil,
            color: nil
        )
        do {
            _ = try await apiClient.createCategory(request)
            newCategoryName = ""
            await onRefresh()
            message = "Категория добавлена"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let category = localCategory(from: request)
                try await enqueueOptimistic(entityId: category.id, operation: .create, payload: category)
                newCategoryName = ""
                await onLocalSnapshotChanged()
                message = "Категория добавлена локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func updateCategory(_ category: Category, _ newName: String) async {
        let request = CategoryUpdateRequest(
            name: newName,
            iconKey: category.iconKey,
            color: category.color,
            version: category.version
        )
        do {
            _ = try await apiClient.updateCategory(categoryId: category.id, request)
            await onRefresh()
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let updated = Category(
                    id: category.id,
                    name: newName,
                    type: category.type,
                    scope: category.scope,
                    ownerUserId: category.ownerUserId,
                    householdId: category.householdId,
                    iconKey: category.iconKey,
                    color: category.color,
                    status: category.status,
                    version: category.version
                )
                try await enqueueOptimistic(entityId: category.id, operation: .update, baseVersion: category.version, payload: updated)
                await onLocalSnapshotChanged()
                message = "Категория обновлена локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func archiveCategory(_ id: String) async {
        do {
            _ = try await apiClient.archiveCategory(categoryId: id)
            await onRefresh()
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let version = categories.first(where: { $0.id == id })?.version
                try await enqueueOptimistic(entityId: id, operation: .archive, baseVersion: version, payload: Optional<Category>.none)
                await onLocalSnapshotChanged()
                message = "Категория архивирована локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func restoreCategory(_ id: String) async {
        do {
            _ = try await apiClient.restoreCategory(categoryId: id)
            await onRefresh()
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                guard let category = categories.first(where: { $0.id == id }) else { throw LocalOptimisticError.missingCurrentEntity }
                let restored = Category(
                    id: category.id,
                    name: category.name,
                    type: category.type,
                    scope: category.scope,
                    ownerUserId: category.ownerUserId,
                    householdId: category.householdId,
                    iconKey: category.iconKey,
                    color: category.color,
                    status: .active,
                    version: category.version
                )
                try await enqueueOptimistic(entityId: id, operation: .restore, baseVersion: category.version, payload: restored)
                await onLocalSnapshotChanged()
                message = "Категория восстановлена локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func enqueueOptimistic<T: Encodable>(
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: T?
    ) async throws {
        guard let localScope else { throw LocalOptimisticError.missingLocalScope }
        if let payload {
            try await syncService.enqueueOptimisticMutation(
                scope: localScope,
                entityType: .categories,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                request: payload
            )
        } else {
            try await syncService.enqueueOptimisticMutation(
                scope: localScope,
                entityType: .categories,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion
            )
        }
    }

    private func localCategory(from request: CategoryCreateRequest) -> Category {
        Category(
            id: "local-\(UUID().uuidString)",
            name: request.name,
            type: request.type,
            scope: request.scope,
            ownerUserId: localScope?.viewerUserId,
            householdId: nil,
            iconKey: request.iconKey,
            color: request.color,
            status: .active,
            version: nil
        )
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
