import Foundation
import Security
import CryptoKit

final class CategoryAggregateMappingStore: @unchecked Sendable {
    static let shared = CategoryAggregateMappingStore()

    private let servicePrefix = "com.finance.app.category-mapping"

    private func serviceKey(_ label: String) -> String {
        let hash = SHA256.hash(data: Data(label.utf8))
        return "\(servicePrefix).\(hash.compactMap { String(format: "%02x", $0) }.joined())"
    }

    func save(label: String, categoryId: String) {
        let service = serviceKey(label)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: "mapping",
        ]
        SecItemDelete(query as CFDictionary)
        guard let data = categoryId.data(using: .utf8) else { return }
        let attributes: [String: Any] = query.merging([
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]) { _, new in new }
        SecItemAdd(attributes as CFDictionary, nil)
    }

    func get(label: String) -> String? {
        let service = serviceKey(label)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: "mapping",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
