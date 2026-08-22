import Foundation
import XCTest
@testable import FinanceApp

final class SecureSessionTests: XCTestCase {
    override func tearDown() {
        SecureSessionURLProtocol.reset()
        super.tearDown()
    }

    func testLoginUsesIOSBearerAndPersistsRotatableTokensWithoutPassword() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        SecureSessionURLProtocol.configure { request in
            XCTAssertEqual(request.url?.path, "/finance-api/api/v1/sessions")
            let body = try XCTUnwrap(request.httpBody)
            let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: String])
            XCTAssertEqual(json["transport"], "ios_bearer")
            XCTAssertEqual(json["deviceName"], "iPhone")
            XCTAssertEqual(json["email"], "owner@example.test")
            XCTAssertEqual(json["password"], "correct horse battery staple")
            return .json(statusCode: 201, body: self.bearerJSON())
        }

        let client = makeClient(coordinator: coordinator)
        let status = try await client.login(
            email: " owner@example.test ",
            password: "correct horse battery staple"
        )

        XCTAssertTrue(status.isAuthenticated)
        XCTAssertEqual(status.userId, "user-a")
        XCTAssertEqual(status.sessionId, "session-a")
        let stored = try XCTUnwrap(store.credentials)
        XCTAssertEqual(stored.accessToken, "access-a")
        XCTAssertEqual(stored.refreshToken, "refresh-a")
        XCTAssertFalse(String(decoding: try JSONEncoder().encode(stored), as: UTF8.self)
            .contains("correct horse battery staple"))
    }

    func testRegistrationUsesIOSBearerAndInstallsSession() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        SecureSessionURLProtocol.configure { request in
            let body = try XCTUnwrap(request.httpBody)
            let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: String])
            XCTAssertEqual(json["transport"], "ios_bearer")
            XCTAssertEqual(json["displayName"], "Owner")
            return .json(statusCode: 201, body: self.bearerJSON())
        }

        let result = try await makeClient(coordinator: coordinator).register(
            email: "owner@example.test",
            password: "correct horse battery staple",
            displayName: "Owner"
        )

        guard case .authenticated(let status) = result else {
            return XCTFail("Expected authenticated registration")
        }
        XCTAssertEqual(status.userId, "user-a")
        XCTAssertEqual(store.credentials?.refreshToken, "refresh-a")
    }

    func testConcurrent401ResponsesUseOneRefreshAndRetryEachRequestOnce() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let state = RequestCountState()

        SecureSessionURLProtocol.configure { request in
            switch request.url?.path {
            case "/finance-api/api/v1/sessions/current":
                let call = state.recordCurrent(
                    authorization: request.value(forHTTPHeaderField: "Authorization")
                )
                if call <= 2 {
                    return .json(statusCode: 401, body: self.errorJSON(code: "UNAUTHORIZED"))
                }
                return .json(statusCode: 200, body: self.currentSessionJSON())
            case "/finance-api/api/v1/sessions/refresh":
                state.recordRefresh()
                Thread.sleep(forTimeInterval: 0.1)
                return .json(
                    statusCode: 200,
                    body: self.bearerJSON(access: "access-b", refresh: "refresh-b")
                )
            default:
                return .json(statusCode: 404, body: "{}")
            }
        }

        let client = makeClient(coordinator: coordinator)
        async let first = client.sessionStatus()
        async let second = client.sessionStatus()
        let (firstStatus, secondStatus) = try await (first, second)
        let statuses = [firstStatus, secondStatus]

        XCTAssertEqual(statuses.compactMap(\.userId), ["user-a", "user-a"])
        XCTAssertEqual(state.refreshCalls, 1)
        XCTAssertEqual(state.currentCalls, 4)
        XCTAssertEqual(state.authorizations.filter { $0 == "Bearer access-a" }.count, 2)
        XCTAssertEqual(state.authorizations.filter { $0 == "Bearer access-b" }.count, 2)
        XCTAssertEqual(store.credentials?.refreshToken, "refresh-b")
        XCTAssertEqual(store.saveCalls, 2)
    }

    func testRotationIsPersistedAsOneCredentialBlobBeforeGenerationAdvances() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let oldLease = try await coordinator.currentLease()

        let authorized = try await coordinator.refresh(afterUnauthorized: oldLease) { _ in
            self.bearer(access: "access-b", refresh: "refresh-b")
        }

        XCTAssertEqual(store.credentials?.accessToken, "access-b")
        XCTAssertEqual(store.credentials?.refreshToken, "refresh-b")
        XCTAssertEqual(store.saveCalls, 2)
        XCTAssertGreaterThan(authorized.lease.generation, oldLease.generation)
        XCTAssertEqual(authorized.lease.userId, oldLease.userId)
        XCTAssertEqual(authorized.lease.sessionId, oldLease.sessionId)
    }

    func test403DoesNotClearCredentialsOrInvalidateLease() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let lease = try await coordinator.currentLease()
        SecureSessionURLProtocol.configure { _ in
            .json(statusCode: 403, body: self.errorJSON(code: "FORBIDDEN"))
        }

        do {
            _ = try await makeClient(coordinator: coordinator).sessionStatus()
            XCTFail("Expected forbidden")
        } catch let error as FinanceApiError {
            guard case .httpError(let statusCode, _) = error else {
                return XCTFail("Expected httpError, got \(error)")
            }
            XCTAssertEqual(statusCode, 403)
        }

        let currentLease = try await coordinator.currentLease()
        XCTAssertEqual(currentLease, lease)
        XCTAssertEqual(store.credentials?.refreshToken, "refresh-a")
    }

    func testRefresh5xxAndNetworkFailureKeepLocalSession() async throws {
        for refreshOutcome in [
            SecureSessionURLProtocol.Outcome.json(
                statusCode: 503,
                body: errorJSON(code: "UNAVAILABLE")
            ),
            .failure(URLError(.notConnectedToInternet)),
        ] {
            let store = MemorySessionCredentialStore()
            let coordinator = SessionCoordinator(store: store)
            _ = try await coordinator.install(bearer())
            let lease = try await coordinator.currentLease()
            SecureSessionURLProtocol.configure { request in
                if request.url?.path.hasSuffix("/sessions/refresh") == true {
                    return refreshOutcome
                }
                return .json(statusCode: 401, body: self.errorJSON(code: "UNAUTHORIZED"))
            }

            do {
                _ = try await makeClient(coordinator: coordinator).sessionStatus()
                XCTFail("Expected refresh failure")
            } catch {
                // The important invariant is preserved credentials, not the presentation error.
            }

            let currentLease = try await coordinator.currentLease()
            XCTAssertEqual(currentLease, lease)
            XCTAssertEqual(store.credentials?.refreshToken, "refresh-a")
        }
    }

    func testOfflineLogoutClearsCredentialsAndInvalidatesExistingLease() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let lease = try await coordinator.currentLease()
        SecureSessionURLProtocol.configure { _ in
            .failure(URLError(.notConnectedToInternet))
        }

        let result = await makeClient(coordinator: coordinator).logout()

        XCTAssertFalse(result.remoteSessionRevoked)
        XCTAssertTrue(result.localCredentialsCleared)
        XCTAssertNil(store.credentials)
        do {
            try await coordinator.validate(lease)
            XCTFail("Expected invalidated lease")
        } catch let error as SessionCoordinatorError {
            XCTAssertEqual(error, .superseded)
        }
    }

    func testStaleRefreshCannotOverwriteNewAccountSession() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let leaseA = try await coordinator.currentLease()

        let staleRefresh = Task {
            try await coordinator.refresh(afterUnauthorized: leaseA) { _ in
                try? await Task.sleep(nanoseconds: 150_000_000)
                return self.bearer(access: "stale-a", refresh: "stale-refresh-a")
            }
        }
        try await Task.sleep(nanoseconds: 20_000_000)
        _ = try await coordinator.install(bearer(
            access: "access-user-b",
            refresh: "refresh-user-b",
            userId: "user-b",
            sessionId: "session-b"
        ))

        do {
            _ = try await staleRefresh.value
            XCTFail("Expected stale refresh rejection")
        } catch {
            // Cancellation or superseded are both safe: neither can install A over B.
        }
        let leaseB = try await coordinator.currentLease()
        XCTAssertEqual(leaseB.userId, "user-b")
        XCTAssertEqual(leaseB.sessionId, "session-b")
        XCTAssertEqual(store.credentials?.accessToken, "access-user-b")
    }

    func testSecond401AfterRefreshIsNotRetriedAndClearsCurrentSession() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let state = RequestCountState()
        SecureSessionURLProtocol.configure { request in
            if request.url?.path.hasSuffix("/sessions/refresh") == true {
                state.recordRefresh()
                return .json(
                    statusCode: 200,
                    body: self.bearerJSON(access: "access-b", refresh: "refresh-b")
                )
            }
            _ = state.recordCurrent(
                authorization: request.value(forHTTPHeaderField: "Authorization")
            )
            return .json(statusCode: 401, body: self.errorJSON(code: "UNAUTHORIZED"))
        }

        do {
            _ = try await makeClient(coordinator: coordinator).sessionStatus()
            XCTFail("Expected unauthorized")
        } catch {
            XCTAssertTrue(SessionRestorePolicy.isConfirmedInvalidIdentity(error))
        }

        XCTAssertEqual(state.currentCalls, 2)
        XCTAssertEqual(state.refreshCalls, 1)
        XCTAssertNil(store.credentials)
    }

    func testOCRUsesSameBearerTransportAnd403DoesNotRefresh() async throws {
        let store = MemorySessionCredentialStore()
        let coordinator = SessionCoordinator(store: store)
        _ = try await coordinator.install(bearer())
        let state = RequestCountState()
        SecureSessionURLProtocol.configure { request in
            state.recordOCR(
                authorization: request.value(forHTTPHeaderField: "Authorization"),
                contentType: request.value(forHTTPHeaderField: "Content-Type")
            )
            return .json(statusCode: 403, body: self.errorJSON(code: "FORBIDDEN"))
        }

        do {
            _ = try await makeClient(coordinator: coordinator).screenshotOcr(
                imageData: Data([0x01, 0x02]),
                contentType: "image/png",
                capturedAt: "2026-08-22T10:00:00.000Z",
                householdId: nil
            )
            XCTFail("Expected forbidden")
        } catch {
            // OCR remains an online request and shares the authenticated transport.
        }

        XCTAssertEqual(state.ocrAuthorization, "Bearer access-a")
        XCTAssertTrue(state.ocrContentType?.hasPrefix("multipart/form-data;") == true)
        XCTAssertEqual(state.refreshCalls, 0)
        XCTAssertNotNil(store.credentials)
    }

    private func makeClient(coordinator: SessionCoordinator) -> LiveApiClient {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [SecureSessionURLProtocol.self]
        return LiveApiClient(
            baseURL: "https://finance-security-tests.invalid/finance-api",
            tokenStore: CSRFTokenStore(),
            session: URLSession(configuration: configuration),
            sessionCoordinator: coordinator
        )
    }

    private func bearer(
        access: String = "access-a",
        refresh: String = "refresh-a",
        userId: String = "user-a",
        sessionId: String = "session-a"
    ) -> BearerSessionResponse {
        BearerSessionResponse(
            tokenType: "Bearer",
            accessToken: access,
            refreshToken: refresh,
            expiresAt: "2026-08-22T11:00:00.000Z",
            actor: ActorContext(userId: userId, sessionId: sessionId, memberships: [])
        )
    }

    private func bearerJSON(
        access: String = "access-a",
        refresh: String = "refresh-a",
        userId: String = "user-a",
        sessionId: String = "session-a"
    ) -> String {
        #"{"tokenType":"Bearer","accessToken":"\#(access)","refreshToken":"\#(refresh)","expiresAt":"2026-08-22T11:00:00.000Z","actor":{"userId":"\#(userId)","sessionId":"\#(sessionId)","memberships":[]}}"#
    }

    private func currentSessionJSON() -> String {
        #"{"actor":{"userId":"user-a","sessionId":"session-a","memberships":[]}}"#
    }

    private func errorJSON(code: String) -> String {
        #"{"error":{"code":"\#(code)","message":"\#(code)","requestId":"request-test"}}"#
    }
}

private final class MemorySessionCredentialStore: SessionCredentialStoring, @unchecked Sendable {
    private let lock = NSLock()
    private var storedCredentials: BearerSessionCredentials?
    private(set) var saveCalls = 0

    var credentials: BearerSessionCredentials? {
        lock.lock()
        defer { lock.unlock() }
        return storedCredentials
    }

    func load() throws -> BearerSessionCredentials? {
        credentials
    }

    func save(_ credentials: BearerSessionCredentials) throws {
        lock.lock()
        storedCredentials = credentials
        saveCalls += 1
        lock.unlock()
    }

    func clear() throws {
        lock.lock()
        storedCredentials = nil
        lock.unlock()
    }
}

private final class RequestCountState: @unchecked Sendable {
    private let lock = NSLock()
    private(set) var currentCalls = 0
    private(set) var refreshCalls = 0
    private(set) var authorizations: [String?] = []
    private(set) var ocrAuthorization: String?
    private(set) var ocrContentType: String?

    @discardableResult
    func recordCurrent(authorization: String?) -> Int {
        lock.lock()
        defer { lock.unlock() }
        currentCalls += 1
        authorizations.append(authorization)
        return currentCalls
    }

    func recordRefresh() {
        lock.lock()
        refreshCalls += 1
        lock.unlock()
    }

    func recordOCR(authorization: String?, contentType: String?) {
        lock.lock()
        ocrAuthorization = authorization
        ocrContentType = contentType
        lock.unlock()
    }
}

private final class SecureSessionURLProtocol: URLProtocol {
    enum Outcome {
        case json(statusCode: Int, body: String)
        case failure(Error)
    }

    private static let lock = NSLock()
    private static var handler: ((URLRequest) throws -> Outcome)?

    static func configure(_ handler: @escaping (URLRequest) throws -> Outcome) {
        lock.lock()
        self.handler = handler
        lock.unlock()
    }

    static func reset() {
        lock.lock()
        handler = nil
        lock.unlock()
    }

    override class func canInit(with request: URLRequest) -> Bool {
        request.url?.host == "finance-security-tests.invalid"
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        Self.lock.lock()
        let handler = Self.handler
        Self.lock.unlock()

        do {
            guard let handler else { throw URLError(.badServerResponse) }
            switch try handler(request) {
            case .failure(let error):
                client?.urlProtocol(self, didFailWithError: error)
            case .json(let statusCode, let body):
                guard let url = request.url,
                      let response = HTTPURLResponse(
                          url: url,
                          statusCode: statusCode,
                          httpVersion: "HTTP/1.1",
                          headerFields: ["Content-Type": "application/json"]
                      ) else {
                    throw URLError(.badServerResponse)
                }
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                client?.urlProtocol(self, didLoad: Data(body.utf8))
                client?.urlProtocolDidFinishLoading(self)
            }
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
