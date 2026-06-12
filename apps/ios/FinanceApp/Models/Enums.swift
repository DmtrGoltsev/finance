import Foundation

enum FinanceMode: String, CaseIterable, Sendable {
    case personal, shared, overview

    var title: String {
        switch self {
        case .personal: return "Личное"
        case .shared: return "Общее"
        case .overview: return "Мой обзор"
        }
    }
}

enum AuthTransport: String, Codable, Sendable {
    case pwa_cookie
}
