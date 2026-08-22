import SwiftUI

struct AnalyticsTab: View {
    let dashboard: FinanceDashboard?
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let localScope: LocalStoreScope?
    let onRefresh: () async -> Void
    let onLocalSnapshotChanged: () async -> Void

    @State private var selectedSubsection: AnalyticsSubsection = .summary
    @State private var reportMonth = DateHelpers.currentYearMonth()
    @State private var reportSummary: ReportSummary?
    @State private var categoryBreakdown: ReportCategoryBreakdown?
    @State private var accountBalances: ReportAccountBalances?
    @State private var isLoadingReport = false

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                AnalyticsSubsectionPicker(selected: $selectedSubsection)

                switch selectedSubsection {
                case .summary:
                    summaryContent
                case .planning:
                    PlanningView(
                        dashboard: dashboard,
                        apiClient: apiClient,
                        syncService: syncService,
                        localScope: localScope,
                        onLocalSnapshotChanged: onLocalSnapshotChanged
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
                let currency = dashboard?.personalView().primaryCurrency ?? .RUB
                let overlay = dashboard?.pendingMonthlyOverlay(yearMonth: reportMonth, currency: currency) ?? .empty
                let selectedMonthTransactions = (dashboard?.personalTransactions ?? []).filter {
                    $0.belongs(toYearMonth: reportMonth)
                }
                let totals = reportSummary?.totalsByCurrency
                    ?? (reportMonth == DateHelpers.currentYearMonth() ? dashboard?.totals ?? [] : [])

                AnalyticsSummaryCard(
                    totals: totals,
                    pendingOverlay: overlay,
                    currency: currency
                )

                CategoryBreakdownCard(
                    breakdown: categoryBreakdown,
                    transactions: selectedMonthTransactions,
                    categories: dashboard?.categories.filter { $0.scope == .personal } ?? [],
                    currency: currency
                )

                CapitalBreakdownCard(
                    groups: accountBalances?.assetCategoryGroups ?? dashboard?.assetCategoryGroups ?? [],
                    currency: currency
                )
            }
        }
    }

    private func loadReport() async {
        isLoadingReport = true
        defer { isLoadingReport = false }
        do {
            let tz = TimeZone.current.identifier
            async let summary = apiClient.getReportSummary(
                reportMode: .personal, householdId: nil,
                startDate: DateHelpers.monthStartDate(reportMonth),
                endDate: DateHelpers.monthEndDate(reportMonth),
                timezone: tz,
                accountIds: nil, categoryIds: nil, transactionTypes: nil, currency: nil
            )
            async let breakdown = apiClient.getReportCategoryBreakdown(
                reportMode: .personal, householdId: nil,
                startDate: DateHelpers.monthStartDate(reportMonth),
                endDate: DateHelpers.monthEndDate(reportMonth),
                timezone: tz,
                accountIds: nil, categoryIds: nil, transactionTypes: nil, currency: nil
            )
            async let balances = apiClient.getReportAccountBalances(
                reportMode: .personal, householdId: nil,
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
            categoryBreakdown = nil
            accountBalances = nil
        }
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
