import SwiftUI

struct CategoriesTab: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let apiClient: FinanceApiClient
    let onRefresh: () async -> Void

    private var categories: [Category] {
        dashboard?.categories ?? []
    }

    private var hasHousehold: Bool {
        dashboard?.session.householdId != nil
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ModeChips(selectedMode: selectedMode, onModeSelected: onModeSelected)

                CategoryManagementCard(
                    categories: categories,
                    hasHousehold: hasHousehold,
                    apiClient: apiClient,
                    onRefresh: onRefresh
                )
            }
            .padding(16)
        }
        .refreshable {
            await onRefresh()
        }
    }
}
