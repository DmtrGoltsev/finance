import XCTest
@testable import FinanceApp

final class SyncReliabilityTests: XCTestCase {
    func testBackendPlanningPayloadsDecodeAndMergeIntoPlan() async throws {
        let context = try makeContext("planning-payload")
        defer { context.cleanup() }
        let planId = UUID().uuidString
        let incomeId = UUID().uuidString
        let allocationId = UUID().uuidString

        try await context.store.applyPullPage(
            scope: context.scope,
            deviceId: context.deviceId,
            response: SyncPullResponse(
                changes: [
                    change(
                        seq: 1,
                        entityType: .planningPlans,
                        entityId: planId,
                        payload: [
                            "id": .string(planId),
                            "scope": .string("personal"),
                            "ownerUserId": .string(context.scope.viewerUserId),
                            "householdId": .null,
                            "month": .string("2026-08"),
                            "currency": .string("RUB"),
                            "version": .int(3),
                        ]
                    ),
                    change(
                        seq: 2,
                        entityType: .planningIncomeSources,
                        entityId: incomeId,
                        payload: [
                            "id": .string(incomeId),
                            "planId": .string(planId),
                            "amount": .string("125000.50"),
                            "source": .string("Salary"),
                            "description": .string("Main job"),
                            "dayOfMonth": .int(5),
                            "confirmationState": .string("confirmed"),
                            "confirmedAt": .string("2026-08-05T08:00:00.000Z"),
                            "version": .int(4),
                        ]
                    ),
                    change(
                        seq: 3,
                        entityType: .planningAllocations,
                        entityId: allocationId,
                        payload: [
                            "id": .string(allocationId),
                            "planId": .string(planId),
                            "targetType": .string("expense_category"),
                            "targetId": .string("category-food"),
                            "targetSnapshot": .object([
                                "name": .string("Food"),
                                "meta": .object(["rank": .int(2)]),
                                "flags": .array([.bool(true), .null]),
                            ]),
                            "requiresAttention": .bool(false),
                            "allocationMode": .string("amount"),
                            "allocationValue": .string("30000"),
                            "isSavingsGoal": .bool(false),
                            "recordStatus": .string("active"),
                            "version": .int(7),
                        ]
                    ),
                ],
                nextCursor: 3,
                hasMore: false,
                serverTime: "2026-08-21T10:00:00.000Z"
            ),
            quarantined: []
        )

        let snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        let plan = try XCTUnwrap(snapshot.planningPlans.first?.entity)
        XCTAssertEqual(plan.summary.totalPlannedIncome, "0")
        XCTAssertEqual(plan.incomeSources.map(\.id), [incomeId])
        XCTAssertEqual(plan.incomeSources.first?.confirmationState.rawValue, IncomeConfirmationState.confirmed.rawValue)
        XCTAssertEqual(plan.allocations.map(\.id), [allocationId])
        XCTAssertEqual(plan.allocations.first?.targetSnapshot?["meta"], .object(["rank": .int(2)]))
        XCTAssertEqual(plan.allocations.first?.targetSnapshot?["flags"], .array([.bool(true), .null]))
        XCTAssertEqual(snapshot.syncState.cursor, 3)
        XCTAssertTrue(snapshot.issues.isEmpty)
    }

    func testCreateThenDeleteInSamePullPageLeavesNoEntityAndAdvancesCursor() async throws {
        let context = try makeContext("create-delete-page")
        defer { context.cleanup() }
        let planId = UUID().uuidString
        let created = change(
            seq: 1,
            entityType: .planningPlans,
            entityId: planId,
            payload: planningPlanPayload(id: planId, ownerUserId: context.scope.viewerUserId)
        )
        let deleted = change(
            seq: 2,
            entityType: .planningPlans,
            entityId: planId,
            changeType: "delete",
            payload: nil,
            tombstonePayload: ["id": .string(planId)]
        )

        try await context.store.applyPullPage(
            scope: context.scope,
            deviceId: context.deviceId,
            response: SyncPullResponse(
                changes: [created, deleted],
                nextCursor: 2,
                hasMore: false,
                serverTime: "2026-08-21T10:00:00.000Z"
            ),
            quarantined: []
        )

        let snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertTrue(snapshot.planningPlans.isEmpty)
        XCTAssertEqual(snapshot.tombstones.map(\.entityId), [planId])
        XCTAssertEqual(snapshot.syncState.cursor, 2)
    }

    func testProductionPullEvolvesOwnershipForCreateThenDelete() async throws {
        let context = try makeContext("production-create-delete-page")
        defer { context.cleanup() }
        let planId = UUID().uuidString
        let created = change(
            seq: 1,
            entityType: .planningPlans,
            entityId: planId,
            payload: planningPlanPayload(id: planId, ownerUserId: context.scope.viewerUserId)
        )
        let deleted = change(
            seq: 2,
            entityType: .planningPlans,
            entityId: planId,
            changeType: "delete",
            payload: nil,
            tombstonePayload: [
                "id": .string(planId),
                "entityType": .string(SyncEntityType.planningPlans.rawValue),
            ]
        )
        let service = FinanceSyncService(
            apiClient: StubSyncApiClient(mode: .pull(SyncPullResponse(
                changes: [created, deleted],
                nextCursor: 2,
                hasMore: false,
                serverTime: "2026-08-21T10:00:00.000Z"
            ))),
            localStore: context.store,
            deviceIdentityStore: context.deviceIdentityStore
        )

        let result = await service.syncNow(scope: context.scope)
        let snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)

        XCTAssertEqual(result.pulledChanges, 2)
        XCTAssertTrue(result.issues.isEmpty)
        XCTAssertTrue(snapshot.planningPlans.isEmpty)
        XCTAssertEqual(snapshot.tombstones.map(\.entityId), [planId])
        XCTAssertEqual(snapshot.syncState.cursor, 2)
    }

    func testLegacyCookieStateCannotAuthorizeNativeClientAndIsCleared() async throws {
        let context = try makeContext("live-403")
        defer { context.cleanup() }
        let pendingMutation = try await enqueuePersonalCategory(in: context)
        let tokenStore = CSRFTokenStore.shared
        let identityStore = SessionIdentityStore.shared
        tokenStore.clear()
        identityStore.clear()
        defer {
            tokenStore.clear()
            identityStore.clear()
        }
        tokenStore.saveCsrfToken("csrf-kept")
        tokenStore.saveSessionExpiry("2026-08-22T10:00:00.000Z")
        identityStore.save(try XCTUnwrap(SessionIdentityBinding(session: SessionStatus(
            isAuthenticated: true,
            displayName: "User",
            householdId: nil,
            userId: "user-a"
        ))))
        StubURLProtocol.response = .init(statusCode: 403, body: #"{"message":"Forbidden"}"#)

        do {
            _ = try await LiveApiClient(
                baseURL: "https://finance-tests.invalid",
                session: makeStubbedSession()
            ).sessionStatus()
            XCTFail("Expected unauthorized without iOS bearer credentials")
        } catch {
            XCTAssertTrue(SessionRestorePolicy.isConfirmedInvalidIdentity(error))
        }
        XCTAssertNil(tokenStore.csrfToken)
        XCTAssertNil(tokenStore.sessionExpiry)
        XCTAssertEqual(identityStore.load()?.userId, "user-a")
        let snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(snapshot.pendingMutations.map(\.clientMutationId), [pendingMutation.clientMutationId])
    }

    func testLive401ClearsCredentialsAndRequiresIdentityWipe() async throws {
        let tokenStore = CSRFTokenStore.shared
        tokenStore.clear()
        defer {
            tokenStore.clear()
        }
        tokenStore.saveCsrfToken("csrf-to-clear")
        tokenStore.saveSessionExpiry("2026-08-22T10:00:00.000Z")
        StubURLProtocol.response = .init(statusCode: 401, body: #"{"message":"Unauthorized"}"#)

        do {
            _ = try await LiveApiClient(
                baseURL: "https://finance-tests.invalid",
                session: makeStubbedSession()
            ).sessionStatus()
            XCTFail("Expected unauthorized")
        } catch {
            XCTAssertTrue(SessionRestorePolicy.isConfirmedInvalidIdentity(error))
        }
        XCTAssertNil(tokenStore.csrfToken)
        XCTAssertNil(tokenStore.sessionExpiry)
    }

    private func makeStubbedSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    func testNetworkColdStartPreservesPendingQueueThroughRealSyncService() async throws {
        let context = try makeContext("network-cold-start")
        defer { context.cleanup() }
        let mutation = try await enqueuePersonalCategory(in: context)
        let api = StubSyncApiClient(mode: .networkFailure)
        let service = FinanceSyncService(
            apiClient: api,
            localStore: context.store,
            deviceIdentityStore: context.deviceIdentityStore
        )

        let result = await service.syncNow(scope: context.scope)
        XCTAssertFalse(result.requiresReauthentication)
        XCTAssertGreaterThanOrEqual(result.push.retry, 1)

        let coldStore = FileBackedFinanceLocalStore(rootURL: context.root)
        let restored = try await coldStore.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(restored.pendingMutations.map(\.clientMutationId), [mutation.clientMutationId])
        XCTAssertEqual(restored.pendingMutations.first?.status.rawValue, PendingMutationStatus.retry.rawValue)
    }

    func testLegacySnapshotMigratesThenLogoutWipesCurrentAndLegacyFiles() async throws {
        let context = try makeContext("legacy-migration")
        defer { context.cleanup() }
        let legacyScope = LocalStoreScope(viewerUserId: context.scope.viewerUserId, sessionId: "legacy-session")
        var legacy = FinanceLocalSnapshot.empty(scope: legacyScope, deviceId: "legacy-device")
        legacy.syncState.cursor = 41
        legacy.categories = [localRecord(TestFixtures.category(id: "legacy-category"), entityType: .categories)]
        let legacyURL = context.root.appendingPathComponent("user-a_legacy-session.json")
        try FileManager.default.createDirectory(at: context.root, withIntermediateDirectories: true)
        try JSONEncoder().encode(legacy).write(to: legacyURL, options: .atomic)

        let migrated = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(migrated.syncState.cursor, 41)
        XCTAssertEqual(migrated.categories.map { $0.entity.id }, ["legacy-category"])
        XCTAssertFalse(FileManager.default.fileExists(atPath: legacyURL.path))

        try await FinanceSessionDataWiper(localStore: context.store).wipeCurrentUser(scope: context.scope)
        let afterLogout = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(afterLogout.syncState.cursor, 0)
        XCTAssertTrue(afterLogout.categories.isEmpty)
    }

    func testLegacyMigrationPreservesPendingDeleteTombstoneWithoutEntity() async throws {
        let context = try makeContext("legacy-pending-delete")
        defer { context.cleanup() }
        let legacyScope = LocalStoreScope(viewerUserId: context.scope.viewerUserId, sessionId: "legacy-session")
        let entityId = UUID().uuidString
        let mutationId = UUID().uuidString
        let evidence = SyncOwnershipEvidence(
            viewerUserId: context.scope.viewerUserId,
            subjectEntityType: .categories,
            subjectEntityId: entityId,
            referencedAccountIds: [],
            referencedCategoryIds: [],
            referencedAssetCategoryIds: [],
            referencedPlanIds: [],
            attestedPersonalPlanIds: [],
            attestedPersonalAccountIds: [],
            attestedPersonalCategoryIds: [],
            attestedPersonalAssetCategoryIds: []
        )
        var legacy = FinanceLocalSnapshot.empty(scope: legacyScope, deviceId: "legacy-device")
        legacy.pendingMutations = [PendingMutation(
            clientMutationId: mutationId,
            deviceId: "legacy-device",
            scope: legacyScope,
            entityType: .categories,
            entityId: entityId,
            operation: .delete,
            baseVersion: 3,
            payload: nil,
            ownershipEvidence: evidence
        )]
        legacy.tombstones = [SyncTombstone(
            entityType: .categories,
            entityId: entityId,
            operation: .delete,
            baseVersion: 3,
            pendingMutationId: mutationId,
            createdAt: "2026-08-21T10:00:00.000Z",
            safeError: nil
        )]
        let legacyURL = context.root.appendingPathComponent("user-a_legacy-session.json")
        try FileManager.default.createDirectory(at: context.root, withIntermediateDirectories: true)
        try JSONEncoder().encode(legacy).write(to: legacyURL, options: .atomic)

        let migrated = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)

        XCTAssertTrue(migrated.categories.isEmpty)
        XCTAssertEqual(migrated.pendingMutations.map(\.clientMutationId), [mutationId])
        XCTAssertEqual(migrated.tombstones.map(\.pendingMutationId), [mutationId])
        XCTAssertEqual(migrated.tombstones.map(\.entityId), [entityId])
    }

    func testOptimisticRecordAndMutationCommitAtomicallyToOneSnapshot() async throws {
        let context = try makeContext("atomic-optimistic")
        defer { context.cleanup() }
        let mutation = try await enqueuePersonalCategory(in: context)

        let coldStore = FileBackedFinanceLocalStore(rootURL: context.root)
        let snapshot = try await coldStore.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(snapshot.categories.map { $0.entity.id }, [mutation.entityId])
        XCTAssertEqual(snapshot.categories.first?.metadata.pendingMutationId, mutation.clientMutationId)
        XCTAssertEqual(snapshot.pendingMutations.map(\.clientMutationId), [mutation.clientMutationId])
    }

    func testCreateUpdateDeleteCoalescesAndSuccessorReceivesServerBaseVersion() async throws {
        let context = try makeContext("coalescing")
        defer { context.cleanup() }
        let entityId = UUID().uuidString
        let create = mutation(
            context: context,
            entityId: entityId,
            operation: .create,
            payload: ["name": .string("Draft"), "type": .string("expense"), "scope": .string("personal")]
        )
        try await context.store.commitOptimisticMutation(
            create,
            planningMetadata: nil,
            optimisticPayload: categoryPayload(id: entityId, name: "Draft")
        )
        let update = mutation(
            context: context,
            entityId: entityId,
            operation: .update,
            baseVersion: 1,
            payload: ["name": .string("Final")]
        )
        try await context.store.commitOptimisticMutation(
            update,
            planningMetadata: nil,
            optimisticPayload: categoryPayload(id: entityId, name: "Final", version: 1)
        )
        var snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(snapshot.pendingMutations.count, 1)
        XCTAssertEqual(snapshot.pendingMutations.first?.operation.rawValue, SyncOperation.create.rawValue)
        XCTAssertEqual(snapshot.pendingMutations.first?.payload?["name"], .string("Final"))
        XCTAssertEqual(snapshot.categories.first?.entity.name, "Final")

        let delete = mutation(context: context, entityId: entityId, operation: .delete, baseVersion: 1)
        try await context.store.commitOptimisticMutation(delete, planningMetadata: nil, optimisticPayload: [:])
        snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertTrue(snapshot.pendingMutations.isEmpty)
        XCTAssertTrue(snapshot.categories.isEmpty)
        XCTAssertTrue(snapshot.tombstones.isEmpty)

        let persistedId = UUID().uuidString
        let firstUpdate = mutation(
            context: context,
            entityId: persistedId,
            operation: .update,
            baseVersion: 4,
            payload: ["name": .string("One")]
        )
        let secondUpdate = mutation(
            context: context,
            entityId: persistedId,
            operation: .update,
            baseVersion: 4,
            payload: ["name": .string("Two")]
        )
        try await context.store.commitOptimisticMutation(
            firstUpdate,
            planningMetadata: nil,
            optimisticPayload: categoryPayload(id: persistedId, name: "One", version: 4)
        )
        try await context.store.commitOptimisticMutation(
            secondUpdate,
            planningMetadata: nil,
            optimisticPayload: categoryPayload(id: persistedId, name: "Two", version: 4)
        )
        let initiallyReady = try await context.store.pendingMutations(
            scope: context.scope,
            deviceId: context.deviceId,
            limit: 100
        )
        XCTAssertEqual(initiallyReady.count, 1)
        try await context.store.markApplied(
            scope: context.scope,
            deviceId: context.deviceId,
            result: SyncMutationResult(
                clientMutationId: firstUpdate.clientMutationId,
                entityType: .categories,
                entityId: persistedId,
                operation: .update,
                status: .applied,
                serverVersion: 5,
                changeSeq: 20,
                errorCode: nil,
                message: nil,
                data: categoryPayload(id: persistedId, name: "One", version: 5)
            )
        )
        let successor = try await context.store.pendingMutations(scope: context.scope, deviceId: context.deviceId, limit: 100)
        let afterFirstResult = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(successor.map(\.clientMutationId), [secondUpdate.clientMutationId])
        XCTAssertEqual(successor.first?.baseVersion, 5)
        XCTAssertEqual(afterFirstResult.categories.first?.entity.name, "Two")
    }

    func testPushResultMismatchIsQuarantinedForRetry() async throws {
        let context = try makeContext("push-mismatch")
        defer { context.cleanup() }
        let mutation = try await enqueuePersonalCategory(in: context)
        let service = FinanceSyncService(
            apiClient: StubSyncApiClient(mode: .mismatchedResult),
            localStore: context.store,
            deviceIdentityStore: context.deviceIdentityStore
        )

        let result = await service.syncNow(scope: context.scope)
        let snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertEqual(result.push.failed, 1)
        XCTAssertEqual(result.push.retry, 1)
        XCTAssertEqual(snapshot.pendingMutations.first?.clientMutationId, mutation.clientMutationId)
        XCTAssertEqual(snapshot.pendingMutations.first?.status.rawValue, PendingMutationStatus.retry.rawValue)
        XCTAssertEqual(snapshot.issues.first?.mutationId, mutation.clientMutationId)
    }

    func testUndecodablePullIsQuarantinedWhileCursorAdvances() async throws {
        let context = try makeContext("decode-quarantine")
        defer { context.cleanup() }
        let planId = UUID().uuidString
        let bad = change(
            seq: 9,
            entityType: .planningPlans,
            entityId: planId,
            payload: ["id": .string(planId), "scope": .string("personal")]
        )

        try await context.store.applyPullPage(
            scope: context.scope,
            deviceId: context.deviceId,
            response: SyncPullResponse(
                changes: [bad],
                nextCursor: 9,
                hasMore: false,
                serverTime: "2026-08-21T10:00:00.000Z"
            ),
            quarantined: []
        )

        let snapshot = try await context.store.loadSnapshot(scope: context.scope, deviceId: context.deviceId)
        XCTAssertTrue(snapshot.planningPlans.isEmpty)
        XCTAssertEqual(snapshot.syncState.cursor, 9)
        XCTAssertEqual(snapshot.issues.first?.errorCode, "PULL_CHANGE_DECODE_FAILED")
        XCTAssertEqual(snapshot.issues.first?.entityId, planId)
    }

    func testOfflineExpiryAllowsOnlyConfiguredGraceWindow() {
        let now = Date(timeIntervalSince1970: 2_000_000_000)
        let inside = now.addingTimeInterval(-OfflineSessionRestorePolicy.maximumGrace + 1).ISO8601Format()
        let boundary = now.addingTimeInterval(-OfflineSessionRestorePolicy.maximumGrace).ISO8601Format()
        let outside = now.addingTimeInterval(-OfflineSessionRestorePolicy.maximumGrace - 1).ISO8601Format()

        XCTAssertTrue(OfflineSessionRestorePolicy.canRestore(storedExpiry: inside, now: now))
        XCTAssertTrue(OfflineSessionRestorePolicy.canRestore(storedExpiry: boundary, now: now))
        XCTAssertFalse(OfflineSessionRestorePolicy.canRestore(storedExpiry: outside, now: now))
        XCTAssertFalse(OfflineSessionRestorePolicy.canRestore(storedExpiry: nil, now: now))
        XCTAssertFalse(OfflineSessionRestorePolicy.canRestore(storedExpiry: "not-a-date", now: now))
    }

    private func makeContext(_ name: String) throws -> TestContext {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceApp-\(name)-\(UUID().uuidString)", isDirectory: true)
        let suiteName = "FinanceApp.\(name).\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.set("device", forKey: "device-id")
        return TestContext(
            root: root,
            scope: LocalStoreScope(viewerUserId: "user-a"),
            deviceId: "device",
            store: FileBackedFinanceLocalStore(rootURL: root),
            deviceIdentityStore: DeviceIdentityStore(defaults: defaults, key: "device-id"),
            defaultsSuiteName: suiteName
        )
    }

    private func enqueuePersonalCategory(in context: TestContext) async throws -> PendingMutation {
        let entityId = UUID().uuidString
        let optimisticPayload = categoryPayload(id: entityId, name: "Food")
        let evidence = try PersonalSyncOwnershipValidator.evidence(
            scope: context.scope,
            entityType: .categories,
            entityId: entityId,
            ownershipPayload: optimisticPayload,
            snapshot: .empty(scope: context.scope, deviceId: context.deviceId)
        )
        let mutation = PendingMutation(
            deviceId: context.deviceId,
            scope: context.scope,
            entityType: .categories,
            entityId: entityId,
            operation: .create,
            payload: ["name": .string("Food"), "type": .string("expense"), "scope": .string("personal")],
            ownershipEvidence: evidence
        )
        try await context.store.commitOptimisticMutation(
            mutation,
            planningMetadata: nil,
            optimisticPayload: optimisticPayload
        )
        return mutation
    }

    private func mutation(
        context: TestContext,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: [String: SyncJSONValue]? = nil
    ) -> PendingMutation {
        PendingMutation(
            deviceId: context.deviceId,
            scope: context.scope,
            entityType: .categories,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: payload
        )
    }

    private func categoryPayload(id: String, name: String, version: Int? = nil) -> [String: SyncJSONValue] {
        var payload: [String: SyncJSONValue] = [
            "id": .string(id),
            "name": .string(name),
            "type": .string("expense"),
            "scope": .string("personal"),
            "ownerUserId": .string("user-a"),
            "householdId": .null,
            "iconKey": .null,
            "color": .null,
            "status": .string("active"),
        ]
        if let version { payload["version"] = .int(version) }
        return payload
    }

    private func planningPlanPayload(id: String, ownerUserId: String) -> [String: SyncJSONValue] {
        [
            "id": .string(id),
            "scope": .string("personal"),
            "ownerUserId": .string(ownerUserId),
            "householdId": .null,
            "month": .string("2026-08"),
            "currency": .string("RUB"),
            "version": .int(1),
        ]
    }

    private func change(
        seq: Int64,
        entityType: SyncEntityType,
        entityId: String,
        changeType: String = "create",
        payload: [String: SyncJSONValue]?,
        tombstonePayload: [String: SyncJSONValue]? = nil
    ) -> SyncChange {
        SyncChange(
            seq: seq,
            entityType: entityType,
            entityId: entityId,
            changeType: changeType,
            entityVersion: 1,
            entityUpdatedAt: "2026-08-21T10:00:00.000Z",
            changedByUserId: "user-a",
            clientMutationId: nil,
            payload: payload,
            tombstonePayload: tombstonePayload,
            createdAt: "2026-08-21T10:00:00.000Z"
        )
    }

    private func localRecord<Entity: Identifiable & Codable & Sendable>(
        _ entity: Entity,
        entityType: SyncEntityType
    ) -> LocalRecord<Entity> where Entity.ID == String {
        LocalRecord(
            entity: entity,
            metadata: LocalRecordMetadata(
                entityType: entityType,
                entityId: entity.id,
                serverVersion: 1,
                syncStatus: .synced,
                pendingMutationId: nil,
                updatedAt: "2026-08-21T10:00:00.000Z",
                lastSyncedAt: "2026-08-21T10:00:00.000Z"
            )
        )
    }
}

private struct TestContext {
    let root: URL
    let scope: LocalStoreScope
    let deviceId: String
    let store: FileBackedFinanceLocalStore
    let deviceIdentityStore: DeviceIdentityStore
    let defaultsSuiteName: String

    func cleanup() {
        try? FileManager.default.removeItem(at: root)
        UserDefaults.standard.removePersistentDomain(forName: defaultsSuiteName)
    }
}

private final class StubSyncApiClient: FinanceSyncApiClient, @unchecked Sendable {
    enum Mode {
        case networkFailure
        case mismatchedResult
        case pull(SyncPullResponse)
    }

    private let mode: Mode

    init(mode: Mode) {
        self.mode = mode
    }

    func syncPush(_ request: SyncPushRequest) async throws -> SyncPushResponse {
        switch mode {
        case .networkFailure:
            throw FinanceApiError.networkError(URLError(.notConnectedToInternet))
        case .mismatchedResult:
            let mutation = try XCTUnwrap(request.mutations.first)
            return SyncPushResponse(
                deviceId: request.deviceId,
                serverTime: "2026-08-21T10:00:00.000Z",
                results: [SyncMutationResult(
                    clientMutationId: mutation.clientMutationId,
                    entityType: mutation.entityType,
                    entityId: "different-entity-id",
                    operation: mutation.operation,
                    status: .applied,
                    serverVersion: 2,
                    changeSeq: 1,
                    errorCode: nil,
                    message: nil,
                    data: nil
                )]
            )
        case .pull:
            return SyncPushResponse(
                deviceId: request.deviceId,
                serverTime: "2026-08-21T10:00:00.000Z",
                results: []
            )
        }
    }

    func syncPull(_ request: SyncPullRequest) async throws -> SyncPullResponse {
        if case .pull(let response) = mode { return response }
        return SyncPullResponse(
            changes: [],
            nextCursor: request.cursor,
            hasMore: false,
            serverTime: "2026-08-21T10:00:00.000Z"
        )
    }
}

private final class StubURLProtocol: URLProtocol {
    struct Response {
        let statusCode: Int
        let body: String
    }

    static var response = Response(statusCode: 500, body: "{}")

    override class func canInit(with request: URLRequest) -> Bool {
        request.url?.host == "finance-tests.invalid"
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let url = request.url,
              let response = HTTPURLResponse(
                  url: url,
                  statusCode: Self.response.statusCode,
                  httpVersion: "HTTP/1.1",
                  headerFields: ["Content-Type": "application/json"]
              ) else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(Self.response.body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
