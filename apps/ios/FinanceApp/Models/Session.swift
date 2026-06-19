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
