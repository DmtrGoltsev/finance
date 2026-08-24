import Foundation

enum CategoryScope: String, Codable, Sendable {
    case personal, household
}

enum CategoryType: String, Codable, Sendable {
    case income, expense
}

struct Category: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let type: CategoryType
    let scope: CategoryScope
    let ownerUserId: String?
    let householdId: String?
    let iconKey: String?
    let color: String?
    let status: RecordStatus
    let version: Int?
}

typealias FinanceCategory = Category

struct CategoryCreateRequest: Codable, Sendable {
    let name: String
    let type: CategoryType
    let scope: CategoryScope
    let householdId: String?
    let iconKey: String?
    let color: String?
}

struct CategoryUpdateRequest: Codable, Sendable {
    let name: String?
    let iconKey: String?
    let color: String?
    let version: Int?
}

struct CategoryOfflineUpdateRequest: Codable, Sendable {
    let name: String?
    let iconKey: String?
    let color: String?

    init(_ request: CategoryUpdateRequest) {
        name = request.name
        iconKey = request.iconKey
        color = request.color
    }
}
