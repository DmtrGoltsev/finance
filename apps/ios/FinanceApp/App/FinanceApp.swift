import SwiftUI

@main
struct FinanceApp: App {
    private let apiClient: LiveApiClient = {
        LiveApiClient()
    }()

    var body: some Scene {
        WindowGroup {
            FinanceAppView(apiClient: apiClient)
        }
    }
}
