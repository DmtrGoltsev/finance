import Foundation
import Security

final class CSRFTokenStore: @unchecked Sendable {
    static let shared = CSRFTokenStore()
    private let service = "com.finance.app.csrf-token"
    private let account = "csrf-token"
    private let sessionService = "com.finance.app.session-expiry"
    private let sessionAccount = "session-expiry"

    private var cachedToken: String?
    private var cachedExpiry: String?

    var csrfToken: String? {
        if let cached = cachedToken { return cached }
        let token = loadFromKeychain(service: service, account: account)
        cachedToken = token
        return token
    }

    var sessionExpiry: String? {
        if let cached = cachedExpiry { return cached }
        let expiry = loadFromKeychain(service: sessionService, account: sessionAccount)
        cachedExpiry = expiry
        return expiry
    }

    var isSessionExpired: Bool {
        guard let expiry = sessionExpiry else { return true }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: expiry) else { return true }
        return date < Date()
    }

    func saveCsrfToken(_ token: String) {
        cachedToken = token
        saveToKeychain(value: token, service: service, account: account)
    }

    func saveSessionExpiry(_ expiry: String) {
        cachedExpiry = expiry
        saveToKeychain(value: expiry, service: sessionService, account: sessionAccount)
    }

    func clear() {
        cachedToken = nil
        cachedExpiry = nil
        deleteFromKeychain(service: service, account: account)
        deleteFromKeychain(service: sessionService, account: sessionAccount)
    }

    private func saveToKeychain(value: String, service: String, account: String) {
        guard let data = value.data(using: .utf8) else { return }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        let attributes: [String: Any] = query + [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        SecItemAdd(attributes as CFDictionary, nil)
    }

    private func loadFromKeychain(service: String, account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func deleteFromKeychain(service: String, account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
