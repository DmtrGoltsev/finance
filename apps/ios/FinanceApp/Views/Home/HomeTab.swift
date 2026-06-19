import SwiftUI

struct HomeTab: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let onOpenPlanning: () -> Void
    let syncOverview: LocalSyncOverview
    let isSyncing: Bool
    let onSyncTapped: () -> Void

    var body: some View {
        let view = dashboard?.viewFor(selectedMode)

        ScrollView {
            VStack(spacing: 12) {
                ModeChips(selectedMode: selectedMode, onModeSelected: onModeSelected)
                SyncStatusRow(
                    overview: syncOverview,
                    isSyncing: isSyncing,
                    onTap: onSyncTapped
                )

                if let v = view {
                    PlanningEntryCard(selectedMode: selectedMode, onOpenPlanning: onOpenPlanning)
                    CapitalCard(view: v)
                    AssetChips(summaries: v.assetSummaries)
                    MonthExpenseCard(view: v)
                    TopCategoriesCard(categories: v.topCategories)
                    RecentOperationsCard(
                        transactions: v.recentTransactions,
                        categories: dashboard?.categories ?? []
                    )
                } else {
                    LoadingOverlay(message: "Загружаем данные")
                }
            }
            .padding(16)
        }
        .refreshable {
            // Pull-to-refresh handled by parent
        }
    }
}

struct SyncStatusRow: View {
    let overview: LocalSyncOverview
    let isSyncing: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .foregroundColor(iconColor)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.caption)
                        .fontWeight(.semibold)
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                if isSyncing {
                    ProgressView()
                } else {
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(FinanceColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private var title: String {
        if isSyncing { return "Синхронизация" }
        if !overview.issues.isEmpty { return "Проблемы синхронизации" }
        if overview.pendingCount > 0 { return "Ожидает синхронизации" }
        return "Готово"
    }

    private var subtitle: String {
        if !overview.issues.isEmpty {
            return "Проблемы: \(overview.issues.count)"
        }
        if overview.pendingCount > 0 {
            return "Локальные изменения ожидают: \(overview.pendingCount)"
        }
        return "Можно синхронизировать вручную"
    }

    private var symbol: String {
        if !overview.issues.isEmpty { return "exclamationmark.triangle" }
        if overview.pendingCount > 0 { return "arrow.triangle.2.circlepath" }
        return "checkmark.icloud"
    }

    private var iconColor: Color {
        if !overview.issues.isEmpty { return .orange }
        return FinanceColors.primary
    }
}

struct AssetChips: View {
    let summaries: [FinanceDashboard.AssetSummary]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                let displaySummaries = summaries.filter { $0.count > 0 }.isEmpty
                    ? Array(summaries.prefix(3))
                    : summaries.filter { $0.count > 0 }
                ForEach(displaySummaries, id: \.accountType) { summary in
                    HStack(spacing: 4) {
                        Image(systemName: summary.sfSymbol)
                            .font(.system(size: 12))
                        Text("\(summary.title) \(MoneyHelpers.format(summary.balance, currency: summary.currency))")
                            .font(.caption)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(FinanceColors.surface)
                    .clipShape(Capsule())
                    .overlay(
                        Capsule()
                            .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
                    )
                }
            }
        }
    }
}
