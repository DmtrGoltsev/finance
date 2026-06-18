import SwiftUI

struct AnalyticsTab: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let apiClient: FinanceApiClient
    let onRefresh: () async -> Void

    @State private var selectedSubsection: AnalyticsSubsection = .summary
    @State private var reportMonth = DateHelpers.currentYearMonth()
    @State private var reportSummary: ReportSummary?
    @State private var categoryBreakdown: ReportCategoryBreakdown?
    @State private var accountBalances: ReportAccountBalances?
    @State private var isLoadingReport = false

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ModeChips(selectedMode: selectedMode, onModeSelected: onModeSelected)

                AnalyticsSubsectionPicker(selected: $selectedSubsection)

                switch selectedSubsection {
                case .summary:
                    summaryContent
                case .planning:
                    PlanningView(
                        dashboard: dashboard,
                        selectedMode: selectedMode,
                        onModeSelected: onModeSelected,
                        apiClient: apiClient
                    )
                }
            }
            .padding(16)
        }
        .onChange(of: selectedSubsection) { _, newSub in
            if newSub == .summary { Task { await loadReport() } }
        }
        .onChange(of: reportMonth) { _, _ in Task { await loadReport() } }
        .task {
            await loadReport()
        }
    }

    private var summaryContent: some View {
        VStack(spacing: 12) {
            ReportMonthSwitcher(yearMonth: $reportMonth)

            if isLoadingReport {
                ProgressView("Загружаем отчёт...")
            } else {
                let currency = dashboard?.viewFor(selectedMode).primaryCurrency ?? .RUB

                AnalyticsSummaryCard(
                    totals: reportSummary?.totalsByCurrency ?? dashboard?.totals ?? [],
                    investmentAmount: investmentAmount(for: currency),
                    currency: currency
                )

                CategoryBreakdownCard(
                    transactions: dashboard?.viewFor(selectedMode).visibleTransactions ?? [],
                    categories: dashboard?.categories ?? [],
                    currency: currency
                )

                CapitalBreakdownCard(
                    groups: dashboard?.assetCategoryGroups ?? [],
                    currency: currency
                )
            }
        }
    }

    private func loadReport() async {
        guard let mode = reportMode else { return }
        isLoadingReport = true
        defer { isLoadingReport = false }
        do {
            let hhId = householdId
            let tz = TimeZone.current.identifier
            async let summary = apiClient.getReportSummary(
                reportMode: mode, householdId: hhId,
                startDate: DateHelpers.monthStartDate(reportMonth),
                endDate: DateHelpers.monthEndDate(reportMonth),
                timezone: tz,
                accountIds: nil, categoryIds: nil, transactionTypes: nil, currency: nil
            )
            async let breakdown = apiClient.getReportCategoryBreakdown(
                reportMode: mode, householdId: hhId,
                startDate: DateHelpers.monthStartDate(reportMonth),
                endDate: DateHelpers.monthEndDate(reportMonth),
                timezone: tz,
                accountIds: nil, categoryIds: nil, transactionTypes: nil, currency: nil
            )
            async let balances = apiClient.getReportAccountBalances(
                reportMode: mode, householdId: hhId,
                startDate: DateHelpers.monthStartDate(reportMonth),
                endDate: DateHelpers.monthEndDate(reportMonth),
                timezone: tz,
                accountIds: nil, currency: nil
            )
            reportSummary = try await summary
            categoryBreakdown = try await breakdown
            accountBalances = try await balances
        } catch {
            reportSummary = nil
        }
    }

    private var reportMode: ReportMode? {
        switch selectedMode {
        case .personal: return .personal
        case .shared: return .shared_family_report
        case .overview: return .combined_viewer_overview
        }
    }

    private var householdId: String? {
        selectedMode == .shared ? dashboard?.session.householdId : nil
    }

    private func investmentAmount(for currency: CurrencyCode) -> String {
        if let amount = dashboard?.investmentsByCurrency.first(where: { $0.currency == currency })?.amount {
            return amount
        }
        if let total = dashboard?.investmentsTotal, total.currency == currency {
            return total.amount
        }
        if let amount = reportSummary?.totalsByCurrency.first(where: { $0.currency == currency })?.investmentsTotal {
            return amount
        }
        return "0"
    }
}

enum AnalyticsSubsection: String, CaseIterable {
    case summary, planning

    var title: String {
        switch self {
        case .summary: return "Сводка"
        case .planning: return "План месяца"
        }
    }
}

struct AnalyticsSubsectionPicker: View {
    @Binding var selected: AnalyticsSubsection

    var body: some View {
        HStack(spacing: 0) {
            ForEach(AnalyticsSubsection.allCases, id: \.self) { tab in
                Button {
                    selected = tab
                } label: {
                    Text(tab.title)
                        .font(.subheadline)
                        .fontWeight(selected == tab ? .semibold : .regular)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 16)
                        .background(selected == tab ? FinanceColors.primary : Color.clear)
                        .foregroundColor(selected == tab ? .white : .primary)
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
    }
}
