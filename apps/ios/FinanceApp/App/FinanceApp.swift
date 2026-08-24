import SwiftUI

actor AuthBoundSyncSessionLeaseProvider: SyncSessionLeaseProvider {
    private let authLeaseProvider: any FinanceSessionLeaseProvider
    private var activeLease: SyncSessionLease?

    init(authLeaseProvider: any FinanceSessionLeaseProvider) {
        self.authLeaseProvider = authLeaseProvider
    }

    @discardableResult
    func activate(session: SessionStatus) async throws -> SyncSessionLease {
        let authLease = try await authLeaseProvider.currentSessionLease()
        guard session.isAuthenticated,
              session.userId == authLease.userId,
              session.sessionId == authLease.sessionId else {
            throw SessionCoordinatorError.identityMismatch
        }
        let lease = SyncSessionLease(
            viewerUserId: authLease.userId,
            sessionId: authLease.sessionId,
            generation: authLease.generation
        )
        activeLease = lease
        return lease
    }

    func invalidate() {
        activeLease = nil
    }

    func currentLease(for viewerUserId: String) async -> SyncSessionLease? {
        guard let activeLease, activeLease.viewerUserId == viewerUserId,
              await validatesAgainstAuth(activeLease) else {
            return nil
        }
        return activeLease
    }

    func isCurrent(_ lease: SyncSessionLease) async -> Bool {
        guard activeLease == lease else { return false }
        return await validatesAgainstAuth(lease)
    }

    private func validatesAgainstAuth(_ lease: SyncSessionLease) async -> Bool {
        guard let sessionId = lease.sessionId else { return false }
        do {
            try await authLeaseProvider.validateSessionLease(
                SessionLease(
                    userId: lease.viewerUserId,
                    sessionId: sessionId,
                    generation: lease.generation
                )
            )
            return true
        } catch {
            return false
        }
    }
}

@main
struct FinanceApp: App {
    private let environment: AppEnvironment
    private let sessionCoordinator: SessionCoordinator
    private let apiClient: LiveApiClient
    private let localStore: SwiftDataFinanceLocalStore
    private let syncLeaseProvider: AuthBoundSyncSessionLeaseProvider
    private let syncService: FinanceSyncService

    init() {
        let environment = AppEnvironment.current
        let sessionCoordinator = SessionCoordinator()
        let apiClient = LiveApiClient(
            environment: environment,
            sessionCoordinator: sessionCoordinator
        )
        let localStore: SwiftDataFinanceLocalStore
        do {
            localStore = try SwiftDataFinanceLocalStore.live()
        } catch {
            fatalError("Unable to initialize the protected finance database: \(error)")
        }
        let syncLeaseProvider = AuthBoundSyncSessionLeaseProvider(authLeaseProvider: apiClient)

        self.environment = environment
        self.sessionCoordinator = sessionCoordinator
        self.apiClient = apiClient
        self.localStore = localStore
        self.syncLeaseProvider = syncLeaseProvider
        self.syncService = FinanceSyncService(
            apiClient: apiClient,
            localStore: localStore,
            leaseProvider: syncLeaseProvider
        )
    }

    var body: some Scene {
        WindowGroup {
            FinanceAppView(
                apiClient: apiClient,
                syncService: syncService,
                syncLeaseProvider: syncLeaseProvider,
                sessionDataWiper: FinanceSessionDataWiper(localStore: localStore),
                configurationError: environment.configurationError
            )
        }
    }
}
