import SwiftUI

struct AssetsTab: View {
    let dashboard: FinanceDashboard?
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let localScope: LocalStoreScope?
    let onRefresh: () async -> Void
    let onLocalSnapshotChanged: () async -> Void

    @State private var showAssetCategorySheet = false
    @State private var showAddAccountSheet = false
    @State private var addAccountCategoryId: String?
    @State private var message: String?
    @State private var isLoading = false

    private var visibleAccounts: [Account] {
        dashboard?.personalAccounts ?? []
    }

    private var visibleGroups: [AssetCategoryGroup] {
        let accountIds = Set(visibleAccounts.map(\.id))
        return dashboard?.assetCategoryGroups.filter { group in
            let linked = visibleAccounts.filter { $0.assetCategoryId == group.assetCategoryId }
            return group.scopeType == .personal && (!linked.isEmpty || Decimal(string: group.manualAmount) ?? .zero != .zero)
        } ?? []
    }

    private var legacyAccounts: [Account] {
        visibleAccounts.filter { $0.assetCategoryId == nil && $0.status == .active }
    }

    private var assetCategories: [AssetCategory] {
        dashboard?.assetCategories.filter { $0.scopeType == .personal } ?? []
    }

    private var viewerUserId: String? {
        localScope?.viewerUserId
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Button {
                    showAssetCategorySheet = true
                } label: {
                    Label("Добавить категорию активов", systemImage: "plus.circle")
                        .font(.subheadline)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .tint(FinanceColors.primary)

                if visibleGroups.isEmpty && legacyAccounts.isEmpty {
                    EmptyState(text: "Нет категорий активов. Добавьте первую категорию.")
                } else {
                    ForEach(visibleGroups) { group in
                        AssetCategoryGroupCard(
                            group: group,
                            accounts: visibleAccounts.filter {
                                $0.assetCategoryId == group.assetCategoryId && $0.status == .active
                            },
                            assetCategories: assetCategories,
                            onUpdateCategory: { id, req in await updateAssetCategory(id, req) },
                            onArchiveCategory: { id in await archiveAssetCategory(id) },
                            onUpdateAccount: { id, req in await updateAccount(id, req) },
                            onArchiveAccount: { id in await archiveAccount(id) },
                            onRestoreAccount: { id in await restoreAccount(id) },
                            onAddAccount: {
                                addAccountCategoryId = group.assetCategoryId
                                showAddAccountSheet = true
                            }
                        )
                    }

                    if !legacyAccounts.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(spacing: 10) {
                                IconBubble(systemName: "tray.full", color: .secondary, size: 36)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Без категории")
                                        .font(.headline)
                                    Text("\(legacyAccounts.count) \(pluralItems(legacyAccounts.count)) без привязки")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.horizontal, 14)
                            .padding(.top, 12)

                            ForEach(legacyAccounts) { account in
                                AccountRow(
                                    account: account,
                                    assetCategories: assetCategories,
                                    onUpdate: { id, req in await updateAccount(id, req) },
                                    onArchive: { id in await archiveAccount(id) },
                                    onRestore: { id in await restoreAccount(id) }
                                )
                                .padding(.horizontal, 14)
                            }

                            Text("Привяжите счета к категории активов для удобного учёта")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 14)
                                .padding(.bottom, 8)
                        }
                        .background(FinanceColors.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
                    }

                    InvestmentsCard(
                        investmentsTotal: dashboard?.investmentsTotal,
                        investmentsByCurrency: dashboard?.investmentsByCurrency ?? []
                    )
                }
            }
            .padding(16)
        }
        .refreshable {
            await onRefresh()
        }
        .sheet(isPresented: $showAssetCategorySheet) {
            AssetCategorySheet(
                onDismiss: { showAssetCategorySheet = false },
                onCreate: { request in
                    await createAssetCategory(request)
                    showAssetCategorySheet = false
                }
            )
        }
        .sheet(isPresented: $showAddAccountSheet) {
            AddAccountSheet(
                assetCategoryId: addAccountCategoryId,
                assetCategories: assetCategories,
                onDismiss: {
                    showAddAccountSheet = false
                    addAccountCategoryId = nil
                },
                onCreate: { request in
                    await createAccount(request)
                    showAddAccountSheet = false
                }
            )
        }
        .overlay(alignment: .bottom) {
            if let msg = message, !msg.isEmpty {
                Text(msg)
                    .font(.caption)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(FinanceColors.primary.opacity(0.9))
                    .foregroundColor(.white)
                    .clipShape(Capsule())
                    .padding(.bottom, 8)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
    }

    private func createAssetCategory(_ request: AssetCategoryCreateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.createAssetCategory(request)
            await onRefresh()
            message = "Категория создана"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let category = localAssetCategory(from: request)
                try await enqueueOptimistic(entityType: .assetCategories, entityId: category.id, operation: .create, payload: category)
                await onLocalSnapshotChanged()
                message = "Категория создана локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func updateAssetCategory(_ id: String, _ request: AssetCategoryUpdateRequest) async {
        do {
            _ = try await apiClient.updateAssetCategory(assetCategoryId: id, request)
            await onRefresh()
            message = "Категория обновлена"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                guard let current = assetCategories.first(where: { $0.id == id }) else { throw LocalOptimisticError.missingCurrentEntity }
                let category = updatedAssetCategory(current, request: request)
                try await enqueueOptimistic(entityType: .assetCategories, entityId: id, operation: .update, baseVersion: current.version, payload: category)
                await onLocalSnapshotChanged()
                message = "Категория обновлена локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func archiveAssetCategory(_ id: String) async {
        do {
            _ = try await apiClient.archiveAssetCategory(assetCategoryId: id)
            await onRefresh()
            message = "Категория архивирована"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let version = assetCategories.first(where: { $0.id == id })?.version
                try await enqueueOptimistic(entityType: .assetCategories, entityId: id, operation: .archive, baseVersion: version, payload: Optional<AssetCategory>.none)
                await onLocalSnapshotChanged()
                message = "Категория архивирована локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func createAccount(_ request: AccountCreateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.createAccount(request)
            await onRefresh()
            message = "Счёт создан"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let account = localAccount(from: request)
                try await enqueueOptimistic(entityType: .accounts, entityId: account.id, operation: .create, payload: account)
                await onLocalSnapshotChanged()
                message = "Счёт создан локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func updateAccount(_ id: String, _ request: AccountUpdateRequest) async {
        do {
            _ = try await apiClient.updateAccount(accountId: id, request)
            await onRefresh()
            message = "Счёт обновлён"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                guard let current = visibleAccounts.first(where: { $0.id == id }) ?? dashboard?.accounts.first(where: { $0.id == id }) else {
                    throw LocalOptimisticError.missingCurrentEntity
                }
                let account = updatedAccount(current, request: request)
                try await enqueueOptimistic(entityType: .accounts, entityId: id, operation: .update, baseVersion: current.version, payload: account)
                await onLocalSnapshotChanged()
                message = "Счёт обновлён локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func archiveAccount(_ id: String) async {
        do {
            _ = try await apiClient.archiveAccount(accountId: id)
            await onRefresh()
            message = "Счёт архивирован"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                let version = dashboard?.accounts.first(where: { $0.id == id })?.version
                try await enqueueOptimistic(entityType: .accounts, entityId: id, operation: .archive, baseVersion: version, payload: Optional<Account>.none)
                await onLocalSnapshotChanged()
                message = "Счёт архивирован локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func restoreAccount(_ id: String) async {
        do {
            _ = try await apiClient.restoreAccount(accountId: id)
            await onRefresh()
            message = "Счёт восстановлен"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            do {
                guard let current = dashboard?.accounts.first(where: { $0.id == id }) else { throw LocalOptimisticError.missingCurrentEntity }
                let account = Account(
                    id: current.id,
                    name: current.name,
                    accountType: current.accountType,
                    ownershipType: .personal,
                    ownerUserId: current.ownerUserId,
                    householdId: nil,
                    assetCategoryId: current.assetCategoryId,
                    currency: current.currency,
                    initialBalance: current.initialBalance,
                    currentBalance: current.currentBalance,
                    isPaymentAccount: current.isPaymentAccount,
                    status: .active,
                    version: current.version
                )
                try await enqueueOptimistic(entityType: .accounts, entityId: id, operation: .restore, baseVersion: current.version, payload: account)
                await onLocalSnapshotChanged()
                message = "Счёт восстановлен локально, ожидает синхронизации"
            } catch {
                message = error.localizedDescription
            }
        } catch {
            message = error.localizedDescription
        }
    }

    private func enqueueOptimistic<T: Encodable>(
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: T?
    ) async throws {
        guard let localScope else { throw LocalOptimisticError.missingLocalScope }
        if let payload {
            try await syncService.enqueueOptimisticMutation(scope: localScope, entityType: entityType, entityId: entityId, operation: operation, baseVersion: baseVersion, request: payload)
        } else {
            try await syncService.enqueueOptimisticMutation(scope: localScope, entityType: entityType, entityId: entityId, operation: operation, baseVersion: baseVersion)
        }
    }

    private func localAssetCategory(from request: AssetCategoryCreateRequest) -> AssetCategory {
        AssetCategory(
            id: "local-\(UUID().uuidString)",
            name: request.name,
            scopeType: .personal,
            ownerUserId: viewerUserId,
            householdId: nil,
            currency: request.currency,
            assetType: request.assetType ?? .bank,
            iconKey: request.iconKey,
            manualAmount: request.manualAmount ?? "0",
            isInvestment: request.isInvestment ?? false,
            recordStatus: .active,
            version: nil
        )
    }

    private func updatedAssetCategory(_ current: AssetCategory, request: AssetCategoryUpdateRequest) -> AssetCategory {
        AssetCategory(
            id: current.id,
            name: request.name ?? current.name,
            scopeType: .personal,
            ownerUserId: current.ownerUserId,
            householdId: nil,
            currency: current.currency,
            assetType: request.assetType ?? current.assetType,
            iconKey: request.iconKey ?? current.iconKey,
            manualAmount: request.manualAmount ?? current.manualAmount,
            isInvestment: request.isInvestment ?? current.isInvestment,
            recordStatus: current.recordStatus,
            version: current.version
        )
    }

    private func localAccount(from request: AccountCreateRequest) -> Account {
        Account(
            id: "local-\(UUID().uuidString)",
            name: request.name,
            accountType: request.accountType,
            ownershipType: .personal,
            ownerUserId: viewerUserId,
            householdId: nil,
            assetCategoryId: request.assetCategoryId,
            currency: request.currency,
            initialBalance: request.initialBalance,
            currentBalance: request.initialBalance,
            isPaymentAccount: request.isPaymentAccount ?? false,
            status: .active,
            version: nil
        )
    }

    private func updatedAccount(_ current: Account, request: AccountUpdateRequest) -> Account {
        Account(
            id: current.id,
            name: request.name ?? current.name,
            accountType: request.accountType ?? current.accountType,
            ownershipType: .personal,
            ownerUserId: current.ownerUserId,
            householdId: nil,
            assetCategoryId: request.assetCategoryId,
            currency: request.currency ?? current.currency,
            initialBalance: current.initialBalance,
            currentBalance: request.currentBalance ?? current.currentBalance,
            isPaymentAccount: request.isPaymentAccount ?? current.isPaymentAccount,
            status: current.status,
            version: current.version
        )
    }
}
