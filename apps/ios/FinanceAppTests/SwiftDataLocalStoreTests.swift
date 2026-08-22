import Foundation
import SwiftData
import XCTest
@testable import FinanceApp

final class SwiftDataLocalStoreTests: XCTestCase {
    func testAccountIsolationSurvivesLogoutAThenOpenB() async throws {
        let context = try makeContext("account-isolation")
        defer { context.cleanup() }
        let scopeA = LocalStoreScope(viewerUserId: "user-a")
        let scopeB = LocalStoreScope(viewerUserId: "user-b")
        var snapshotA = FinanceLocalSnapshot.empty(scope: scopeA, deviceId: "device")
        snapshotA.syncState.cursor = 11
        var snapshotB = FinanceLocalSnapshot.empty(scope: scopeB, deviceId: "device")
        snapshotB.syncState.cursor = 29
        try await context.store.saveSnapshot(snapshotA)
        try await context.store.saveSnapshot(snapshotB)

        try await context.store.wipe(scope: scopeA)

        let restoredA = try await context.store.loadSnapshot(scope: scopeA, deviceId: "device")
        let restoredB = try await context.store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(restoredA.syncState.cursor, 0)
        XCTAssertEqual(restoredB.syncState.cursor, 29)
        XCTAssertEqual(restoredB.scope.viewerUserId, "user-b")
    }

    func testStalePushResponseIsRejectedAfterAccountSwitch() async throws {
        let context = try makeContext("stale-response")
        defer { context.cleanup() }
        let scopeA = LocalStoreScope(viewerUserId: "user-a")
        let mutation = try await enqueueCategory(scope: scopeA, store: context.store)
        let api = DelayedSyncApiClient()
        let leases = SyncSessionLeaseCoordinator()
        await leases.activate(viewerUserId: "user-a", sessionId: "session-a")
        let service = FinanceSyncService(
            apiClient: api,
            localStore: context.store,
            deviceIdentityStore: context.deviceIdentityStore,
            leaseProvider: leases
        )

        let syncTask = Task { await service.syncNow(scope: scopeA) }
        await api.waitUntilPushStarts()
        await leases.activate(viewerUserId: "user-b", sessionId: "session-b")
        await service.cancelActiveSync()
        await api.resumePush()
        let result = await syncTask.value

        let snapshotA = try await context.store.loadSnapshot(scope: scopeA, deviceId: "device")
        let snapshotB = try await context.store.loadSnapshot(
            scope: LocalStoreScope(viewerUserId: "user-b"),
            deviceId: "device"
        )
        XCTAssertEqual(result.push.applied, 0)
        XCTAssertEqual(snapshotA.pendingMutations.map(\.clientMutationId), [mutation.clientMutationId])
        XCTAssertNotEqual(snapshotA.pendingMutations.first?.status.rawValue, PendingMutationStatus.applied.rawValue)
        XCTAssertTrue(snapshotB.pendingMutations.isEmpty)
        XCTAssertTrue(snapshotB.categories.isEmpty)
    }

    func testLegacyMigrationPreservesPendingMutationAndIsIdempotent() async throws {
        let context = try makeContext("migration-pending")
        defer { context.cleanup() }
        let legacyScope = LocalStoreScope(viewerUserId: "user-a", sessionId: "legacy-session")
        let mutation = PendingMutation(
            clientMutationId: "pending-preserved",
            deviceId: "legacy-device",
            scope: legacyScope,
            entityType: .categories,
            entityId: "category-pending",
            operation: .create,
            payload: [
                "name": .string("Pending"),
                "type": .string("expense"),
                "scope": .string("personal"),
            ]
        )
        var legacy = FinanceLocalSnapshot.empty(scope: legacyScope, deviceId: "legacy-device")
        legacy.pendingMutations = [mutation]
        let legacyURL = context.legacyRoot.appendingPathComponent("user-a_legacy-session.json")
        try FileManager.default.createDirectory(at: context.legacyRoot, withIntermediateDirectories: true)
        try JSONEncoder().encode(legacy).write(to: legacyURL, options: .atomic)

        let scope = LocalStoreScope(viewerUserId: "user-a")
        let first = try await context.store.loadSnapshot(scope: scope, deviceId: "device")
        let second = try await context.store.loadSnapshot(scope: scope, deviceId: "device")

        XCTAssertEqual(first.pendingMutations.map(\.clientMutationId), ["pending-preserved"])
        XCTAssertEqual(second.pendingMutations.map(\.clientMutationId), ["pending-preserved"])
        XCTAssertEqual(second.pendingMutations.first?.scope.viewerUserId, "user-a")
        XCTAssertNil(second.pendingMutations.first?.scope.sessionId)
        XCTAssertTrue(FileManager.default.fileExists(atPath: legacyURL.path), "Recovery JSON is retained")
    }

    func testFailedSwiftDataTransactionRollsBackWholeSnapshot() async throws {
        let context = try makeContext("transaction-rollback")
        defer { context.cleanup() }
        let scope = LocalStoreScope(viewerUserId: "user-a")
        var baseline = FinanceLocalSnapshot.empty(scope: scope, deviceId: "device")
        baseline.syncState.cursor = 7
        try await context.store.saveSnapshot(baseline)

        var rejected = baseline
        rejected.syncState.cursor = 99
        rejected.pendingMutations = [PendingMutation(
            clientMutationId: "must-rollback",
            deviceId: "device",
            scope: scope,
            entityType: .categories,
            entityId: "category",
            operation: .delete
        )]
        await context.store.injectFailureOnceForTesting(.beforeSave)
        do {
            try await context.store.saveSnapshot(rejected)
            XCTFail("Injected transaction failure must throw")
        } catch let error as SwiftDataFinanceLocalStoreError {
            XCTAssertEqual(error.localizedDescription, SwiftDataFinanceLocalStoreError.injectedFailure.localizedDescription)
        }

        let restored = try await context.store.loadSnapshot(scope: scope, deviceId: "device")
        XCTAssertEqual(restored.syncState.cursor, 7)
        XCTAssertTrue(restored.pendingMutations.isEmpty)
    }

    private func makeContext(_ name: String) throws -> SwiftDataTestContext {
        let schema = Schema([SwiftDataFinanceSnapshotRecord.self])
        let configuration = ModelConfiguration(
            "FinanceOfflineStore-\(name)-\(UUID().uuidString)",
            schema: schema,
            isStoredInMemoryOnly: true
        )
        let container = try ModelContainer(for: schema, configurations: [configuration])
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceApp-SwiftData-\(name)-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let suiteName = "FinanceApp.SwiftData.\(name).\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.set("device", forKey: "device-id")
        return SwiftDataTestContext(
            store: SwiftDataFinanceLocalStore(modelContainer: container, legacyRootURL: root),
            legacyRoot: root,
            deviceIdentityStore: DeviceIdentityStore(defaults: defaults, key: "device-id"),
            defaultsSuiteName: suiteName
        )
    }

    private func enqueueCategory(
        scope: LocalStoreScope,
        store: SwiftDataFinanceLocalStore
    ) async throws -> PendingMutation {
        let category = TestFixtures.category(id: "category-pending")
        let optimisticPayload = try SyncJSONValue.object(from: category)
        let evidence = try PersonalSyncOwnershipValidator.evidence(
            scope: scope,
            entityType: .categories,
            entityId: category.id,
            ownershipPayload: optimisticPayload,
            snapshot: .empty(scope: scope, deviceId: "device")
        )
        let mutation = PendingMutation(
            clientMutationId: "mutation-pending",
            deviceId: "device",
            scope: scope,
            entityType: .categories,
            entityId: category.id,
            operation: .create,
            payload: [
                "name": .string(category.name),
                "type": .string("expense"),
                "scope": .string("personal"),
            ],
            ownershipEvidence: evidence
        )
        try await store.commitOptimisticMutation(
            mutation,
            planningMetadata: nil,
            optimisticPayload: optimisticPayload
        )
        return mutation
    }
}

private struct SwiftDataTestContext {
    let store: SwiftDataFinanceLocalStore
    let legacyRoot: URL
    let deviceIdentityStore: DeviceIdentityStore
    let defaultsSuiteName: String

    func cleanup() {
        try? FileManager.default.removeItem(at: legacyRoot)
        UserDefaults.standard.removePersistentDomain(forName: defaultsSuiteName)
    }
}

private actor DelayedSyncApiClient: FinanceSyncApiClient {
    private var pushStarted = false
    private var pushContinuation: CheckedContinuation<Void, Never>?

    func syncPush(_ request: SyncPushRequest) async throws -> SyncPushResponse {
        pushStarted = true
        await withCheckedContinuation { continuation in
            pushContinuation = continuation
        }
        let mutation = try XCTUnwrap(request.mutations.first)
        return SyncPushResponse(
            deviceId: request.deviceId,
            serverTime: "2026-08-22T10:00:00.000Z",
            results: [SyncMutationResult(
                clientMutationId: mutation.clientMutationId,
                entityType: mutation.entityType,
                entityId: mutation.entityId,
                operation: mutation.operation,
                status: .applied,
                serverVersion: 1,
                changeSeq: 1,
                errorCode: nil,
                message: nil,
                data: nil
            )]
        )
    }

    func syncPull(_ request: SyncPullRequest) async throws -> SyncPullResponse {
        SyncPullResponse(
            changes: [],
            nextCursor: request.cursor,
            hasMore: false,
            serverTime: "2026-08-22T10:00:00.000Z"
        )
    }

    func waitUntilPushStarts() async {
        while !pushStarted { await Task.yield() }
    }

    func resumePush() {
        pushContinuation?.resume()
        pushContinuation = nil
    }
}
