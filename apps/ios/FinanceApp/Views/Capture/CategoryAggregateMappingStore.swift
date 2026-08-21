import Foundation
import CryptoKit

final class CategoryAggregateMappingStore: @unchecked Sendable {
    static let shared = CategoryAggregateMappingStore()
    static let keychainAccessibility = DeviceBoundKeychain.accessibility

    private let servicePrefix = "com.finance.app.category-mapping"
    private let indexedServicesKey = "finance.category-mapping.services"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    private func serviceKey(_ label: String) -> String {
        let hash = SHA256.hash(data: Data(label.utf8))
        return "\(servicePrefix).\(hash.compactMap { String(format: "%02x", $0) }.joined())"
    }

    func save(label: String, categoryId: String) {
        let service = serviceKey(label)
        rememberService(service)
        DeviceBoundKeychain.saveString(categoryId, service: service, account: "mapping")
    }

    func get(label: String) -> String? {
        DeviceBoundKeychain.loadString(service: serviceKey(label), account: "mapping")
    }

    func clearAll() {
        indexedServices().forEach(deleteService)
        defaults.removeObject(forKey: indexedServicesKey)

    }

    private func rememberService(_ service: String) {
        var services = indexedServices()
        guard !services.contains(service) else { return }
        services.append(service)
        defaults.set(services, forKey: indexedServicesKey)
    }

    private func indexedServices() -> [String] {
        defaults.stringArray(forKey: indexedServicesKey) ?? []
    }

    private func deleteService(_ service: String) {
        DeviceBoundKeychain.delete(service: service, account: "mapping")
    }
}
