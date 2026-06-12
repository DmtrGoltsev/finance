import SwiftUI

struct PlanningView: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let apiClient: FinanceApiClient

    @State private var month = nextPlanningMonth()
    @State private var plan: PlanningPlan?
    @State private var history: [PlanningPlan] = []
    @State private var isLoading = false
    @State private var message: String?

    private var boundedMonth: String { coercePlanningMonth(month) }
    private var resolvedScope: PlanningScopeInfo? { selectedMode.toPlanningScope(dashboard?.session.householdId) }
    private var currency: CurrencyCode { planningCurrency(dashboard, mode: selectedMode) }

    var body: some View {
        VStack(spacing: 12) {
            PlanningScopeCard(
                selectedMode: selectedMode,
                hasHousehold: !(dashboard?.session.householdId?.isEmpty ?? true),
                month: boundedMonth,
                currency: currency,
                onModeSelected: onModeSelected,
                onMonthSelected: { month = coercePlanningMonth($0) }
            )

            if selectedMode == .overview {
                PlanningOverviewGate(onModeSelected: onModeSelected)
            } else if resolvedScope == nil {
                PlanningMessageCard(text: "Общее планирование недоступно без активного общего бюджета. Выберите Личное или подключите общий бюджет.")
            } else {
                if let msg = message, !msg.isEmpty {
                    PlanningMessageCard(text: msg)
                }

                PlanningPlanCard(
                    plan: plan,
                    month: boundedMonth,
                    currency: currency,
                    isLoading: isLoading,
                    onRefresh: { await loadPlanningState() },
                    onCreatePlan: { await createPlan() }
                )

                if let currentPlan = plan {
                    IncomeSourcesCard(
                        plan: currentPlan,
                        currency: currency,
                        isLoading: isLoading,
                        onCreate: { request in await createIncomeSource(planId: currentPlan.id, request: request) },
                        onUpdate: { source, request in await updateIncomeSource(source: source, request: request) },
                        onConfirm: { source in await confirmIncomeSource(source: source) },
                        onDelete: { source in await deleteIncomeSource(source: source) }
                    )

                    AllocationsCard(
                        plan: currentPlan,
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        isLoading: isLoading,
                        onCreate: { request in await createAllocation(planId: currentPlan.id, request: request) },
                        onUpdate: { allocation, request in await updateAllocation(allocation: allocation, request: request) },
                        onDelete: { allocation in await deleteAllocation(allocation: allocation) }
                    )
                }

                PlanningHistoryCard(
                    history: history,
                    currentMonth: boundedMonth,
                    isLoading: isLoading,
                    onCopy: { historyPlan in await copyPlan(historyPlan) }
                )
            }
        }
        .onChange(of: boundedMonth) { _, _ in Task { await loadPlanningState() } }
        .task { await loadPlanningState() }
    }

    private func loadPlanningState(successMessage: String? = nil) async {
        guard let scope = resolvedScope else { return }
        isLoading = true
        message = nil
        do {
            let fetched = try await apiClient.getPlanningPlan(scope: scope.apiScope, month: boundedMonth, householdId: scope.householdId)
            if let fetched = fetched {
                plan = try await apiClient.getPlanningPlan(planId: fetched.id)
            } else {
                plan = nil
            }
            history = (try? await apiClient.listPlanningPlanHistory(scope: scope.apiScope, householdId: scope.householdId)) ?? []
            message = successMessage
        } catch {
            message = planningErrorMessage(error)
            plan = nil
        }
        isLoading = false
    }

    private func createPlan() async {
        guard let scope = resolvedScope else { return }
        isLoading = true
        do {
            let request = PlanningPlanCreateRequest(scope: scope.apiScope, month: boundedMonth, currency: currency, householdId: scope.householdId)
            _ = try await apiClient.createPlanningPlan(request)
            await loadPlanningState(successMessage: "План создан")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func createIncomeSource(planId: String, request: PlanningIncomeSourceCreateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.createPlanningIncomeSource(planId: planId, request)
            await loadPlanningState(successMessage: "Источник дохода добавлен")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func updateIncomeSource(source: PlanningIncomeSource, request: PlanningIncomeSourceUpdateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.updatePlanningIncomeSource(incomeSourceId: source.id, request)
            await loadPlanningState(successMessage: "Источник дохода обновлён")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func confirmIncomeSource(source: PlanningIncomeSource) async {
        isLoading = true
        do {
            _ = try await apiClient.confirmPlanningIncomeSource(incomeSourceId: source.id)
            await loadPlanningState(successMessage: "Доход подтверждён")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func deleteIncomeSource(source: PlanningIncomeSource) async {
        isLoading = true
        do {
            try await apiClient.deletePlanningIncomeSource(incomeSourceId: source.id)
            await loadPlanningState(successMessage: "Источник дохода удалён")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func createAllocation(planId: String, request: PlanningAllocationCreateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.createPlanningAllocation(planId: planId, request)
            await loadPlanningState(successMessage: "Распределение добавлено")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func updateAllocation(allocation: PlanningAllocation, request: PlanningAllocationUpdateRequest) async {
        isLoading = true
        do {
            _ = try await apiClient.updatePlanningAllocation(allocationId: allocation.id, request)
            await loadPlanningState(successMessage: "Распределение обновлено")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func deleteAllocation(allocation: PlanningAllocation) async {
        isLoading = true
        do {
            try await apiClient.deletePlanningAllocation(allocationId: allocation.id)
            await loadPlanningState(successMessage: "Распределение удалено")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }

    private func copyPlan(_ historyPlan: PlanningPlan) async {
        isLoading = true
        do {
            _ = try await apiClient.copyPlanningPlan(planId: historyPlan.id, PlanningPlanCopyRequest(targetMonth: boundedMonth))
            await loadPlanningState(successMessage: "План \(localizedPlanningMonth(historyPlan.month)) скопирован на \(localizedPlanningMonth(boundedMonth))")
        } catch {
            message = planningErrorMessage(error)
            isLoading = false
        }
    }
}

private struct PlanningScopeInfo {
    let apiScope: PlanningScope
    let householdId: String?
}

private extension FinanceMode {
    func toPlanningScope(_ householdId: String?) -> PlanningScopeInfo? {
        switch self {
        case .personal: return PlanningScopeInfo(apiScope: .personal, householdId: nil)
        case .shared:
            guard let hhId = householdId, !hhId.isEmpty else { return nil }
            return PlanningScopeInfo(apiScope: .household, householdId: hhId)
        case .overview: return nil
        }
    }
}

private func planningCurrency(_ dashboard: FinanceDashboard?, mode: FinanceMode) -> CurrencyCode {
    let accounts = dashboard?.viewFor(mode).visibleAccounts ?? []
    return accounts.first?.currency
        ?? dashboard?.totals.first?.currency
        ?? .RUB
}

func nextPlanningMonth() -> String {
    let cal = Calendar.current
    let now = Date()
    guard let next = cal.date(byAdding: .month, value: 1, to: now) else { return DateHelpers.currentYearMonth() }
    let y = cal.component(.year, from: next)
    let m = cal.component(.month, from: next)
    return String(format: "%04d-%02d", y, m)
}

private func coercePlanningMonth(_ ym: String) -> String {
    let current = DateHelpers.currentYearMonth()
    let parts = ym.split(separator: "-")
    guard parts.count == 2,
          let year = Int(parts[0]),
          let month = Int(parts[1]) else { return current }
    let parsed = String(format: "%04d-%02d", year, month)
    return parsed >= current ? parsed : current
}

func localizedPlanningMonth(_ ym: String) -> String {
    DateHelpers.displayMonth(ym)
}

func localizedPlanningScope(_ scope: PlanningScope) -> String {
    switch scope {
    case .personal: return "Личное"
    case .household: return "Общее"
    }
}

func localizedTargetType(_ type: AllocationTargetType) -> String {
    switch type {
    case .expense_category: return "Расходы"
    case .investment_asset_category: return "Инвестиции"
    case .account: return "Счёт"
    case .asset: return "Актив"
    }
}

func localizedAllocationMode(_ mode: AllocationMode) -> String {
    switch mode {
    case .amount: return "Сумма"
    case .percent: return "Процент"
    }
}

func localizedRecurrenceType(_ type: AllocationRecurrenceType) -> String {
    switch type {
    case .regular: return "Регулярная"
    case .one_off: return "Разовая"
    }
}

func localizedPlanningStatus(_ status: String?) -> String {
    switch status {
    case "active", "planned", "on_track": return "по плану"
    case "confirmed", "completed", "done": return "выполнено"
    case "needs_attention", "target_attention", "warning", "attention": return "требует внимания"
    case "no_actuals": return "нет фактических данных"
    case "not_applicable": return "не применяется"
    case "under_plan", "underplanned", "behind": return "ниже плана"
    case "over_plan", "overplanned", "ahead": return "выше плана"
    default: return "ожидает данных"
    }
}

private func planningErrorMessage(_ error: Error) -> String {
    let msg = error.localizedDescription
    if msg.contains("401") { return "Сессия истекла. Войдите снова." }
    if msg.contains("403") { return "Нет доступа к планированию." }
    if msg.contains("404") { return "План для выбранного месяца ещё не создан" }
    return msg
}

struct PlanningMessageCard: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.subheadline)
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(UIColor.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct PlanningOverviewGate: View {
    let onModeSelected: (FinanceMode) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Обзор не создаёт единый план")
                .font(.headline)
            Text("Планирование работает в одном режиме. Выберите личный или общий план, чтобы не смешивать бюджеты.")
                .font(.subheadline)
                .foregroundColor(.secondary)
            HStack(spacing: 8) {
                Button("Личное") { onModeSelected(.personal) }
                    .buttonStyle(.bordered)
                    .frame(maxWidth: .infinity)
                Button("Общее") { onModeSelected(.shared) }
                    .buttonStyle(.bordered)
                    .frame(maxWidth: .infinity)
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct PlanningBanner: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption)
            .fontWeight(.medium)
            .foregroundColor(color)
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(color.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

func planningMonthChoices() -> [PlanningMonthChoice] {
    let current = DateHelpers.currentYearMonth()
    let cal = Calendar.current
    let now = Date()
    let currentY = cal.component(.year, from: now)
    let currentM = cal.component(.month, from: now)

    return (0...12).compactMap { offset -> PlanningMonthChoice? in
        var comps = DateComponents()
        comps.year = currentY
        comps.month = currentM + offset
        comps.day = 1
        guard let date = cal.date(from: comps) else { return nil }
        let y = cal.component(.year, from: date)
        let m = cal.component(.month, from: date)
        let ym = String(format: "%04d-%02d", y, m)
        let title: String
        switch offset {
        case 0: title = "Текущий: \(DateHelpers.displayMonth(ym))"
        case 1: title = "Следующий: \(DateHelpers.displayMonth(ym))"
        default: title = DateHelpers.displayMonth(ym)
        }
        return PlanningMonthChoice(month: ym, title: title)
    }
}

func planningGoalMonthChoices() -> [PlanningMonthChoice] {
    let cal = Calendar.current
    let now = Date()
    let currentY = cal.component(.year, from: now)
    let currentM = cal.component(.month, from: now)

    return (1...36).compactMap { offset -> PlanningMonthChoice? in
        var comps = DateComponents()
        comps.year = currentY
        comps.month = currentM + offset
        comps.day = 1
        guard let date = cal.date(from: comps) else { return nil }
        let y = cal.component(.year, from: date)
        let m = cal.component(.month, from: date)
        let ym = String(format: "%04d-%02d", y, m)
        let prefix: String? = {
            switch offset {
            case 1: return "Следующий"
            case 6: return "6 мес."
            case 12: return "1 год"
            case 24: return "2 года"
            case 36: return "3 года"
            default: return nil
            }
        }()
        let title = prefix.map { "\($0): \(DateHelpers.displayMonth(ym))" } ?? DateHelpers.displayMonth(ym)
        return PlanningMonthChoice(month: ym, title: title)
    }
}

struct PlanningMonthChoice: Identifiable {
    let month: String
    let title: String
    var id: String { month }
}

func normalizePlanningAmount(_ string: String) -> String? {
    let normalized = string.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
    guard !normalized.isEmpty else { return nil }
    guard let value = Decimal(string: normalized), value > .zero else { return nil }
    let ns = value as NSDecimalNumber
    let rounded = ns.rounding(accordingToBehavior: NSDecimalNumberHandler(roundingMode: .plain, scale: 2, raiseOnExactness: false, raiseOnOverflow: false, raiseOnUnderflow: false, raiseOnDivideByZero: false))
    return rounded.stringValue
}

func planningDecimalInput(_ string: String) -> String {
    string.filter { $0.isNumber || $0 == "." || $0 == "," }.replacingOccurrences(of: ",", with: ".")
}

func toPlanningDay(_ string: String) -> Int? {
    guard let day = Int(string), (1...31).contains(day) else { return nil }
    return day
}

func snapshotTitle(_ snapshot: [String: JSONValue]?) -> String? {
    guard let snapshot = snapshot, !snapshot.isEmpty else { return nil }
    for key in ["name", "title", "displayName", "label"] {
        if let val = snapshot[key]?.stringValue, !val.isEmpty {
            return val
        }
    }
    return nil
}
