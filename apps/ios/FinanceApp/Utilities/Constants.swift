import SwiftUI

enum FinanceColors {
    static let primary = Color(red: 0x25 / 255, green: 0x6B / 255, blue: 0x5F / 255)
    static let onPrimary = Color.white
    static let primaryContainer = Color(red: 0xD3 / 255, green: 0xF2 / 255, blue: 0xEA / 255)
    static let background = Color(red: 0xFB / 255, green: 0xFC / 255, blue: 0xFA / 255)
    static let surface = Color(red: 0xFB / 255, green: 0xFC / 255, blue: 0xFA / 255)
    static let income = Color(red: 0x2E / 255, green: 0x7D / 255, blue: 0x62 / 255)
    static let expense = Color(red: 0xE3 / 255, green: 0x5D / 255, blue: 0x4F / 255)
    static let transfer = Color(red: 0x5B / 255, green: 0x6E / 255, blue: 0xE1 / 255)
    static let investment = Color(red: 0x22 / 255, green: 0x7C / 255, blue: 0x9D / 255)
    static let warning = Color(red: 0x8A / 255, green: 0x6A / 255, blue: 0x12 / 255)
    static let error = Color(red: 0xE3 / 255, green: 0x5D / 255, blue: 0x4F / 255)
    static let planningPrimary = Color(red: 0x42 / 255, green: 0x67 / 255, blue: 0xD5 / 255)
    static let analyticsAccent = Color(red: 0x6D / 255, green: 0x5B / 255, blue: 0xD0 / 255)
}

enum FinanceConstants {
    static let currencies: [CurrencyCode] = [.RUB, .USD, .EUR, .XAU]
    static let csrfHeaderName = "X-CSRF-Token"
    static let sessionCookieName = "__Host-finance_session"
    static let passwordMinLength = 12
}
