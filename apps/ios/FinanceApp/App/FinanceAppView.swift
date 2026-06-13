import SwiftUI

struct FinanceAppView: View {
    let apiClient: FinanceApiClient

    @State private var dashboard: FinanceDashboard?
    @State private var isLoading = false
    @State private var selectedTab = 0
    @State private var selectedMode: FinanceMode = .personal
    @State private var message: String?
    @State private var isAuthenticated = false
    @State private var showQuickAdd = false
    @State private var quickAddError: String?

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
                message: message ?? "Войдите, чтобы увидеть финансы",
                onLogin: { email, password in
                    Task { await performLogin(email: email, password: password) }
                },
                onRegister: { email, password, confirm, displayName in
                    Task { await performRegister(email: email, password: password, confirmPassword: confirm, displayName: displayName) }
                }
            )
            .padding(16)

            if isLoading {
                LoadingOverlay(message: "Обновляем данные")
                    .padding()
            }
        }
    }

    private var mainView: some View {
        ZStack(alignment: .bottomTrailing) {
            TabView(selection: $selectedTab) {
                Tab("Главная", systemImage: "house", value: 0) {
                    HomeTab(
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        onModeSelected: { selectedMode = $0 },
                        onOpenPlanning: { selectedTab = 4 }
                    )
                }
                Tab("Операции", systemImage: "list.bullet", value: 1) {
                    OperationsTab(
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        onModeSelected: { selectedMode = $0 },
                        onDeleteTransaction: { id in Task { await deleteTransaction(id) } },
                        apiClient: apiClient,
                        householdId: dashboard?.session.householdId,
                        onRefreshDashboard: loadDashboard
                    )
                }
                Tab("Активы", systemImage: "building.columns", value: 2) {
                    AssetsTab(
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        onModeSelected: { selectedMode = $0 },
                        apiClient: apiClient,
                        onRefresh: { await loadDashboard() }
                    )
                }
                Tab("Категории", systemImage: "tag", value: 3) {
                    CategoriesTab(
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        onModeSelected: { selectedMode = $0 },
                        apiClient: apiClient,
                        onRefresh: { await loadDashboard() }
                    )
                }
                Tab("Аналитика", systemImage: "chart.bar", value: 4) {
                    AnalyticsTab(
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        onModeSelected: { selectedMode = $0 },
                        apiClient: apiClient,
                        onRefresh: { await loadDashboard() }
                    )
                }
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
        .sheet(isPresented: $showQuickAdd) {
            QuickAddSheet(
                dashboard: dashboard,
                selectedMode: selectedMode,
                errorMessage: quickAddError,
                onDismiss: { showQuickAdd = false },
                onSubmit: { draft in Task { await submitQuickAdd(draft) } }
            )
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

    private func restoreSession() async {
        isLoading = true
        do {
            let status = try await apiClient.sessionStatus()
            if status.isAuthenticated {
                isAuthenticated = true
                await loadDashboard()
            } else {
                message = "Войдите, чтобы увидеть финансы"
            }
        } catch {
            message = "Войдите, чтобы увидеть финансы"
        }
        isLoading = false
    }

    private func performLogin(email: String, password: String) async {
        guard !email.isEmpty, !password.isEmpty else {
            message = "Введите email и пароль"
            return
        }
        isLoading = true
        message = "Входим"
        do {
            let status = try await apiClient.login(email: email, password: password)
            if status.isAuthenticated {
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
            case .authenticated:
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
            message = "Данные обновлены"
        } catch let error as FinanceApiError where error.isAuthError {
            isAuthenticated = false
            message = "Сессия истекла. Войдите снова."
        } catch {
            message = error.localizedDescription
        }
        isLoading = false
    }

    private func deleteTransaction(_ id: String) async {
        isLoading = true
        message = "Удаляем операцию"
        do {
            try await apiClient.deleteTransaction(transactionId: id)
            await loadDashboard()
            message = "Операция удалена"
        } catch {
            message = error.localizedDescription
            isLoading = false
        }
    }

    private func submitQuickAdd(_ draft: QuickAddDraft) async {
        guard draft.visibility != .overview else {
            quickAddError = "Мой обзор только показывает видимые вам данные. Выберите Личное или Общее перед сохранением."
            return
        }
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

            switch draft.type {
            case .expense, .income:
                let scopedAccounts = accounts
                    .filteredByMode(draft.visibility, householdId: dashboard?.session.householdId)
                let source: Account
                if let found = scopedAccounts.first(where: { $0.id == draft.accountId }) {
                    source = found
                } else if let first = scopedAccounts.first {
                    source = first
                } else {
                    quickAddError = "В режиме \(draft.visibility.title) нет активного счёта."
                    isLoading = false
                    return
                }

                let scopedCategories = categories.filteredByMode(draft.visibility, householdId: dashboard?.session.householdId)
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
                    occurredAt: DateHelpers.nowISO(),
                    transactionDate: draft.transactionDate,
                    description: nil,
                    sourceType: "manual"
                )
                _ = try await apiClient.createTransaction(request)

            case .transfer:
                let scopedAccounts = accounts
                    .filteredByMode(draft.visibility, householdId: dashboard?.session.householdId)
                guard let source = scopedAccounts.first(where: { $0.id == draft.accountId }) ?? scopedAccounts.first,
                      let dest = scopedAccounts.first(where: { $0.id == draft.destinationAccountId }) else {
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
                    occurredAt: DateHelpers.nowISO(),
                    transactionDate: draft.transactionDate,
                    description: nil,
                    sourceType: "manual"
                )
                _ = try await apiClient.createTransaction(request)
            }

            showQuickAdd = false
            await loadDashboard()
            message = "Сохранено в \(draft.visibility.title.lowercased())"
        } catch {
            quickAddError = error.localizedDescription
            message = error.localizedDescription
            isLoading = false
        }
    }
}
