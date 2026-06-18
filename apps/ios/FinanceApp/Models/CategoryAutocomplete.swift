import Foundation

struct CategoryAutocompleteItem: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let type: CategoryType
    let scope: CategoryScope
    let householdId: String?
    let iconKey: String?
    let color: String?
}
