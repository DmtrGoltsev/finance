import XCTest
@testable import FinanceApp

final class LocalStoreAndSyncPolicyTests: XCTestCase {
    func testLocalStoreSeparatesUsersAndSessionWiperRemovesOnlyRequestedScope() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppTests-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let store = FileBackedFinanceLocalStore(rootURL: root)
        let scopeA = LocalStoreScope(viewerUserId: "user-a", accessVersion: "1")
        let scopeB = LocalStoreScope(viewerUserId: "user-b", accessVersion: "1")
        var snapshotA = FinanceLocalSnapshot.empty(scope: scopeA, deviceId: "device")
        var snapshotB = FinanceLocalSnapshot.empty(scope: scopeB, deviceId: "device")
        snapshotA.syncState.cursor = 11
        snapshotB.syncState.cursor = 22
        try await store.saveSnapshot(snapshotA)
        try await store.saveSnapshot(snapshotB)

        let loadedA = try await store.loadSnapshot(scope: scopeA, deviceId: "device")
        let loadedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(loadedA.syncState.cursor, 11)
        XCTAssertEqual(loadedB.syncState.cursor, 22)

        let wiper = FinanceSessionDataWiper(localStore: store)
        try await wiper.wipeCurrentUser(scope: scopeA)
        let wipedA = try await store.loadSnapshot(scope: scopeA, deviceId: "device")
        let preservedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(wipedA.syncState.cursor, 0)
        XCTAssertEqual(preservedB.syncState.cursor, 22)

        try await wiper.wipeAllProtectedLocalData()
        let wipedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(wipedB.syncState.cursor, 0)
    }

    func testOfflineQueueRejectsSharedPayloads() {
        let scope = LocalStoreScope(viewerUserId: "user-a")
        let personal = PendingMutation(
            deviceId: "device",
            scope: scope,
            entityType: .accounts,
            entityId: "personal",
            operation: .create,
            payload: ["ownershipType": .string("personal"), "householdId": .null]
        )
        let shared = PendingMutation(
            deviceId: "device",
            scope: scope,
            entityType: .accounts,
            entityId: "shared",
            operation: .create,
            payload: ["ownershipType": .string("shared"), "householdId": .string("h")]
        )

        XCTAssertTrue(FinanceSyncService.isPersonalOnlyMutation(personal))
        XCTAssertFalse(FinanceSyncService.isPersonalOnlyMutation(shared))
    }

    func testOCRRemainsOnlineOnlyAndOutsideSyncEntityTypes() {
        XCTAssertFalse(SyncEntityType.allCases.map(\.rawValue).contains("capture_draft"))
        XCTAssertFalse(SyncEntityType.allCases.map(\.rawValue).contains("screenshot_ocr"))
        XCTAssertTrue(SyncQueuePolicy.onlineOnlyReason(.screenshotOCR).contains("только онлайн"))
        XCTAssertTrue(SyncQueuePolicy.onlineOnlyReason(.screenshotOCR).contains("нельзя сохранять локально"))
    }
}
