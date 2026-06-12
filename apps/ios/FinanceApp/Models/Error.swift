import Foundation

struct FinanceError: Codable, Sendable {
    let code: String
    let message: String
    let requestId: String
    let details: [FinanceErrorDetail]?
}

struct FinanceErrorDetail: Codable, Sendable {
    let field: String?
    let reason: String?
    let allowedValues: [String]?
}
