import SwiftUI

struct AssetsTab: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let apiClient: FinanceApiClient
    let onRefresh: () async -> Void

    @State private var showAssetCategorySheet = false
    @State private var showAddAccountSheet = false
    @State private var addAccountCategoryId: String?
    @State private var message: String?
    @State private var isLoading = false

    private var visibleAccounts: [Account] {
        dashboard?.accountsFor(selectedMode) ?? []
    }

    private var visibleGroups: [AssetCategoryGroup] {
        let accountIds = Set(visibleAccounts.map(\.id))
        return dashboard?.assetCategoryGroups.filter { group in
            let linked = visibleAccounts.filter { $0.assetCategoryId == group.assetCategoryId }
            return !linked.isEmpty || Decimal(string: group.manualAmount) ?? .zero != .zero
        } ?? []
    }

    private var legacyAccounts: [Account] {
        visibleAccounts.filter { $0.assetCategoryId == nil && $0.status == .active }
    }

    private var assetCategories: [AssetCategory] {
        dashboard?.assetCategories ?? []
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ModeChips(selectedMode: selectedMode, onModeSelected: onModeSelected)

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
                householdId: dashboard?.session.householdId,
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
                householdId: dashboard?.session.householdId,
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
        } catch {
            message = error.localizedDescription
        }
    }

    private func archiveAssetCategory(_ id: String) async {
        do {
            _ = try await apiClient.archiveAssetCategory(assetCategoryId: id)
            await onRefresh()
            message = "Категория архивирована"
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
        } catch {
            message = error.localizedDescription
        }
    }

    private func archiveAccount(_ id: String) async {
        do {
            _ = try await apiClient.archiveAccount(accountId: id)
            await onRefresh()
            message = "Счёт архивирован"
        } catch {
            message = error.localizedDescription
        }
    }

    private func restoreAccount(_ id: String) async {
        do {
            _ = try await apiClient.restoreAccount(accountId: id)
            await onRefresh()
            message = "Счёт восстановлен"
        } catch {
            message = error.localizedDescription
        }
    }
}
