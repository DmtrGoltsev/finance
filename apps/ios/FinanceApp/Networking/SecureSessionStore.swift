import Foundation
import Security

protocol SessionCredentialStoring: Sendable {
    func load() throws -> BearerSessionCredentials?
    func save(_ credentials: BearerSessionCredentials) throws
    func clear() throws
}

enum SessionCredentialStoreError: Error, Equatable, Sendable {
    case keychain(OSStatus)
    case invalidData
}

final class KeychainSessionCredentialStore: SessionCredentialStoring, @unchecked Sendable {
    static let service = "com.finance.app.ios-bearer-session"
    static let account = "current-session"

    func load() throws -> BearerSessionCredentials? {
        guard let data = DeviceBoundKeychain.loadData(
            service: Self.service,
            account: Self.account
        ) else {
            return nil
        }
        do {
            return try JSONDecoder().decode(BearerSessionCredentials.self, from: data)
        } catch {
            DeviceBoundKeychain.delete(service: Self.service, account: Self.account)
            throw SessionCredentialStoreError.invalidData
        }
    }

    func save(_ credentials: BearerSessionCredentials) throws {
        let data = try JSONEncoder().encode(credentials)
        let status = DeviceBoundKeychain.saveData(
            data,
            service: Self.service,
            account: Self.account
        )
        guard status == errSecSuccess else {
            throw SessionCredentialStoreError.keychain(status)
        }
    }

    func clear() throws {
        let status = SecItemDelete([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Self.service,
            kSecAttrAccount as String: Self.account,
        ] as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SessionCredentialStoreError.keychain(status)
        }
    }
}

actor SessionCoordinator {
    private struct RefreshFlight {
        let id: UUID
        let generation: UInt64
        let task: Task<BearerSessionResponse, Error>
    }

    private let store: any SessionCredentialStoring
    private let now: @Sendable () -> Date
    private var credentials: BearerSessionCredentials?
    private var generation: UInt64 = 0
    private var refreshFlight: RefreshFlight?

    init(
        store: any SessionCredentialStoring = KeychainSessionCredentialStore(),
        now: @escaping @Sendable () -> Date = Date.init
    ) {
        self.store = store
        self.now = now
        self.credentials = try? store.load()
    }

    func install(_ response: BearerSessionResponse) throws -> SessionStatus {
        guard let newCredentials = response.credentials(validatedAt: now()) else {
            throw SessionCoordinatorError.invalidBearerResponse
        }
        do {
            try store.save(newCredentials)
        } catch {
            throw SessionCoordinatorError.credentialPersistenceFailed
        }

        refreshFlight?.task.cancel()
        refreshFlight = nil
        credentials = newCredentials
        generation &+= 1
        return response.sessionStatus
    }

    func authorizedSession() throws -> AuthorizedSession {
        guard let credentials else {
            throw FinanceApiError.unauthorized
        }
        return AuthorizedSession(
            accessToken: credentials.accessToken,
            lease: SessionLease(
                userId: credentials.userId,
                sessionId: credentials.sessionId,
                generation: generation
            )
        )
    }

    func currentLease() throws -> SessionLease {
        try authorizedSession().lease
    }

    func restoredSessionStatus() -> SessionStatus? {
        guard let credentials else { return nil }
        guard OfflineSessionRestorePolicy.canRestore(
            lastServerValidatedAt: credentials.lastServerValidatedAt,
            now: now()
        ) else {
            invalidateCredentials()
            return nil
        }
        return SessionStatus(
            isAuthenticated: true,
            displayName: "Пользователь \(credentials.userId.prefix(8))",
            householdId: nil,
            userId: credentials.userId,
            sessionId: credentials.sessionId
        )
    }

    func markServerValidated(_ status: SessionStatus) throws {
        guard let current = credentials,
              status.isAuthenticated,
              status.userId == current.userId,
              status.sessionId == current.sessionId else {
            throw SessionCoordinatorError.superseded
        }
        let validated = current.serverValidated(at: now())
        do {
            try store.save(validated)
        } catch {
            throw SessionCoordinatorError.credentialPersistenceFailed
        }
        credentials = validated
    }

    func validate(_ lease: SessionLease) throws {
        guard let credentials else {
            throw SessionCoordinatorError.superseded
        }
        guard lease.generation == generation,
              lease.userId == credentials.userId,
              lease.sessionId == credentials.sessionId else {
            throw SessionCoordinatorError.superseded
        }
    }

    func refresh(
        afterUnauthorized lease: SessionLease,
        using operation: @escaping @Sendable (String) async throws -> BearerSessionResponse
    ) async throws -> AuthorizedSession {
        if lease.generation != generation,
           credentials?.userId == lease.userId,
           credentials?.sessionId == lease.sessionId {
            return try authorizedSession()
        }
        try validate(lease)
        guard let currentCredentials = credentials else {
            throw FinanceApiError.unauthorized
        }

        let flight: RefreshFlight
        if let existing = refreshFlight, existing.generation == lease.generation {
            flight = existing
        } else {
            let id = UUID()
            let refreshToken = currentCredentials.refreshToken
            let task = Task { try await operation(refreshToken) }
            flight = RefreshFlight(id: id, generation: lease.generation, task: task)
            refreshFlight = flight
        }

        let response: BearerSessionResponse
        do {
            response = try await flight.task.value
        } catch {
            clearRefreshFlight(id: flight.id)
            if SessionRestorePolicy.isConfirmedInvalidIdentity(error),
               generation == lease.generation {
                invalidateCredentials()
            }
            throw error
        }

        guard let rotatedCredentials = response.credentials(validatedAt: now()) else {
            clearRefreshFlight(id: flight.id)
            throw SessionCoordinatorError.invalidBearerResponse
        }

        if generation == lease.generation {
            guard rotatedCredentials.userId == lease.userId,
                  rotatedCredentials.sessionId == lease.sessionId else {
                clearRefreshFlight(id: flight.id)
                throw SessionCoordinatorError.identityMismatch
            }
            do {
                try store.save(rotatedCredentials)
            } catch {
                clearRefreshFlight(id: flight.id)
                throw SessionCoordinatorError.credentialPersistenceFailed
            }
            credentials = rotatedCredentials
            generation &+= 1
        } else {
            guard credentials == rotatedCredentials else {
                clearRefreshFlight(id: flight.id)
                throw SessionCoordinatorError.superseded
            }
        }

        clearRefreshFlight(id: flight.id)
        return try authorizedSession()
    }

    func invalidateIfCurrent(_ lease: SessionLease) {
        guard generation == lease.generation,
              credentials?.userId == lease.userId,
              credentials?.sessionId == lease.sessionId else {
            return
        }
        invalidateCredentials()
    }

    func invalidateForLogout() -> LogoutAuthorization {
        let accessToken = credentials?.accessToken
        let sessionId = credentials?.sessionId
        let revokeToken = credentials?.revokeToken
        refreshFlight?.task.cancel()
        refreshFlight = nil
        credentials = nil
        generation &+= 1

        let cleared: Bool
        do {
            try store.clear()
            cleared = true
        } catch {
            cleared = false
        }
        return LogoutAuthorization(
            accessToken: accessToken,
            sessionId: sessionId,
            revokeToken: revokeToken,
            localCredentialsCleared: cleared
        )
    }

    private func invalidateCredentials() {
        refreshFlight?.task.cancel()
        refreshFlight = nil
        credentials = nil
        generation &+= 1
        try? store.clear()
    }

    private func clearRefreshFlight(id: UUID) {
        guard refreshFlight?.id == id else { return }
        refreshFlight = nil
    }
}
