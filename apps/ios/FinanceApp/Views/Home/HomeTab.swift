import SwiftUI

struct HomeTab: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let onOpenPlanning: () -> Void

    var body: some View {
        let view = dashboard?.viewFor(selectedMode)

        ScrollView {
            VStack(spacing: 12) {
                ModeChips(selectedMode: selectedMode, onModeSelected: onModeSelected)

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
