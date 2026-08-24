import SwiftUI

struct CategoriesTab: View {
    let dashboard: FinanceDashboard?
    let apiClient: FinanceApiClient
    let syncService: FinanceSyncService
    let localScope: LocalStoreScope?
    let onRefresh: () async -> Void
    let onLocalSnapshotChanged: () async -> Void

    private var categories: [Category] {
        dashboard?.categories ?? []
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                CategoryManagementCard(
                    categories: categories,
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
