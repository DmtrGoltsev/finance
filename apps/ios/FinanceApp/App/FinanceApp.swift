import SwiftUI

@main
struct FinanceApp: App {
    private let environment: AppEnvironment
    private let apiClient: LiveApiClient
    private let localStore: FileBackedFinanceLocalStore
    private let syncService: FinanceSyncService

    init() {
        let environment = AppEnvironment.current
        let apiClient = LiveApiClient(environment: environment)
        self.environment = environment
        let localStore = FileBackedFinanceLocalStore()
        self.apiClient = apiClient
        self.localStore = localStore
        self.syncService = FinanceSyncService(apiClient: apiClient, localStore: localStore)
    }

    var body: some Scene {
        WindowGroup {
            FinanceAppView(
                apiClient: apiClient,
                syncService: syncService,
                sessionDataWiper: FinanceSessionDataWiper(localStore: localStore),
                configurationError: environment.configurationError
            )
        }
    }
}
