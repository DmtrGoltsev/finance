import Foundation

struct SyncPushSummary: Codable, Sendable {
    var pushed: Int = 0
    var applied: Int = 0
    var rejected: Int = 0
    var retry: Int = 0
    var failed: Int = 0
}

struct ManualSyncResult: Codable, Sendable {
    let push: SyncPushSummary
    let pulledChanges: Int
    let hasMorePullChanges: Bool
    let issues: [SyncIssue]
}

struct LocalSyncOverview: Codable, Sendable {
    let pendingCount: Int
    let issues: [SyncIssue]
    let lastError: String?

    static let empty = LocalSyncOverview(pendingCount: 0, issues: [], lastError: nil)
}

actor FinanceSyncService {
    private let apiClient: FinanceApiClient
    private let localStore: FinanceLocalStore
    private let deviceIdentityStore: DeviceIdentityStore

    init(
        apiClient: FinanceApiClient,
        localStore: FinanceLocalStore = FileBackedFinanceLocalStore(),
        deviceIdentityStore: DeviceIdentityStore = .shared
    ) {
        self.apiClient = apiClient
        self.localStore = localStore
        self.deviceIdentityStore = deviceIdentityStore
    }

    func syncNow(scope: LocalStoreScope, limit: Int = 100, entityTypes: [SyncEntityType]? = nil) async -> ManualSyncResult {
        let deviceId = deviceIdentityStore.deviceId()
        var pushSummary = SyncPushSummary()
        var pulledChanges = 0
        var hasMore = false

        do {
            pushSummary = try await pushPending(scope: scope, deviceId: deviceId, limit: limit)
            let pull = try await pullAndApply(scope: scope, deviceId: deviceId, limit: limit, entityTypes: entityTypes)
            pulledChanges = pull.changes.count
            hasMore = pull.hasMore
        } catch {
            let pending = (try? await localStore.pendingMutations(scope: scope, deviceId: deviceId, limit: limit)) ?? []
            for mutation in pending {
                try? await localStore.markFailed(
                    scope: scope,
                    deviceId: deviceId,
                    mutationId: mutation.clientMutationId,
                    message: error.localizedDescription
                )
            }
            pushSummary.failed += pending.count
            pushSummary.retry += pending.count
        }

        let issues = (try? await localStore.issues(scope: scope, deviceId: deviceId)) ?? []
        return ManualSyncResult(push: pushSummary, pulledChanges: pulledChanges, hasMorePullChanges: hasMore, issues: issues)
    }

    func retryIssue(scope: LocalStoreScope, issueId: String) async throws {
        try await localStore.retryIssue(scope: scope, deviceId: deviceIdentityStore.deviceId(), issueId: issueId)
    }

    func overview(scope: LocalStoreScope, limit: Int = 100) async -> LocalSyncOverview {
        let deviceId = deviceIdentityStore.deviceId()
        do {
            let snapshot = try await localStore.loadSnapshot(scope: scope, deviceId: deviceId)
            let pendingCount = snapshot.pendingMutations.filter(\.canPush).count
            return LocalSyncOverview(
                pendingCount: min(pendingCount, limit),
                issues: snapshot.issues,
                lastError: snapshot.syncState.lastError
            )
        } catch {
            return LocalSyncOverview(
                pendingCount: 0,
                issues: [],
                lastError: SyncSafeMessage.describe(error.localizedDescription)
            )
        }
    }

    func localSnapshot(scope: LocalStoreScope) async throws -> FinanceLocalSnapshot {
        try await localStore.loadSnapshot(scope: scope, deviceId: deviceIdentityStore.deviceId())
    }

    func enqueueMutation(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: [String: SyncJSONValue]? = nil,
        planningMetadata: PlanningMutationMetadata? = nil
    ) async throws {
        guard SyncQueuePolicy.isSyncable(entityType: entityType, operation: operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }
        let mutation = PendingMutation(
            deviceId: deviceIdentityStore.deviceId(),
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: payload
        )
        try await localStore.enqueueMutation(mutation, planningMetadata: planningMetadata)
    }

    func enqueueOptimisticMutation(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: [String: SyncJSONValue]? = nil,
        planningMetadata: PlanningMutationMetadata? = nil
    ) async throws {
        guard SyncQueuePolicy.isSyncable(entityType: entityType, operation: operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }

        let mutation = PendingMutation(
            deviceId: deviceIdentityStore.deviceId(),
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: payload
        )

        switch operation {
        case .delete, .archive:
            try await localStore.optimisticDelete(
                scope: scope,
                deviceId: mutation.deviceId,
                entityType: entityType,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                pendingMutationId: mutation.clientMutationId
            )
        case .create, .update, .restore, .confirm:
            if let payload {
                try await localStore.optimisticUpsert(
                    scope: scope,
                    deviceId: mutation.deviceId,
                    entityType: entityType,
                    entityId: entityId,
                    baseVersion: baseVersion,
                    pendingMutationId: mutation.clientMutationId,
                    payload: payload
                )
            }
        }

        try await localStore.enqueueMutation(mutation, planningMetadata: planningMetadata)
    }

    func enqueueOptimisticMutation<T: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        request: T,
        planningMetadata: PlanningMutationMetadata? = nil
    ) async throws {
        try await enqueueOptimisticMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: try SyncJSONValue.object(from: request),
            planningMetadata: planningMetadata
        )
    }

    func enqueueMutation<T: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        request: T,
        planningMetadata: PlanningMutationMetadata? = nil
    ) async throws {
        try await enqueueMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: try SyncJSONValue.object(from: request),
            planningMetadata: planningMetadata
        )
    }

    func enqueueOptimisticPlanningMutation(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: [String: SyncJSONValue]? = nil,
        planId: String?,
        month: String?,
        planningScope: PlanningScope?
    ) async throws {
        guard entityType.isPlanningEntity else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }
        guard SyncQueuePolicy.isSyncable(entityType: entityType, operation: operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }

        let mutation = PendingMutation(
            deviceId: deviceIdentityStore.deviceId(),
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: payload
        )
        let metadata = PlanningMutationMetadata(
            pendingMutationId: mutation.clientMutationId,
            planId: planId,
            month: month,
            scope: planningScope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            localModifiedAt: Date().ISO8601Format()
        )

        switch operation {
        case .delete, .archive:
            try await localStore.optimisticDelete(
                scope: scope,
                deviceId: mutation.deviceId,
                entityType: entityType,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                pendingMutationId: mutation.clientMutationId
            )
        case .create, .update, .restore, .confirm:
            if let payload {
                try await localStore.optimisticUpsert(
                    scope: scope,
                    deviceId: mutation.deviceId,
                    entityType: entityType,
                    entityId: entityId,
                    baseVersion: baseVersion,
                    pendingMutationId: mutation.clientMutationId,
                    payload: payload
                )
            }
        }

        try await localStore.enqueueMutation(mutation, planningMetadata: metadata)
    }

    func enqueueOptimisticPlanningMutation<T: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        request: T,
        planId: String?,
        month: String?,
        planningScope: PlanningScope?
    ) async throws {
        try await enqueueOptimisticPlanningMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: try SyncJSONValue.object(from: request),
            planId: planId,
            month: month,
            planningScope: planningScope
        )
    }

    func rejectOnlineOnlyOperation(_ operation: OnlineOnlySyncOperation) -> SyncIssue {
        let now = Date().ISO8601Format()
        return SyncIssue(
            id: "online-only-\(operation.rawValue)",
            mutationId: nil,
            entityType: nil,
            entityId: nil,
            operation: nil,
            status: .rejected,
            decision: .editOrDiscardOnly,
            title: "Операция доступна только онлайн",
            safeDescription: SyncQueuePolicy.onlineOnlyReason(operation),
            errorCode: "ONLINE_ONLY_OPERATION",
            attempts: 0,
            createdAt: now,
            updatedAt: now
        )
    }

    private func pushPending(scope: LocalStoreScope, deviceId: String, limit: Int) async throws -> SyncPushSummary {
        let loadedPending = try await localStore.pendingMutations(scope: scope, deviceId: deviceId, limit: limit)
        let blocked = loadedPending.filter { !isPersonalOnlyMutation($0) }
        for mutation in blocked {
            try await localStore.markRejected(
                scope: scope,
                deviceId: deviceId,
                mutationId: mutation.clientMutationId,
                issue: personalOnlyRejection(for: mutation)
            )
        }
        let pending = loadedPending.filter(isPersonalOnlyMutation)
        guard !pending.isEmpty else { return SyncPushSummary(rejected: blocked.count) }

        for mutation in pending {
            try await localStore.recordAttempt(scope: scope, deviceId: deviceId, mutationId: mutation.clientMutationId)
        }

        let response = try await apiClient.syncPush(
            SyncPushRequest(deviceId: deviceId, mutations: pending.map { $0.toSyncMutationRequest() })
        )

        var summary = SyncPushSummary(pushed: pending.count, rejected: blocked.count)
        let mutationsById = Dictionary(uniqueKeysWithValues: pending.map { ($0.clientMutationId, $0) })
        for result in response.results {
            guard let mutation = mutationsById[result.clientMutationId] else { continue }
            switch result.status {
            case .applied:
                try await localStore.markApplied(scope: scope, deviceId: deviceId, result: result)
                summary.applied += 1
            case .rejected:
                let issue = SyncIssue.rejected(from: mutation, result: result)
                try await localStore.markRejected(scope: scope, deviceId: deviceId, mutationId: result.clientMutationId, issue: issue)
                summary.rejected += 1
            }
        }

        let resultIds = Set(response.results.map(\.clientMutationId))
        for missing in pending where !resultIds.contains(missing.clientMutationId) {
            try await localStore.markFailed(
                scope: scope,
                deviceId: deviceId,
                mutationId: missing.clientMutationId,
                message: "Сервер не вернул результат синхронизации"
            )
            summary.retry += 1
        }
        return summary
    }

    private func pullAndApply(
        scope: LocalStoreScope,
        deviceId: String,
        limit: Int,
        entityTypes: [SyncEntityType]?
    ) async throws -> SyncPullResponse {
        let snapshot = try await localStore.loadSnapshot(scope: scope, deviceId: deviceId)
        let response = try await apiClient.syncPull(
            SyncPullRequest(
                deviceId: deviceId,
                cursor: snapshot.syncState.cursor,
                limit: limit,
                entityTypes: entityTypes
            )
        )
        let personalResponse = SyncPullResponse(
            changes: response.changes.filter(isPersonalOnlyChange),
            nextCursor: response.nextCursor,
            hasMore: response.hasMore,
            serverTime: response.serverTime
        )
        try await localStore.applyPullResponse(scope: scope, deviceId: deviceId, response: personalResponse)
        return personalResponse
    }

    private func isPersonalOnlyMutation(_ mutation: PendingMutation) -> Bool {
        guard let payload = mutation.payload else { return true }
        return isPersonalOnlyPayload(payload, entityType: mutation.entityType)
    }

    private func isPersonalOnlyChange(_ change: SyncChange) -> Bool {
        guard let payload = change.payload else { return true }
        return isPersonalOnlyPayload(payload, entityType: change.entityType)
    }

    private func isPersonalOnlyPayload(
        _ payload: [String: SyncJSONValue],
        entityType: SyncEntityType
    ) -> Bool {
        let hasNoHousehold = payload["householdId"] == nil || payload["householdId"] == .null
        switch entityType {
        case .accounts:
            return hasNoHousehold && stringValue(payload["ownershipType"]).map { $0 == OwnershipType.personal.rawValue } != false
        case .categories:
            return hasNoHousehold && stringValue(payload["scope"]).map { $0 == CategoryScope.personal.rawValue } != false
        case .assetCategories:
            return hasNoHousehold && stringValue(payload["scopeType"]).map { $0 == AssetCategoryScope.personal.rawValue } != false
        case .planningPlans:
            return hasNoHousehold && stringValue(payload["scope"]).map { $0 == PlanningScope.personal.rawValue } != false
        case .transactions, .investmentMigrations, .planningIncomeSources, .planningAllocations:
            return hasNoHousehold
        }
    }

    private func stringValue(_ value: SyncJSONValue?) -> String? {
        guard case .string(let string)? = value else { return nil }
        return string
    }

    private func personalOnlyRejection(for mutation: PendingMutation) -> SyncIssue {
        let now = Date().ISO8601Format()
        return SyncIssue(
            id: "issue-\(mutation.clientMutationId)",
            mutationId: mutation.clientMutationId,
            entityType: mutation.entityType,
            entityId: mutation.entityId,
            operation: mutation.operation,
            status: .rejected,
            decision: .editOrDiscardOnly,
            title: "Изменение не синхронизировано",
            safeDescription: "Приложение ведёт только личные финансы. Старое изменение другого типа можно удалить и создать заново.",
            errorCode: "PERSONAL_ONLY_SCOPE",
            attempts: mutation.attemptCount,
            createdAt: now,
            updatedAt: now
        )
    }
}
