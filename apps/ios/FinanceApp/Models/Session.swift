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

struct ActorContext: Codable, Sendable {
    let userId: String
    let sessionId: String?
    let memberships: [ActorMembership]
}

struct ActorMembership: Codable, Sendable {
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

struct CategoryMappingResult: Codable, Sendable {
    let categoryId: String
    let householdId: String?
}
