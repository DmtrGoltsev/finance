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
        let token = DeviceBoundKeychain.loadString(service: service, account: account)
        cachedToken = token
        return token
    }

    var sessionExpiry: String? {
        if let cached = cachedExpiry { return cached }
        let expiry = DeviceBoundKeychain.loadString(service: sessionService, account: sessionAccount)
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
        DeviceBoundKeychain.saveString(token, service: service, account: account)
    }

    func saveSessionExpiry(_ expiry: String) {
        cachedExpiry = expiry
        DeviceBoundKeychain.saveString(expiry, service: sessionService, account: sessionAccount)
    }

    func clear() {
        cachedToken = nil
        cachedExpiry = nil
        DeviceBoundKeychain.delete(service: service, account: account)
        DeviceBoundKeychain.delete(service: sessionService, account: sessionAccount)
    }
}

final class SessionIdentityStore: @unchecked Sendable {
    static let shared = SessionIdentityStore()
    private let service = "com.finance.app.session-identity"
    private let account = "last-authenticated-user"

    func load() -> SessionIdentityBinding? {
        guard let data = DeviceBoundKeychain.loadData(service: service, account: account) else { return nil }
        guard let binding = try? JSONDecoder().decode(SessionIdentityBinding.self, from: data),
              !binding.userId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        return binding
    }

    func save(_ binding: SessionIdentityBinding) {
        guard let data = try? JSONEncoder().encode(binding) else { return }
        DeviceBoundKeychain.saveData(data, service: service, account: account)
    }

    func clear() {
        DeviceBoundKeychain.delete(service: service, account: account)
    }
}

enum DeviceBoundKeychain {
    static let accessibility = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

    @discardableResult
    static func saveString(_ value: String, service: String, account: String) -> OSStatus {
        guard let data = value.data(using: .utf8) else { return errSecParam }
        return saveData(data, service: service, account: account)
    }

    static func loadString(service: String, account: String) -> String? {
        guard let data = loadData(service: service, account: account) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    @discardableResult
    static func saveData(_ data: Data, service: String, account: String) -> OSStatus {
        let query = baseQuery(service: service, account: account)
        let updateAttributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: accessibility,
        ]
        let updateStatus = SecItemUpdate(query as CFDictionary, updateAttributes as CFDictionary)
        guard updateStatus == errSecItemNotFound else { return updateStatus }

        let addAttributes = query.merging(updateAttributes) { _, new in new }
        return SecItemAdd(addAttributes as CFDictionary, nil)
    }

    static func loadData(service: String, account: String) -> Data? {
        var query = baseQuery(service: service, account: account)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        SecItemUpdate(
            baseQuery(service: service, account: account) as CFDictionary,
            [kSecAttrAccessible as String: accessibility] as CFDictionary
        )
        return data
    }

    static func delete(service: String, account: String) {
        SecItemDelete(baseQuery(service: service, account: account) as CFDictionary)
    }

    private static func baseQuery(service: String, account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}
