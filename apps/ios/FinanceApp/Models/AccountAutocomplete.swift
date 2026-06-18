import Foundation

struct AccountAutocompleteItem: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let accountType: AccountType
    let ownershipType: OwnershipType
    let householdId: String?
    let isPaymentAccount: Bool
    let currency: CurrencyCode
}
