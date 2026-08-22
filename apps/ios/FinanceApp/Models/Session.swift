import Foundation

struct SessionStatus: Codable, Sendable {
    let isAuthenticated: Bool
    let displayName: String?
    let householdId: String?
    let userId: String?
    let sessionId: String?

    init(isAuthenticated: Bool, displayName: String?, householdId: String?, userId: String? = nil, sessionId: String? = nil) {
        self.isAuthenticated = isAuthenticated
        self.displayName = displayName
        self.householdId = householdId
        self.userId = userId
        self.sessionId = sessionId
    }
}

struct SessionIdentityBinding: Codable, Equatable, Sendable {
    let userId: String
    let displayName: String?

    init?(session: SessionStatus) {
        guard session.isAuthenticated,
              let userId = session.userId?.trimmingCharacters(in: .whitespacesAndNewlines),
              !userId.isEmpty else {
            return nil
        }
        self.userId = userId
        self.displayName = session.displayName
    }
}

enum SessionRestorePolicy {
    static func isConfirmedInvalidIdentity(_ error: Error) -> Bool {
        guard let apiError = error as? FinanceApiError else { return false }
        switch apiError {
        case .unauthorized:
            return true
        case .httpError(let statusCode, _):
            return statusCode == 401
        default:
            return false
        }
    }
}

enum SessionHTTPStatusPolicy {
    static func invalidatesIdentity(statusCode: Int) -> Bool {
        statusCode == 401
    }

    static func isForbiddenOrCSRF(statusCode: Int) -> Bool {
        statusCode == 403
    }
}

enum OfflineSessionRestorePolicy {
    static let maximumGrace: TimeInterval = 72 * 60 * 60

    static func canRestore(lastServerValidatedAt: String?, now: Date = Date()) -> Bool {
        guard let lastServerValidatedAt,
              let validatedAt = parse(lastServerValidatedAt) else {
            return false
        }
        let elapsed = now.timeIntervalSince(validatedAt)
        return elapsed >= 0 && elapsed <= maximumGrace
    }

    private static func parse(_ value: String) -> Date? {
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractional.date(from: value) {
            return date
        }
        let standard = ISO8601DateFormatter()
        standard.formatOptions = [.withInternetDateTime]
        return standard.date(from: value)
    }
}

struct LogoutResult: Equatable, Sendable {
    let remoteSessionRevoked: Bool
    let localCredentialsCleared: Bool
}

struct SessionLease: Equatable, Sendable {
    let userId: String
    let sessionId: String
    let generation: UInt64
}

struct BearerSessionCredentials: Codable, Equatable, Sendable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: String
    let accessExpiresAt: String?
    let refreshExpiresAt: String?
    let userId: String
    let sessionId: String
    let revokeToken: String?
    let lastServerValidatedAt: String?

    init(
        accessToken: String,
        refreshToken: String,
        expiresAt: String,
        accessExpiresAt: String? = nil,
        refreshExpiresAt: String? = nil,
        userId: String,
        sessionId: String,
        revokeToken: String? = nil,
        lastServerValidatedAt: String? = nil
    ) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.expiresAt = expiresAt
        self.accessExpiresAt = accessExpiresAt
        self.refreshExpiresAt = refreshExpiresAt
        self.userId = userId
        self.sessionId = sessionId
        self.revokeToken = revokeToken
        self.lastServerValidatedAt = lastServerValidatedAt
    }

    func serverValidated(at date: Date) -> BearerSessionCredentials {
        BearerSessionCredentials(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresAt: expiresAt,
            accessExpiresAt: accessExpiresAt,
            refreshExpiresAt: refreshExpiresAt,
            userId: userId,
            sessionId: sessionId,
            revokeToken: revokeToken,
            lastServerValidatedAt: date.ISO8601Format()
        )
    }
}

struct AuthorizedSession: Equatable, Sendable {
    let accessToken: String
    let lease: SessionLease
}

struct LogoutAuthorization: Equatable, Sendable {
    let accessToken: String?
    let sessionId: String?
    let revokeToken: String?
    let localCredentialsCleared: Bool
}

enum SessionCoordinatorError: Error, Equatable, LocalizedError, Sendable {
    case unavailable
    case superseded
    case identityMismatch
    case invalidBearerResponse
    case credentialPersistenceFailed

    var errorDescription: String? {
        switch self {
        case .unavailable:
            return "Сессия отсутствует. Войдите снова."
        case .superseded:
            return "Сессия была изменена во время запроса."
        case .identityMismatch:
            return "Сервер вернул данные другой сессии."
        case .invalidBearerResponse:
            return "Сервер вернул некорректные данные мобильной сессии."
        case .credentialPersistenceFailed:
            return "Не удалось безопасно сохранить мобильную сессию."
        }
    }
}

struct ActorContext: Codable, Equatable, Sendable {
    let userId: String
    let sessionId: String?
    let memberships: [ActorMembership]
}

struct ActorMembership: Codable, Equatable, Sendable {
    let householdId: String
    let status: String
}

enum RegistrationResult: Sendable {
    case authenticated(SessionStatus)
    case accepted(message: String)
}

struct LoginResponse: Codable, Sendable {
    let transport: String
    let csrfToken: String?
    let expiresAt: String?
    let actor: ActorContext?
}

struct BearerSessionResponse: Codable, Equatable, Sendable {
    let tokenType: String
    let accessToken: String
    let refreshToken: String
    let revokeToken: String?
    let expiresAt: String
    let accessExpiresAt: String?
    let refreshExpiresAt: String?
    let actor: ActorContext

    init(
        tokenType: String,
        accessToken: String,
        refreshToken: String,
        revokeToken: String? = nil,
        expiresAt: String,
        accessExpiresAt: String? = nil,
        refreshExpiresAt: String? = nil,
        actor: ActorContext
    ) {
        self.tokenType = tokenType
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.revokeToken = revokeToken
        self.expiresAt = expiresAt
        self.accessExpiresAt = accessExpiresAt
        self.refreshExpiresAt = refreshExpiresAt
        self.actor = actor
    }

    func credentials(validatedAt: Date) -> BearerSessionCredentials? {
        let accessToken = accessToken.trimmingCharacters(in: .whitespacesAndNewlines)
        let refreshToken = refreshToken.trimmingCharacters(in: .whitespacesAndNewlines)
        let userId = actor.userId.trimmingCharacters(in: .whitespacesAndNewlines)
        let sessionId = actor.sessionId?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard tokenType.caseInsensitiveCompare("Bearer") == .orderedSame,
              !accessToken.isEmpty,
              !refreshToken.isEmpty,
              !expiresAt.isEmpty,
              !userId.isEmpty,
              !sessionId.isEmpty else {
            return nil
        }
        return BearerSessionCredentials(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresAt: expiresAt,
            accessExpiresAt: accessExpiresAt ?? expiresAt,
            refreshExpiresAt: refreshExpiresAt ?? expiresAt,
            userId: userId,
            sessionId: sessionId,
            revokeToken: revokeToken,
            lastServerValidatedAt: validatedAt.ISO8601Format()
        )
    }

    var sessionStatus: SessionStatus {
        SessionStatus(
            isAuthenticated: true,
            displayName: "Пользователь \(actor.userId.prefix(8))",
            householdId: nil,
            userId: actor.userId,
            sessionId: actor.sessionId
        )
    }
}

struct CategoryMappingResult: Codable, Sendable {
    let categoryId: String
    let householdId: String?
}
