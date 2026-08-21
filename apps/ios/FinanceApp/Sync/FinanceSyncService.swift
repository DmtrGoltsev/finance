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
    let requiresReauthentication: Bool
}

struct LocalSyncOverview: Codable, Sendable {
    let pendingCount: Int
    let issues: [SyncIssue]
    let lastError: String?

    static let empty = LocalSyncOverview(pendingCount: 0, issues: [], lastError: nil)
}

actor FinanceSyncService {
    private let apiClient: any FinanceSyncApiClient
    private let localStore: FinanceLocalStore
    private let deviceIdentityStore: DeviceIdentityStore

    init(
        apiClient: any FinanceSyncApiClient,
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
        var requiresReauthentication = false

        do {
            pushSummary = try await pushPending(scope: scope, deviceId: deviceId, limit: limit)
            let pull = try await pullAndApply(scope: scope, deviceId: deviceId, limit: limit, entityTypes: entityTypes)
            pulledChanges = pull.changes.count
            hasMore = pull.hasMore
        } catch {
            requiresReauthentication = SessionRestorePolicy.isConfirmedInvalidIdentity(error)
            if !requiresReauthentication {
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
        }

        let issues = (try? await localStore.issues(scope: scope, deviceId: deviceId)) ?? []
        return ManualSyncResult(
            push: pushSummary,
            pulledChanges: pulledChanges,
            hasMorePullChanges: hasMore,
            issues: issues,
            requiresReauthentication: requiresReauthentication
        )
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

    func enqueueOptimisticMutation<Request: Encodable, OptimisticEntity: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        request: Request,
        optimisticEntity: OptimisticEntity,
        ownershipContext: PersonalOwnershipContext = .empty,
        planningMetadata: PlanningMutationMetadata? = nil
    ) async throws {
        let queuePayload = try OfflineSyncPayloadContract.payload(
            entityType: entityType,
            operation: operation,
            request: request
        )
        try await enqueuePreparedMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            queuePayload: queuePayload,
            optimisticPayload: try SyncJSONValue.object(from: optimisticEntity),
            ownershipContext: ownershipContext,
            planningMetadata: planningMetadata
        )
    }

    func enqueueOptimisticMutation<OptimisticEntity: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        optimisticEntity: OptimisticEntity,
        ownershipContext: PersonalOwnershipContext = .empty,
        planningMetadata: PlanningMutationMetadata? = nil
    ) async throws {
        try OfflineSyncPayloadContract.validate(
            payload: nil,
            entityType: entityType,
            operation: operation
        )
        try await enqueuePreparedMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            queuePayload: nil,
            optimisticPayload: try SyncJSONValue.object(from: optimisticEntity),
            ownershipContext: ownershipContext,
            planningMetadata: planningMetadata
        )
    }

    func enqueueOptimisticPlanningMutation<Request: Encodable, OptimisticEntity: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        request: Request,
        optimisticEntity: OptimisticEntity,
        ownershipContext: PersonalOwnershipContext = .empty,
        planId: String?,
        month: String?,
        planningScope: PlanningScope?
    ) async throws {
        guard entityType.isPlanningEntity else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }
        let queuePayload = try OfflineSyncPayloadContract.payload(
            entityType: entityType,
            operation: operation,
            request: request,
            planId: planId
        )
        try await enqueuePreparedMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            queuePayload: queuePayload,
            optimisticPayload: try SyncJSONValue.object(from: optimisticEntity),
            ownershipContext: ownershipContext,
            planningContext: (planId, month, planningScope)
        )
    }

    func enqueueOptimisticPlanningMutation<OptimisticEntity: Encodable>(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        optimisticEntity: OptimisticEntity,
        ownershipContext: PersonalOwnershipContext = .empty,
        planId: String?,
        month: String?,
        planningScope: PlanningScope?
    ) async throws {
        guard entityType.isPlanningEntity else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }
        try OfflineSyncPayloadContract.validate(payload: nil, entityType: entityType, operation: operation)
        try await enqueuePreparedMutation(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            queuePayload: nil,
            optimisticPayload: try SyncJSONValue.object(from: optimisticEntity),
            ownershipContext: ownershipContext,
            planningContext: (planId, month, planningScope)
        )
    }

    private func enqueuePreparedMutation(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int?,
        queuePayload: [String: SyncJSONValue]?,
        optimisticPayload: [String: SyncJSONValue],
        ownershipContext: PersonalOwnershipContext,
        planningMetadata: PlanningMutationMetadata? = nil,
        planningContext: (planId: String?, month: String?, scope: PlanningScope?)? = nil
    ) async throws {
        guard SyncQueuePolicy.isSyncable(entityType: entityType, operation: operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: entityType.rawValue, operation: operation.rawValue)
        }
        try OfflineSyncPayloadContract.validateEnvelope(
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion
        )
        try OfflineSyncPayloadContract.validate(payload: queuePayload, entityType: entityType, operation: operation)

        let deviceId = deviceIdentityStore.deviceId()
        let snapshot = try await localStore.loadSnapshot(scope: scope, deviceId: deviceId)
        var ownershipPayload = optimisticPayload
        if let context = planningContext,
           context.scope == .personal,
           let planId = context.planId {
            ownershipPayload["planId"] = .string(planId)
        }
        let ownershipEvidence = try PersonalSyncOwnershipValidator.evidence(
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            ownershipPayload: ownershipPayload,
            snapshot: snapshot,
            trustedContext: ownershipContext
        )
        let mutation = PendingMutation(
            deviceId: deviceId,
            scope: scope,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: queuePayload,
            ownershipEvidence: ownershipEvidence
        )
        let metadata = planningContext.map { context in
            PlanningMutationMetadata(
                pendingMutationId: mutation.clientMutationId,
                planId: context.planId,
                month: context.month,
                scope: context.scope,
                entityType: entityType,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                localModifiedAt: Date().ISO8601Format()
            )
        } ?? planningMetadata

        try await localStore.commitOptimisticMutation(
            mutation,
            planningMetadata: metadata,
            optimisticPayload: optimisticPayload
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
        let snapshot = try await localStore.loadSnapshot(scope: scope, deviceId: deviceId)
        let loadedPending = try await localStore.pendingMutations(scope: scope, deviceId: deviceId, limit: limit)
        let blocked = loadedPending.filter { !Self.isPersonalOnlyMutation($0, snapshot: snapshot) }
        for mutation in blocked {
            try await localStore.markRejected(
                scope: scope,
                deviceId: deviceId,
                mutationId: mutation.clientMutationId,
                issue: personalOnlyRejection(for: mutation)
            )
        }
        let pending = loadedPending.filter { Self.isPersonalOnlyMutation($0, snapshot: snapshot) }
        guard !pending.isEmpty else { return SyncPushSummary(rejected: blocked.count) }

        for mutation in pending {
            try await localStore.recordAttempt(scope: scope, deviceId: deviceId, mutationId: mutation.clientMutationId)
        }

        let response = try await apiClient.syncPush(
            SyncPushRequest(deviceId: deviceId, mutations: pending.map { $0.toSyncMutationRequest() })
        )

        var summary = SyncPushSummary(pushed: pending.count, rejected: blocked.count)
        guard response.deviceId == deviceId else {
            for mutation in pending {
                try await localStore.markFailed(
                    scope: scope,
                    deviceId: deviceId,
                    mutationId: mutation.clientMutationId,
                    message: "Сервер вернул ответ для другого устройства"
                )
            }
            summary.failed += pending.count
            summary.retry += pending.count
            return summary
        }
        let mutationsById = Dictionary(uniqueKeysWithValues: pending.map { ($0.clientMutationId, $0) })
        var handledMutationIds = Set<String>()
        for result in response.results {
            guard let mutation = mutationsById[result.clientMutationId] else { continue }
            guard handledMutationIds.insert(result.clientMutationId).inserted,
                  SyncPushResultCorrelation.matches(result, mutation: mutation) else {
                try await localStore.markFailed(
                    scope: scope,
                    deviceId: deviceId,
                    mutationId: mutation.clientMutationId,
                    message: "Сервер вернул несогласованный результат синхронизации"
                )
                summary.failed += 1
                summary.retry += 1
                continue
            }
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

        for missing in pending where !handledMutationIds.contains(missing.clientMutationId) {
            try await localStore.markFailed(
                scope: scope,
                deviceId: deviceId,
                mutationId: missing.clientMutationId,
                message: "Сервер не вернул результат синхронизации"
            )
            summary.failed += 1
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
        var ownershipIndex = PersonalOwnershipIndex(snapshot: snapshot)
        var personalChanges: [SyncChange] = []
        var quarantined: [SyncPullQuarantine] = []
        for change in response.changes.sorted(by: { $0.seq < $1.seq }) {
            if PersonalSyncOwnershipValidator.allows(
                    change: change,
                    snapshot: snapshot,
                    index: ownershipIndex
                ) {
                personalChanges.append(change)
                ownershipIndex.recordAccepted(change)
            } else {
                quarantined.append(.personalScope(change))
            }
        }
        let personalResponse = SyncPullResponse(
            changes: personalChanges,
            nextCursor: response.nextCursor,
            hasMore: response.hasMore,
            serverTime: response.serverTime
        )
        try await localStore.applyPullPage(
            scope: scope,
            deviceId: deviceId,
            response: personalResponse,
            quarantined: quarantined
        )
        return personalResponse
    }

    static func isPersonalOnlyMutation(
        _ mutation: PendingMutation,
        snapshot: FinanceLocalSnapshot
    ) -> Bool {
        PersonalSyncOwnershipValidator.allows(mutation: mutation, snapshot: snapshot)
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
