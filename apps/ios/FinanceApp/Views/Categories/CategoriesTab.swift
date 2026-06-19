import SwiftUI

struct CategoriesTab: View {
    let dashboard: FinanceDashboard?
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let localScope: LocalStoreScope?
    let onRefresh: () async -> Void
    let onLocalSnapshotChanged: () async -> Void

    private var categories: [Category] {
        dashboard?.categories ?? []
    }

    private var hasHousehold: Bool {
        dashboard?.session.householdId != nil
    }

    private var householdId: String? {
        dashboard?.session.householdId
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ModeChips(selectedMode: selectedMode, onModeSelected: onModeSelected)

                CategoryManagementCard(
                    categories: categories,
                    hasHousehold: hasHousehold,
                    householdId: householdId,
                    apiClient: apiClient,
                    syncService: syncService,
                    localScope: localScope,
                    onRefresh: onRefresh,
                    onLocalSnapshotChanged: onLocalSnapshotChanged
                )
            }
            .padding(16)
        }
        .refreshable {
            await onRefresh()
        }
    }
}
