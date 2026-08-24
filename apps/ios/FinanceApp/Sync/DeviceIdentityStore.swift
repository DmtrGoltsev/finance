import Foundation

final class DeviceIdentityStore: @unchecked Sendable {
    static let shared = DeviceIdentityStore()

    private let defaults: UserDefaults
    private let key: String
    private let lock = NSLock()

    init(defaults: UserDefaults = .standard, key: String = "finance.sync.deviceId") {
        self.defaults = defaults
        self.key = key
    }

    func deviceId() -> String {
        lock.lock()
        defer { lock.unlock() }
        if let existing = defaults.string(forKey: key), !existing.isEmpty {
            return existing
        }
        let value = UUID().uuidString
        defaults.set(value, forKey: key)
        return value
    }
}

struct FinanceSessionDataWiper: Sendable {
    let localStore: FinanceLocalStore

    init(localStore: FinanceLocalStore) {
        self.localStore = localStore
    }

    func wipeCurrentUser(scope: LocalStoreScope) async throws {
        try await localStore.wipe(scope: scope)
    }

    func wipeAllProtectedLocalData() async throws {
        try await localStore.wipeAllProtectedData()
    }
}
