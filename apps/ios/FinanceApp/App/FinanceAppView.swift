import SwiftUI

struct FinanceAppView: View {
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let sessionDataWiper: FinanceSessionDataWiper
    let configurationError: String?

    @State private var dashboard: FinanceDashboard?
    @State private var isLoading = false
    @State private var selectedTab = 0
    @State private var message: String?
    @State private var isAuthenticated = false
    @State private var showQuickAdd = false
    @State private var quickAddError: String?
    @State private var syncOverview = LocalSyncOverview.empty
    @State private var syncResult: ManualSyncResult?
    @State private var isSyncing = false
    @State private var showSyncSheet = false

    var body: some View {
        Group {
            if !isAuthenticated {
                authView
            } else {
                mainView
            }
        }
        .task {
            await restoreSession()
        }
    }

    private var authView: some View {
        ScrollView {
            SignInCard(
                isLoading: isLoading,
                message: configurationError ?? message ?? "Войдите, чтобы увидеть финансы",
                onLogin: { email, password in
                    Task { await performLogin(email: email, password: password) }
                },
                onRegister: { email, password, confirm, displayName in
                    Task { await performRegister(email: email, password: password, confirmPassword: confirm, displayName: displayName) }
                }
            )
            .padding(16)
            .disabled(configurationError != nil)

            if isLoading {
                LoadingOverlay(message: "Обновляем данные")
                    .padding()
            }
        }
    }

    private var mainView: some View {
        NavigationStack {
            ZStack(alignment: .bottomTrailing) {
            TabView(selection: $selectedTab) {
                HomeTab(
                    dashboard: dashboard,
                    onOpenPlanning: { selectedTab = 4 },
                    syncOverview: syncOverview,
                    isSyncing: isSyncing,
                    onSyncTapped: { Task { await openSyncSheet() } }
                )
                .tabItem {
                    Image(systemName: "house")
                        .accessibilityLabel("Главная")
                }
                .tag(0)

                OperationsTab(
                    dashboard: dashboard,
                    onDeleteTransaction: { id in Task { await deleteTransaction(id) } },
                    apiClient: apiClient,
                    onRefreshDashboard: loadDashboard
                )
                .tabItem {
                    Image(systemName: "list.bullet")
                        .accessibilityLabel("Операции")
                }
                .tag(1)

                AssetsTab(
                    dashboard: dashboard,
                    apiClient: apiClient,
                    syncService: syncService,
                    localScope: currentLocalScope,
                    onRefresh: { await loadDashboard() },
                    onLocalSnapshotChanged: { await refreshLocalSnapshotAndOverview() }
                )
                .tabItem {
                    Image(systemName: "building.columns")
                        .accessibilityLabel("Активы")
                }
                .tag(2)

                CategoriesTab(
                    dashboard: dashboard,
                    apiClient: apiClient,
                    syncService: syncService,
                    localScope: currentLocalScope,
                    onRefresh: { await loadDashboard() },
                    onLocalSnapshotChanged: { await refreshLocalSnapshotAndOverview() }
                )
                .tabItem {
                    Image(systemName: "tag")
                        .accessibilityLabel("Категории расходов")
                }
                .tag(3)

                AnalyticsTab(
                    dashboard: dashboard,
                    apiClient: apiClient,
                    syncService: syncService,
                    localScope: currentLocalScope,
                    onRefresh: { await loadDashboard() },
                    onLocalSnapshotChanged: { await refreshLocalSnapshotAndOverview() }
                )
                .tabItem {
                    Image(systemName: "chart.bar")
                        .accessibilityLabel("Аналитика")
                }
                .tag(4)
            }

            Button {
                quickAddError = nil
                showQuickAdd = true
            } label: {
                Image(systemName: "plus")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .frame(width: 56, height: 56)
                    .background(FinanceColors.primary)
                    .clipShape(Circle())
                    .shadow(color: FinanceColors.primary.opacity(0.4), radius: 8, y: 4)
            }
            .padding(16)
        }
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Button {
                    Task { await openSyncSheet() }
                } label: {
                    Image(systemName: syncToolbarSymbol)
                }
                .accessibilityLabel("Синхронизация")
                .disabled(isLoading || currentLocalScope == nil)
            }

            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await performLogout() }
                } label: {
                    Image(systemName: "rectangle.portrait.and.arrow.right")
                }
                .accessibilityLabel("Выйти")
                .disabled(isLoading)
            }
        }
        }
        .sheet(isPresented: $showQuickAdd) {
            QuickAddSheet(
                dashboard: dashboard,
                errorMessage: quickAddError,
                onDismiss: { showQuickAdd = false },
                onSubmit: { draft in Task { await submitQuickAdd(draft) } }
            )
        }
        .sheet(isPresented: $showSyncSheet) {
            syncSheet
        }
        .overlay(alignment: .bottom) {
            if let msg = message, !msg.isEmpty, isAuthenticated {
                banner(msg)
            }
        }
    }

    private func placeholderTab(_ title: String) -> some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "hammer")
                .font(.system(size: 36))
                .foregroundColor(.secondary)
            Text("\(title) — в разработке")
                .font(.headline)
                .foregroundColor(.secondary)
            Text("Будет доступно в следующих версиях")
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
        }
    }

    private func banner(_ msg: String) -> some View {
        Text(msg)
            .font(.caption)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(FinanceColors.primary.opacity(0.9))
            .foregroundColor(.white)
            .clipShape(Capsule())
            .padding(.bottom, 80)
            .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    private var syncToolbarSymbol: String {
        if !syncOverview.issues.isEmpty { return "exclamationmark.triangle" }
        if syncOverview.pendingCount > 0 { return "arrow.triangle.2.circlepath" }
        return "checkmark.icloud"
    }

    private var syncSheet: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        Image(systemName: syncToolbarSymbol)
                            .foregroundColor(syncOverview.issues.isEmpty ? FinanceColors.primary : .orange)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(isSyncing ? "Синхронизация" : "Синхронизировать")
                                .font(.headline)
                            Text("Ожидает: \(syncOverview.pendingCount), проблемы: \(syncOverview.issues.count)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Button {
                            Task { await runManualSync() }
                        } label: {
                            if isSyncing {
                                ProgressView()
                            } else {
                                Image(systemName: "arrow.triangle.2.circlepath")
                            }
                        }
                        .disabled(isSyncing || currentLocalScope == nil)
                    }

                    if let lastError = syncOverview.lastError, !lastError.isEmpty {
                        Text(lastError)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                if let syncResult {
                    Section("Последний запуск") {
                        Text("Отправлено: \(syncResult.push.pushed), применено: \(syncResult.push.applied), получено: \(syncResult.pulledChanges)")
                            .font(.caption)
                        if syncResult.hasMorePullChanges {
                            Text("На сервере есть еще изменения. Запустите синхронизацию еще раз.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                if !syncOverview.issues.isEmpty {
                    Section("Проблемы") {
                        ForEach(syncOverview.issues) { issue in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text(issue.title)
                                        .font(.subheadline)
                                        .fontWeight(.semibold)
                                    Spacer()
                                    Text(syncIssueStatusTitle(issue.status))
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                                Text(issue.safeDescription)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                if issue.decision == .retryAllowed {
                                    Button {
                                        Task { await retrySyncIssue(issue) }
                                    } label: {
                                        Label("Повторить", systemImage: "arrow.clockwise")
                                    }
                                    .disabled(isSyncing)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            }
            .navigationTitle("Синхронизация")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Готово") { showSyncSheet = false }
                }
            }
        }
    }

    private func syncIssueStatusTitle(_ status: SyncIssueStatus) -> String {
        switch status {
        case .failed:
            return "Проблемы"
        case .rejected:
            return "Отклонено"
        }
    }

    private func restoreSession() async {
        guard configurationError == nil else {
            await wipeProtectedState(message: configurationError ?? "")
            return
        }
        isLoading = true
        do {
            let status = try await apiClient.sessionStatus()
            if status.isAuthenticated {
                await wipeForAccountSwitchIfNeeded(newSession: status)
                isAuthenticated = true
                await loadDashboard()
            } else {
                await wipeProtectedState(message: "Войдите, чтобы увидеть финансы")
            }
        } catch {
            await wipeProtectedState(message: "Войдите, чтобы увидеть финансы")
        }
        isLoading = false
    }

    private func performLogin(email: String, password: String) async {
        guard configurationError == nil else {
            message = configurationError
            return
        }
        guard !email.isEmpty, !password.isEmpty else {
            message = "Введите email и пароль"
            return
        }
        isLoading = true
        message = "Входим"
        do {
            let status = try await apiClient.login(email: email, password: password)
            if status.isAuthenticated {
                await wipeForAccountSwitchIfNeeded(newSession: status)
                isAuthenticated = true
                await loadDashboard()
            } else {
                message = "Не удалось войти"
            }
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func performRegister(email: String, password: String, confirmPassword: String, displayName: String) async {
        guard configurationError == nil else {
            message = configurationError
            return
        }
        let trimmedEmail = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedEmail.isEmpty else { message = "Введите email"; return }
        guard !password.isEmpty else { message = "Введите пароль"; return }
        guard !confirmPassword.isEmpty else { message = "Повторите пароль"; return }
        guard password.count >= FinanceConstants.passwordMinLength else {
            message = "Пароль должен быть не короче 12 символов"
            return
        }
        guard password == confirmPassword else { message = "Пароли не совпадают"; return }

        isLoading = true
        message = "Регистрируем аккаунт"
        do {
            let result = try await apiClient.register(
                email: email,
                password: password,
                displayName: displayName.isEmpty ? nil : displayName
            )
            switch result {
            case .authenticated(let status):
                await wipeForAccountSwitchIfNeeded(newSession: status)
                isAuthenticated = true
                await loadDashboard()
            case .accepted:
                message = "Заявка принята. Если аккаунт доступен, войдите по email и паролю."
            }
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func loadDashboard() async {
        isLoading = true
        message = "Обновляем данные"
        do {
            let yearMonth = DateHelpers.currentYearMonth()
            let boundary = DateHelpers.monthEndDate(yearMonth)
            dashboard = try await apiClient.dashboard(
                startDate: DateHelpers.monthStartDate(yearMonth),
                endDate: boundary
            )
            await refreshLocalSnapshotAndOverview()
            message = "Данные обновлены"
        } catch let error as FinanceApiError where error.isAuthError {
            await wipeProtectedState(message: "Сессия истекла. Войдите снова.")
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func performLogout() async {
        isLoading = true
        message = "Выходим"
        do {
            try await apiClient.logout()
            await wipeProtectedState(message: "Войдите, чтобы увидеть финансы")
        } catch {
            await wipeProtectedState(message: "Сессия завершена локально. \(error.localizedDescription)")
        }
        isLoading = false
    }

    private func wipeProtectedState(message: String) async {
        await wipeProtectedStores()
        dashboard = nil
        selectedTab = 0
        showQuickAdd = false
        quickAddError = nil
        showSyncSheet = false
        syncResult = nil
        syncOverview = .empty
        isAuthenticated = false
        self.message = message
    }

    private var currentLocalScope: LocalStoreScope? {
        guard let session = dashboard?.session,
              let userId = session.userId?.trimmingCharacters(in: .whitespacesAndNewlines),
              !userId.isEmpty else {
            return nil
        }
        return LocalStoreScope.fromSession(session, fallbackUserId: userId)
    }

    private func wipeForAccountSwitchIfNeeded(newSession: SessionStatus) async {
        guard let currentSession = dashboard?.session,
              currentSession.userId != newSession.userId else {
            return
        }
        await wipeProtectedStores()
    }

    private func wipeProtectedStores() async {
        do {
            if let scope = currentLocalScope {
                try await sessionDataWiper.wipeCurrentUser(scope: scope)
            } else {
                try await sessionDataWiper.wipeAllProtectedLocalData()
            }
        } catch {
            // Best-effort local privacy cleanup; auth state still has to be cleared.
        }
        CategoryAggregateMappingStore.shared.clearAll()
    }

    private func openSyncSheet() async {
        showSyncSheet = true
        await refreshSyncOverview()
    }

    private func refreshSyncOverview() async {
        guard let scope = currentLocalScope else {
            syncOverview = .empty
            return
        }
        syncOverview = await syncService.overview(scope: scope)
    }

    private func refreshLocalSnapshotAndOverview() async {
        await applyLocalSnapshotToDashboard()
        await refreshSyncOverview()
    }

    private func applyLocalSnapshotToDashboard() async {
        guard let scope = currentLocalScope, let dashboard else { return }
        do {
            let snapshot = try await syncService.localSnapshot(scope: scope)
            let mergedTransactions = mergedEntities(
                existing: dashboard.transactions,
                localRecords: snapshot.transactions,
                tombstones: snapshot.tombstones,
                entityType: .transactions
            )
            dashboard.accounts = mergedEntities(
                existing: dashboard.accounts,
                localRecords: snapshot.accounts,
                tombstones: snapshot.tombstones,
                entityType: .accounts
            ).filter { $0.ownershipType == .personal && $0.householdId == nil }
            dashboard.categories = mergedEntities(
                existing: dashboard.categories,
                localRecords: snapshot.categories,
                tombstones: snapshot.tombstones,
                entityType: .categories
            ).filter { $0.scope == .personal && $0.householdId == nil }
            dashboard.assetCategories = mergedEntities(
                existing: dashboard.assetCategories,
                localRecords: snapshot.assetCategories,
                tombstones: snapshot.tombstones,
                entityType: .assetCategories
            ).filter { $0.scopeType == .personal && $0.householdId == nil }
            let personalAccountIds = Set(dashboard.accounts.map(\.id))
            dashboard.transactions = mergedTransactions.filter { transaction in
                personalAccountIds.contains(transaction.accountId) &&
                transaction.counterpartyAccountId.map(personalAccountIds.contains) != false
            }
            dashboard.assetCategoryGroups = rebuiltAssetCategoryGroups(
                existing: dashboard.assetCategoryGroups,
                categories: dashboard.assetCategories,
                accounts: dashboard.accounts
            )
        } catch {
            syncOverview = LocalSyncOverview(
                pendingCount: syncOverview.pendingCount,
                issues: syncOverview.issues,
                lastError: SyncSafeMessage.describe(error.localizedDescription)
            )
        }
    }

    private func mergedEntities<Entity: Identifiable & Codable & Sendable>(
        existing: [Entity],
        localRecords: [LocalRecord<Entity>],
        tombstones: [SyncTombstone],
        entityType: SyncEntityType
    ) -> [Entity] where Entity.ID == String {
        let tombstonedIds = Set(tombstones
            .filter { $0.entityType == entityType }
            .map(\.entityId))
        var merged = existing.filter { !tombstonedIds.contains($0.id) }
        for entity in localRecords.map(\.entity) where !tombstonedIds.contains(entity.id) {
            if let index = merged.firstIndex(where: { $0.id == entity.id }) {
                merged[index] = entity
            } else {
                merged.append(entity)
            }
        }
        return merged
    }

    private func rebuiltAssetCategoryGroups(
        existing: [AssetCategoryGroup],
        categories: [AssetCategory],
        accounts: [Account]
    ) -> [AssetCategoryGroup] {
        var existingById: [String: AssetCategoryGroup] = [:]
        for group in existing {
            existingById[group.assetCategoryId] = group
        }
        return categories
            .filter { $0.recordStatus == .active && $0.scopeType == .personal && $0.householdId == nil }
            .map { category in
                let linked = accounts.filter {
                    $0.assetCategoryId == category.id &&
                    $0.status == .active &&
                    $0.currency == category.currency
                }
                let accountsTotal = linked.reduce(Decimal.zero) { total, account in
                    total + (Decimal(string: account.currentBalance) ?? .zero)
                }
                let manualAmount = Decimal(string: category.manualAmount) ?? .zero
                let totalAmount = accountsTotal + manualAmount
                let existingGroup = existingById[category.id]
                return AssetCategoryGroup(
                    assetCategoryId: category.id,
                    name: category.name,
                    scopeType: category.scopeType,
                    householdId: nil,
                    currency: category.currency,
                    manualAmount: category.manualAmount,
                    accountsTotal: MoneyHelpers.decimalToString(accountsTotal),
                    totalAmount: MoneyHelpers.decimalToString(totalAmount),
                    isInvestment: category.isInvestment,
                    assetType: category.assetType,
                    iconKey: category.iconKey,
                    accountCount: linked.isEmpty ? existingGroup?.accountCount : linked.count
                )
            }
    }

    private func runManualSync() async {
        guard let scope = currentLocalScope else { return }
        isSyncing = true
        syncResult = await syncService.syncNow(scope: scope)
        await refreshLocalSnapshotAndOverview()
        isSyncing = false
    }

    private func retrySyncIssue(_ issue: SyncIssue) async {
        guard issue.decision == .retryAllowed, let scope = currentLocalScope else { return }
        isSyncing = true
        do {
            try await syncService.retryIssue(scope: scope, issueId: issue.id)
            syncResult = await syncService.syncNow(scope: scope)
        } catch {
            syncOverview = LocalSyncOverview(
                pendingCount: syncOverview.pendingCount,
                issues: syncOverview.issues,
                lastError: SyncSafeMessage.describe(error.localizedDescription)
            )
        }
        await refreshSyncOverview()
        isSyncing = false
    }

    private func deleteTransaction(_ id: String) async {
        isLoading = true
        message = "Удаляем операцию"
        do {
            try await apiClient.deleteTransaction(transactionId: id)
            await loadDashboard()
            message = "Операция удалена"
        } catch where OfflineMutationFallback.canQueue(after: error) {
            if let scope = currentLocalScope {
                do {
                    try await syncService.enqueueOptimisticMutation(
                        scope: scope,
                        entityType: .transactions,
                        entityId: id,
                        operation: .delete
                    )
                    await refreshLocalSnapshotAndOverview()
                    message = "Операция удалена локально, ожидает синхронизации"
                } catch {
                    message = error.localizedDescription
                }
            } else {
                message = error.localizedDescription
            }
            isLoading = false
        } catch {
            message = error.localizedDescription
            isLoading = false
        }
    }

    private func submitQuickAdd(_ draft: QuickAddDraft) async {
        let normalizedAmount = draft.amount
        guard Decimal(string: normalizedAmount) != nil else {
            quickAddError = "Проверьте сумму"
            return
        }

        isLoading = true
        message = "Сохраняем"
        do {
            let accounts = dashboard?.accounts ?? []
            let categories = dashboard?.categories ?? []
            var queuedOffline = false

            switch draft.type {
            case .expense, .income:
                let scopedAccounts = accounts.filter { $0.status == .active && $0.ownershipType == .personal }
                let operationAccounts = draft.type == .expense
                    ? scopedAccounts.filter { $0.isPaymentAccount }
                    : scopedAccounts
                let source: Account
                if let found = operationAccounts.first(where: { $0.id == draft.accountId }) {
                    source = found
                } else if let first = operationAccounts.first {
                    source = first
                } else {
                    quickAddError = draft.type == .expense
                        ? "Нет активного счёта, отмеченного для оплаты."
                        : "Нет активного счёта."
                    isLoading = false
                    return
                }

                let scopedCategories = categories.filter { $0.scope == .personal && $0.status == .active }
                let category = scopedCategories.first { $0.id == draft.categoryId }
                if category == nil {
                    quickAddError = "Выберите категорию"
                    isLoading = false
                    return
                }

                let request = TransactionCreateRequest(
                    transactionType: draft.type.apiValue,
                    accountId: source.id,
                    counterpartyAccountId: nil,
                    categoryId: draft.categoryId.isEmpty ? nil : draft.categoryId,
                    amount: normalizedAmount,
                    currency: source.currency,
                    occurredAt: nil,
                    transactionDate: draft.transactionDate,
                    description: nil,
                    sourceType: "manual"
                )
                queuedOffline = try await createTransactionOnlineOrQueue(request)

            case .transfer, .investment:
                let scopedAccounts = accounts.filter { $0.status == .active && $0.ownershipType == .personal }
                let investmentCategoryIds = Set((dashboard?.assetCategories ?? [])
                    .filter { $0.scopeType == .personal && $0.recordStatus == .active && $0.isInvestment }
                    .map(\.id))
                let sourceCandidates = draft.type == .investment
                    ? scopedAccounts.filter(\.isPaymentAccount)
                    : scopedAccounts
                let destinationCandidates = draft.type == .investment
                    ? scopedAccounts.filter { $0.assetCategoryId.map(investmentCategoryIds.contains) == true }
                    : scopedAccounts
                guard let source = sourceCandidates.first(where: { $0.id == draft.accountId }) ?? sourceCandidates.first,
                      let dest = destinationCandidates.first(where: { $0.id == draft.destinationAccountId }),
                      source.id != dest.id,
                      source.currency == dest.currency else {
                    quickAddError = "Выберите оба счёта для перевода"
                    isLoading = false
                    return
                }
                let request = TransactionCreateRequest(
                    transactionType: .transfer,
                    accountId: source.id,
                    counterpartyAccountId: dest.id,
                    categoryId: nil,
                    amount: normalizedAmount,
                    currency: source.currency,
                    occurredAt: nil,
                    transactionDate: draft.transactionDate,
                    description: nil,
                    sourceType: "manual"
                )
                queuedOffline = try await createTransactionOnlineOrQueue(request)
            }

            showQuickAdd = false
            if queuedOffline {
                await refreshLocalSnapshotAndOverview()
                message = "Сохранено локально, ожидает синхронизации"
                isLoading = false
            } else {
                await loadDashboard()
                message = "Операция сохранена"
            }
        } catch {
            quickAddError = error.localizedDescription
            message = error.localizedDescription
            isLoading = false
        }
    }

    private func createTransactionOnlineOrQueue(_ request: TransactionCreateRequest) async throws -> Bool {
        do {
            _ = try await apiClient.createTransaction(request)
            return false
        } catch where OfflineMutationFallback.canQueue(after: error) {
            guard let scope = currentLocalScope else { throw error }
            let transaction = Transaction(
                id: "local-\(UUID().uuidString)",
                transactionType: request.transactionType,
                accountId: request.accountId,
                counterpartyAccountId: request.counterpartyAccountId,
                categoryId: request.categoryId,
                amount: request.amount,
                currency: request.currency,
                occurredAt: request.occurredAt ?? DateHelpers.nowISO(),
                transactionDate: request.transactionDate,
                description: request.description,
                sourceType: request.sourceType,
                transferScope: nil,
                transferStatus: request.transactionType == .transfer ? .posted : nil,
                version: nil
            )
            try await syncService.enqueueOptimisticMutation(
                scope: scope,
                entityType: .transactions,
                entityId: transaction.id,
                operation: .create,
                request: transaction
            )
            await refreshLocalSnapshotAndOverview()
            return true
        }
    }
}
