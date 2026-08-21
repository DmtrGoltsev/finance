import Foundation

struct LocalStoreScope: Codable, Hashable, Sendable {
    let viewerUserId: String
    let sessionId: String?
    let householdId: String?
    let accessVersion: String?

    init(viewerUserId: String, sessionId: String? = nil, householdId: String? = nil, accessVersion: String? = nil) {
        self.viewerUserId = viewerUserId
        self.sessionId = sessionId
        self.householdId = householdId
        self.accessVersion = accessVersion
    }

    static func fromSession(_ session: SessionStatus, fallbackUserId: String) -> LocalStoreScope {
        LocalStoreScope(
            viewerUserId: session.userId ?? fallbackUserId,
            sessionId: nil,
            householdId: nil,
            accessVersion: nil
        )
    }

    var storageKey: String {
        [viewerUserId, accessVersion]
            .compactMap { $0?.nilIfBlank }
            .map(Self.storageComponent)
            .joined(separator: "_")
    }

    var legacyUserStoragePrefix: String {
        Self.storageComponent(viewerUserId)
    }

    private static func storageComponent(_ value: String) -> String {
        value.map { char in
            char.isLetter || char.isNumber || char == "-" || char == "_" ? char : "_"
        }.reduce(into: "") { $0.append($1) }
    }
}

enum LocalRecordSyncStatus: String, Codable, Sendable {
    case synced
    case pending
    case retry
    case failed
    case rejected
}

struct LocalRecordMetadata: Codable, Sendable {
    let entityType: SyncEntityType
    let entityId: String
    var serverVersion: Int?
    var syncStatus: LocalRecordSyncStatus
    var pendingMutationId: String?
    var updatedAt: String
    var lastSyncedAt: String?
}

struct LocalRecord<Entity: Codable & Sendable>: Codable, Sendable {
    var entity: Entity
    var metadata: LocalRecordMetadata
}

struct SyncTombstone: Codable, Identifiable, Sendable {
    var id: String { "\(entityType.rawValue):\(entityId)" }
    let entityType: SyncEntityType
    let entityId: String
    let operation: SyncOperation
    let baseVersion: Int?
    let pendingMutationId: String?
    let createdAt: String
    let safeError: String?
}

struct PlanningMutationMetadata: Codable, Identifiable, Sendable {
    var id: String { pendingMutationId }
    let pendingMutationId: String
    let planId: String?
    let month: String?
    let scope: PlanningScope?
    let entityType: SyncEntityType
    let entityId: String
    let operation: SyncOperation
    let baseVersion: Int?
    let localModifiedAt: String
}

enum PendingMutationStatus: String, Codable, Sendable {
    case queued
    case retry
    case applied
    case rejected
    case failed
}

struct PendingMutation: Codable, Identifiable, Sendable {
    var id: String { clientMutationId }
    let clientMutationId: String
    let deviceId: String
    var scope: LocalStoreScope
    let entityType: SyncEntityType
    let entityId: String
    var operation: SyncOperation
    var baseVersion: Int?
    var payload: [String: SyncJSONValue]?
    let ownershipEvidence: SyncOwnershipEvidence?
    var status: PendingMutationStatus
    var attemptCount: Int
    let createdAt: String
    var updatedAt: String
    var lastAttemptAt: String?
    var lastError: String?

    init(
        clientMutationId: String = UUID().uuidString,
        deviceId: String,
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int? = nil,
        payload: [String: SyncJSONValue]? = nil,
        ownershipEvidence: SyncOwnershipEvidence? = nil,
        status: PendingMutationStatus = .queued
    ) {
        let now = Date().ISO8601Format()
        self.clientMutationId = clientMutationId
        self.deviceId = deviceId
        self.scope = scope
        self.entityType = entityType
        self.entityId = entityId
        self.operation = operation
        self.baseVersion = baseVersion
        self.payload = payload
        self.ownershipEvidence = ownershipEvidence
        self.status = status
        self.attemptCount = 0
        self.createdAt = now
        self.updatedAt = now
        self.lastAttemptAt = nil
        self.lastError = nil
    }

    var canPush: Bool {
        (status == .queued || status == .retry) && SyncQueuePolicy.isSyncable(entityType: entityType, operation: operation)
    }

    func toSyncMutationRequest() -> SyncMutationRequest {
        SyncMutationRequest(
            clientMutationId: clientMutationId,
            entityType: entityType,
            entityId: entityId,
            operation: operation,
            baseVersion: baseVersion,
            payload: payload
        )
    }
}

struct LocalSyncState: Codable, Sendable {
    var deviceId: String
    var cursor: Int64
    var lastPulledAt: String?
    var lastPushedAt: String?
    var isSyncing: Bool
    var lastError: String?
    var issueIds: [String]

    static func initial(deviceId: String) -> LocalSyncState {
        LocalSyncState(
            deviceId: deviceId,
            cursor: 0,
            lastPulledAt: nil,
            lastPushedAt: nil,
            isSyncing: false,
            lastError: nil,
            issueIds: []
        )
    }
}

struct FinanceLocalSnapshot: Codable, Sendable {
    var schemaVersion: Int
    var scope: LocalStoreScope
    var updatedAt: String
    var accounts: [LocalRecord<Account>]
    var categories: [LocalRecord<Category>]
    var assetCategories: [LocalRecord<AssetCategory>]
    var transactions: [LocalRecord<Transaction>]
    var planningPlans: [LocalRecord<PlanningPlan>]
    var planningIncomeSources: [LocalRecord<PlanningIncomeSource>]
    var planningAllocations: [LocalRecord<PlanningAllocation>]
    var planningMutationMetadata: [PlanningMutationMetadata]
    var tombstones: [SyncTombstone]
    var pendingMutations: [PendingMutation]
    var syncState: LocalSyncState
    var issues: [SyncIssue]

    static func empty(scope: LocalStoreScope, deviceId: String) -> FinanceLocalSnapshot {
        FinanceLocalSnapshot(
            schemaVersion: financeSyncSchemaVersion,
            scope: scope,
            updatedAt: Date().ISO8601Format(),
            accounts: [],
            categories: [],
            assetCategories: [],
            transactions: [],
            planningPlans: [],
            planningIncomeSources: [],
            planningAllocations: [],
            planningMutationMetadata: [],
            tombstones: [],
            pendingMutations: [],
            syncState: .initial(deviceId: deviceId),
            issues: []
        )
    }
}

struct SyncPullQuarantine: Sendable {
    let change: SyncChange
    let errorCode: String
    let safeDescription: String

    static func personalScope(_ change: SyncChange) -> SyncPullQuarantine {
        SyncPullQuarantine(
            change: change,
            errorCode: "PERSONAL_ONLY_PULL_QUARANTINED",
            safeDescription: "Личная принадлежность изменения не подтверждена. Данные не применены локально."
        )
    }
}

protocol FinanceLocalStore: Sendable {
    func loadSnapshot(scope: LocalStoreScope, deviceId: String) async throws -> FinanceLocalSnapshot
    func saveSnapshot(_ snapshot: FinanceLocalSnapshot) async throws
    func enqueueMutation(_ mutation: PendingMutation, planningMetadata: PlanningMutationMetadata?) async throws
    func commitOptimisticMutation(_ mutation: PendingMutation, planningMetadata: PlanningMutationMetadata?, optimisticPayload: [String: SyncJSONValue]) async throws
    func optimisticUpsert(scope: LocalStoreScope, deviceId: String, entityType: SyncEntityType, entityId: String, baseVersion: Int?, pendingMutationId: String?, payload: [String: SyncJSONValue]) async throws
    func optimisticDelete(scope: LocalStoreScope, deviceId: String, entityType: SyncEntityType, entityId: String, operation: SyncOperation, baseVersion: Int?, pendingMutationId: String?) async throws
    func compactAppliedMutations(scope: LocalStoreScope, deviceId: String) async throws -> Int
    func pendingMutations(scope: LocalStoreScope, deviceId: String, limit: Int) async throws -> [PendingMutation]
    func recordAttempt(scope: LocalStoreScope, deviceId: String, mutationId: String) async throws
    func markApplied(scope: LocalStoreScope, deviceId: String, result: SyncMutationResult) async throws
    func markRejected(scope: LocalStoreScope, deviceId: String, mutationId: String, issue: SyncIssue) async throws
    func markFailed(scope: LocalStoreScope, deviceId: String, mutationId: String, message: String?) async throws
    func retryIssue(scope: LocalStoreScope, deviceId: String, issueId: String) async throws
    func applyPullResponse(scope: LocalStoreScope, deviceId: String, response: SyncPullResponse) async throws
    func applyPullPage(scope: LocalStoreScope, deviceId: String, response: SyncPullResponse, quarantined: [SyncPullQuarantine]) async throws
    func quarantinePullChanges(scope: LocalStoreScope, deviceId: String, changes: [SyncChange]) async throws
    func issues(scope: LocalStoreScope, deviceId: String) async throws -> [SyncIssue]
    func wipe(scope: LocalStoreScope) async throws
    func wipeAllProtectedData() async throws
}

actor FileBackedFinanceLocalStore: FinanceLocalStore {
    static let snapshotWritingOptions: Data.WritingOptions = [
        .atomic,
        .completeFileProtectionUntilFirstUserAuthentication,
    ]

    private let rootURL: URL
    private let fileManager: FileManager
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(rootURL: URL? = nil, fileManager: FileManager = .default) {
        self.fileManager = fileManager
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory
        self.rootURL = rootURL ?? appSupport.appendingPathComponent("FinanceApp/OfflineStore", isDirectory: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        self.encoder = encoder
        self.decoder = JSONDecoder()
    }

    func loadSnapshot(scope: LocalStoreScope, deviceId: String) async throws -> FinanceLocalSnapshot {
        guard !scope.viewerUserId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              scope.householdId == nil else {
            throw LocalStoreError.accountScopeMismatch
        }
        try ensureRootExists()
        let url = snapshotURL(scope: scope)
        guard fileManager.fileExists(atPath: url.path) else {
            if let migrated = try await migrateLegacySnapshots(scope: scope, deviceId: deviceId) {
                return migrated
            }
            return .empty(scope: scope, deviceId: deviceId)
        }
        try protectAndExcludeFromBackup(url)
        let data = try Data(contentsOf: url)
        var snapshot = try decoder.decode(FinanceLocalSnapshot.self, from: data)
        guard snapshot.scope.viewerUserId == scope.viewerUserId,
              snapshot.scope.accessVersion == scope.accessVersion,
              snapshot.scope.householdId == nil,
              scope.householdId == nil else {
            throw LocalStoreError.accountScopeMismatch
        }
        if snapshot.syncState.deviceId != deviceId {
            snapshot.syncState.deviceId = deviceId
        }
        return snapshot
    }

    func saveSnapshot(_ snapshot: FinanceLocalSnapshot) async throws {
        guard !snapshot.scope.viewerUserId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              snapshot.scope.householdId == nil else {
            throw LocalStoreError.accountScopeMismatch
        }
        try ensureRootExists()
        var snapshot = snapshot
        snapshot.updatedAt = Date().ISO8601Format()
        let data = try encoder.encode(snapshot)
        let url = snapshotURL(scope: snapshot.scope)
        try data.write(to: url, options: Self.snapshotWritingOptions)
        try protectAndExcludeFromBackup(url)
    }

    func enqueueMutation(_ mutation: PendingMutation, planningMetadata: PlanningMutationMetadata? = nil) async throws {
        var snapshot = try await loadSnapshot(scope: mutation.scope, deviceId: mutation.deviceId)
        guard SyncQueuePolicy.isSyncable(entityType: mutation.entityType, operation: mutation.operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: mutation.entityType.rawValue, operation: mutation.operation.rawValue)
        }
        snapshot.pendingMutations.append(mutation)
        if let planningMetadata {
            snapshot.planningMutationMetadata.append(planningMetadata)
        }
        if (mutation.operation == .delete || mutation.operation == .archive),
           !snapshot.tombstones.contains(where: { $0.pendingMutationId == mutation.clientMutationId }) {
            snapshot.tombstones.append(
                SyncTombstone(
                    entityType: mutation.entityType,
                    entityId: mutation.entityId,
                    operation: mutation.operation,
                    baseVersion: mutation.baseVersion,
                    pendingMutationId: mutation.clientMutationId,
                    createdAt: Date().ISO8601Format(),
                    safeError: nil
                )
            )
        }
        try await saveSnapshot(snapshot)
    }

    func optimisticUpsert(
        scope: LocalStoreScope,
        deviceId: String,
        entityType: SyncEntityType,
        entityId: String,
        baseVersion: Int? = nil,
        pendingMutationId: String?,
        payload: [String: SyncJSONValue]
    ) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        try applyPayload(
            payload,
            entityType: entityType,
            entityId: entityId,
            version: baseVersion,
            syncStatus: .pending,
            pendingMutationId: pendingMutationId,
            to: &snapshot
        )
        try await saveSnapshot(snapshot)
    }

    func optimisticDelete(
        scope: LocalStoreScope,
        deviceId: String,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation = .delete,
        baseVersion: Int? = nil,
        pendingMutationId: String?
    ) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        snapshot.tombstones.append(
            SyncTombstone(
                entityType: entityType,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                pendingMutationId: pendingMutationId,
                createdAt: Date().ISO8601Format(),
                safeError: nil
            )
        )
        removeEntity(entityType: entityType, entityId: entityId, from: &snapshot)
        try await saveSnapshot(snapshot)
    }

    func compactAppliedMutations(scope: LocalStoreScope, deviceId: String) async throws -> Int {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        let removed = compactAppliedMutations(in: &snapshot)
        if removed > 0 {
            try await saveSnapshot(snapshot)
        }
        return removed
    }

    func pendingMutations(scope: LocalStoreScope, deviceId: String, limit: Int = 100) async throws -> [PendingMutation] {
        let snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        var entityKeys = Set<String>()
        var ready: [PendingMutation] = []
        for mutation in snapshot.pendingMutations where mutation.canPush {
            let entityKey = "\(mutation.entityType.rawValue):\(mutation.entityId)"
            // A later update for the same record must wait for the server
            // version returned by its predecessor.
            guard entityKeys.insert(entityKey).inserted else { continue }
            ready.append(mutation)
            if ready.count == limit { break }
        }
        return ready
    }

    func recordAttempt(scope: LocalStoreScope, deviceId: String, mutationId: String) async throws {
        try await updateMutation(scope: scope, deviceId: deviceId, mutationId: mutationId) { mutation in
            mutation.attemptCount += 1
            mutation.lastAttemptAt = Date().ISO8601Format()
            mutation.updatedAt = mutation.lastAttemptAt ?? mutation.updatedAt
        }
    }

    func markApplied(scope: LocalStoreScope, deviceId: String, result: SyncMutationResult) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        var hasOptimisticSuccessor = false
        if let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == result.clientMutationId }) {
            snapshot.pendingMutations[index].status = .applied
            snapshot.pendingMutations[index].lastError = nil
            snapshot.pendingMutations[index].updatedAt = Date().ISO8601Format()
            if let successorIndex = snapshot.pendingMutations.indices.first(where: {
                $0 > index &&
                    snapshot.pendingMutations[$0].entityType == result.entityType &&
                    snapshot.pendingMutations[$0].entityId == result.entityId &&
                    snapshot.pendingMutations[$0].canPush
            }) {
                hasOptimisticSuccessor = true
                if let serverVersion = result.serverVersion {
                    snapshot.pendingMutations[successorIndex].baseVersion = serverVersion
                }
                snapshot.pendingMutations[successorIndex].updatedAt = Date().ISO8601Format()
            }
        }
        snapshot.issues.removeAll { $0.mutationId == result.clientMutationId }
        snapshot.syncState.issueIds = snapshot.issues.map(\.id)
        if let data = result.data, !hasOptimisticSuccessor {
            try? applyPayload(data, entityType: result.entityType, entityId: result.entityId, version: result.serverVersion, to: &snapshot)
        }
        if result.operation == .delete || result.operation == .archive || result.operation == .restore {
            snapshot.tombstones.removeAll { $0.entityType == result.entityType && $0.entityId == result.entityId }
        }
        _ = compactAppliedMutations(in: &snapshot)
        try await saveSnapshot(snapshot)
    }

    func markRejected(scope: LocalStoreScope, deviceId: String, mutationId: String, issue: SyncIssue) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        if let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) {
            snapshot.pendingMutations[index].status = .rejected
            snapshot.pendingMutations[index].lastError = issue.safeDescription
            snapshot.pendingMutations[index].updatedAt = Date().ISO8601Format()
        }
        upsertIssue(issue, in: &snapshot)
        try await saveSnapshot(snapshot)
    }

    func markFailed(scope: LocalStoreScope, deviceId: String, mutationId: String, message: String?) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        guard let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) else { return }
        snapshot.pendingMutations[index].status = .retry
        snapshot.pendingMutations[index].lastError = SyncSafeMessage.describe(message)
        snapshot.pendingMutations[index].updatedAt = Date().ISO8601Format()
        let issue = SyncIssue.failed(from: snapshot.pendingMutations[index], message: message)
        upsertIssue(issue, in: &snapshot)
        try await saveSnapshot(snapshot)
    }

    func retryIssue(scope: LocalStoreScope, deviceId: String, issueId: String) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        guard let issue = snapshot.issues.first(where: { $0.id == issueId }),
              issue.decision == .retryAllowed,
              let mutationId = issue.mutationId,
              let mutationIndex = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) else {
            return
        }
        snapshot.pendingMutations[mutationIndex].status = .retry
        snapshot.pendingMutations[mutationIndex].lastError = nil
        snapshot.pendingMutations[mutationIndex].updatedAt = Date().ISO8601Format()
        snapshot.issues.removeAll { $0.id == issueId }
        snapshot.syncState.issueIds = snapshot.issues.map(\.id)
        try await saveSnapshot(snapshot)
    }

    func applyPullResponse(scope: LocalStoreScope, deviceId: String, response: SyncPullResponse) async throws {
        try await applyPullPage(
            scope: scope,
            deviceId: deviceId,
            response: response,
            quarantined: []
        )
    }

    func applyPullPage(
        scope: LocalStoreScope,
        deviceId: String,
        response: SyncPullResponse,
        quarantined: [SyncPullQuarantine]
    ) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        for change in response.changes.sorted(by: { $0.seq < $1.seq }) {
            do {
                try applyPullChange(change, to: &snapshot)
            } catch {
                addQuarantine(
                    SyncPullQuarantine(
                        change: change,
                        errorCode: "PULL_CHANGE_DECODE_FAILED",
                        safeDescription: "Серверное изменение не удалось безопасно декодировать и не было применено."
                    ),
                    to: &snapshot
                )
            }
        }
        for item in quarantined {
            addQuarantine(item, to: &snapshot)
        }

        let handledSequences = (response.changes.map(\.seq) + quarantined.map { $0.change.seq }).sorted()
        let hasUniqueSequences = Set(handledSequences).count == handledSequences.count
        let expectedCursor = handledSequences.last ?? snapshot.syncState.cursor
        guard hasUniqueSequences,
              response.nextCursor == expectedCursor,
              response.nextCursor >= snapshot.syncState.cursor else {
            let now = Date().ISO8601Format()
            upsertIssue(
                SyncIssue(
                    id: "pull-cursor-unsafe-\(response.nextCursor)",
                    mutationId: nil,
                    entityType: nil,
                    entityId: nil,
                    operation: nil,
                    status: .failed,
                    decision: .retryAllowed,
                    title: "Курсор синхронизации не принят",
                    safeDescription: "Ответ сервера содержал небезопасный курсор. Локальные данные не удалены, повторите синхронизацию.",
                    errorCode: "PULL_CURSOR_UNSAFE",
                    attempts: 0,
                    createdAt: now,
                    updatedAt: now
                ),
                in: &snapshot
            )
            try await saveSnapshot(snapshot)
            return
        }

        snapshot.syncState.cursor = response.nextCursor
        snapshot.syncState.lastPulledAt = response.serverTime
        snapshot.syncState.lastError = nil
        try await saveSnapshot(snapshot)
    }

    func commitOptimisticMutation(
        _ mutation: PendingMutation,
        planningMetadata: PlanningMutationMetadata? = nil,
        optimisticPayload: [String: SyncJSONValue]
    ) async throws {
        var snapshot = try await loadSnapshot(scope: mutation.scope, deviceId: mutation.deviceId)
        guard SyncQueuePolicy.isSyncable(entityType: mutation.entityType, operation: mutation.operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(entityType: mutation.entityType.rawValue, operation: mutation.operation.rawValue)
        }

        if let createIndex = snapshot.pendingMutations.lastIndex(where: {
            $0.entityType == mutation.entityType && $0.entityId == mutation.entityId && $0.operation == .create && $0.canPush
        }) {
            switch mutation.operation {
            case .update, .restore, .confirm:
                var create = snapshot.pendingMutations[createIndex]
                create.payload = mergeCreatePayload(create.payload, with: mutation.payload)
                create.updatedAt = Date().ISO8601Format()
                snapshot.pendingMutations[createIndex] = create
                try applyPayload(
                    optimisticPayload,
                    entityType: mutation.entityType,
                    entityId: mutation.entityId,
                    version: nil,
                    syncStatus: .pending,
                    pendingMutationId: create.clientMutationId,
                    to: &snapshot
                )
                try await saveSnapshot(snapshot)
                return
            case .delete, .archive:
                let createMutationId = snapshot.pendingMutations[createIndex].clientMutationId
                snapshot.pendingMutations.remove(at: createIndex)
                snapshot.planningMutationMetadata.removeAll { $0.pendingMutationId == createMutationId }
                snapshot.tombstones.removeAll { $0.pendingMutationId == createMutationId }
                removeEntity(entityType: mutation.entityType, entityId: mutation.entityId, from: &snapshot)
                try await saveSnapshot(snapshot)
                return
            case .create:
                break
            }
        }

        switch mutation.operation {
        case .delete, .archive:
            addTombstone(
                entityType: mutation.entityType,
                entityId: mutation.entityId,
                operation: mutation.operation,
                baseVersion: mutation.baseVersion,
                pendingMutationId: mutation.clientMutationId,
                to: &snapshot
            )
            removeEntity(entityType: mutation.entityType, entityId: mutation.entityId, from: &snapshot)
        case .create, .update, .restore, .confirm:
            try applyPayload(
                optimisticPayload,
                entityType: mutation.entityType,
                entityId: mutation.entityId,
                version: mutation.baseVersion,
                syncStatus: .pending,
                pendingMutationId: mutation.clientMutationId,
                to: &snapshot
            )
        }
        snapshot.pendingMutations.append(mutation)
        if let planningMetadata {
            snapshot.planningMutationMetadata.append(planningMetadata)
        }
        try await saveSnapshot(snapshot)
    }

    func quarantinePullChanges(
        scope: LocalStoreScope,
        deviceId: String,
        changes: [SyncChange]
    ) async throws {
        guard !changes.isEmpty else { return }
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        for change in changes {
            let now = Date().ISO8601Format()
            upsertIssue(
                SyncIssue(
                    id: "quarantine-\(change.seq)-\(change.entityType.rawValue)-\(change.entityId)",
                    mutationId: nil,
                    entityType: change.entityType,
                    entityId: change.entityId,
                    operation: SyncOperation(rawValue: change.changeType),
                    status: .rejected,
                    decision: .editOrDiscardOnly,
                    title: "Серверное изменение изолировано",
                    safeDescription: "Личная принадлежность изменения не подтверждена. Данные не применены локально.",
                    errorCode: "PERSONAL_ONLY_PULL_QUARANTINED",
                    attempts: 0,
                    createdAt: now,
                    updatedAt: now
                ),
                in: &snapshot
            )
        }
        snapshot.syncState.issueIds = snapshot.issues.map(\.id)
        try await saveSnapshot(snapshot)
    }

    func issues(scope: LocalStoreScope, deviceId: String) async throws -> [SyncIssue] {
        (try await loadSnapshot(scope: scope, deviceId: deviceId)).issues
    }

    func wipe(scope: LocalStoreScope) async throws {
        guard fileManager.fileExists(atPath: rootURL.path) else { return }
        let currentName = snapshotURL(scope: scope).lastPathComponent
        let legacyPrefix = "\(scope.legacyUserStoragePrefix)_"
        let urls = try fileManager.contentsOfDirectory(
            at: rootURL,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        )
        for url in urls where url.pathExtension == "json" {
            let fileName = url.lastPathComponent
            let belongsByName = fileName == currentName || fileName.hasPrefix(legacyPrefix)
            let belongsBySnapshot: Bool
            if let data = try? Data(contentsOf: url),
               let snapshot = try? decoder.decode(FinanceLocalSnapshot.self, from: data) {
                belongsBySnapshot = snapshot.scope.viewerUserId == scope.viewerUserId
            } else {
                belongsBySnapshot = false
            }
            if belongsByName || belongsBySnapshot {
                try fileManager.removeItem(at: url)
            }
        }
    }

    func wipeAllProtectedData() async throws {
        if fileManager.fileExists(atPath: rootURL.path) {
            try fileManager.removeItem(at: rootURL)
        }
    }

    private func updateMutation(
        scope: LocalStoreScope,
        deviceId: String,
        mutationId: String,
        transform: (inout PendingMutation) -> Void
    ) async throws {
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        guard let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) else { return }
        transform(&snapshot.pendingMutations[index])
        try await saveSnapshot(snapshot)
    }

    private func upsertIssue(_ issue: SyncIssue, in snapshot: inout FinanceLocalSnapshot) {
        if let index = snapshot.issues.firstIndex(where: { $0.id == issue.id }) {
            snapshot.issues[index] = issue
        } else {
            snapshot.issues.append(issue)
        }
        snapshot.syncState.issueIds = snapshot.issues.map(\.id)
    }

    private func applyPayload(
        _ payload: [String: SyncJSONValue],
        entityType: SyncEntityType,
        entityId: String,
        version: Int?,
        syncStatus: LocalRecordSyncStatus = .synced,
        pendingMutationId: String? = nil,
        to snapshot: inout FinanceLocalSnapshot
    ) throws {
        if hasPendingTombstone(entityType: entityType, entityId: entityId, in: snapshot) {
            return
        }
        snapshot.tombstones.removeAll {
            $0.entityType == entityType && $0.entityId == entityId && $0.pendingMutationId == nil
        }
        switch entityType {
        case .transactions:
            let entity: Transaction = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.transactions)
        case .accounts:
            let entity: Account = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.accounts)
        case .categories:
            let entity: Category = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.categories)
        case .assetCategories:
            let entity: AssetCategory = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.assetCategories)
        case .planningPlans:
            let existing = snapshot.planningPlans.first(where: { $0.metadata.entityId == entityId })?.entity
            let entity = try PlanningDomainChangeDTO.plan(from: payload, existing: existing)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.planningPlans)
        case .planningIncomeSources:
            let entity = try PlanningDomainChangeDTO.incomeSource(from: payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.planningIncomeSources)
            mergeIncomeSource(entity, into: &snapshot)
        case .planningAllocations:
            let entity = try PlanningDomainChangeDTO.allocation(from: payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.planningAllocations)
            mergeAllocation(entity, into: &snapshot)
        case .investmentMigrations:
            break
        }
    }

    private func applyTombstone(_ change: SyncChange, to snapshot: inout FinanceLocalSnapshot) {
        addTombstone(
            entityType: change.entityType,
            entityId: change.entityId,
            operation: .delete,
            baseVersion: change.entityVersion,
            pendingMutationId: nil,
            createdAt: change.createdAt,
            to: &snapshot
        )
        removeEntity(entityType: change.entityType, entityId: change.entityId, from: &snapshot)
    }

    private func hasPendingTombstone(entityType: SyncEntityType, entityId: String, in snapshot: FinanceLocalSnapshot) -> Bool {
        snapshot.tombstones.contains { tombstone in
            tombstone.entityType == entityType &&
            tombstone.entityId == entityId &&
            tombstone.pendingMutationId != nil
        }
    }

    private func applyPullChange(_ change: SyncChange, to snapshot: inout FinanceLocalSnapshot) throws {
        if change.tombstonePayload != nil || change.changeType == "delete" || change.changeType == "archive" {
            applyTombstone(change, to: &snapshot)
            return
        }
        guard let payload = change.payload else {
            throw LocalStoreError.invalidPullPayload("Missing payload for \(change.entityType.rawValue) \(change.changeType)")
        }
        try applyPayload(
            payload,
            entityType: change.entityType,
            entityId: change.entityId,
            version: change.entityVersion,
            to: &snapshot
        )
    }

    private func addQuarantine(_ quarantine: SyncPullQuarantine, to snapshot: inout FinanceLocalSnapshot) {
        let now = Date().ISO8601Format()
        upsertIssue(
            SyncIssue(
                id: "quarantine-\(quarantine.change.seq)-\(quarantine.change.entityType.rawValue)-\(quarantine.change.entityId)",
                mutationId: nil,
                entityType: quarantine.change.entityType,
                entityId: quarantine.change.entityId,
                operation: SyncOperation(rawValue: quarantine.change.changeType),
                status: .rejected,
                decision: .editOrDiscardOnly,
                title: "Серверное изменение изолировано",
                safeDescription: quarantine.safeDescription,
                errorCode: quarantine.errorCode,
                attempts: 0,
                createdAt: now,
                updatedAt: now
            ),
            in: &snapshot
        )
    }

    private func addTombstone(
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int?,
        pendingMutationId: String?,
        createdAt: String = Date().ISO8601Format(),
        to snapshot: inout FinanceLocalSnapshot
    ) {
        snapshot.tombstones.removeAll {
            $0.entityType == entityType && $0.entityId == entityId && $0.pendingMutationId == pendingMutationId
        }
        snapshot.tombstones.append(
            SyncTombstone(
                entityType: entityType,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                pendingMutationId: pendingMutationId,
                createdAt: createdAt,
                safeError: nil
            )
        )
    }

    private func mergeCreatePayload(
        _ createPayload: [String: SyncJSONValue]?,
        with newerPayload: [String: SyncJSONValue]?
    ) -> [String: SyncJSONValue]? {
        guard var createPayload else { return newerPayload }
        for (key, value) in newerPayload ?? [:] {
            createPayload[key] = value
        }
        return createPayload
    }

    private func validateEntityId(
        _ actual: String,
        expected: String,
        entityType: SyncEntityType
    ) throws {
        guard actual == expected else {
            throw LocalStoreError.invalidPullPayload("\(entityType.rawValue) id does not match sync envelope")
        }
    }

    private func mergeIncomeSource(_ source: PlanningIncomeSource, into snapshot: inout FinanceLocalSnapshot) {
        guard let index = snapshot.planningPlans.firstIndex(where: { $0.entity.id == source.planId }) else { return }
        let record = snapshot.planningPlans[index]
        var sources = record.entity.incomeSources
        if let sourceIndex = sources.firstIndex(where: { $0.id == source.id }) {
            sources[sourceIndex] = source
        } else {
            sources.append(source)
        }
        snapshot.planningPlans[index].entity = PlanningPlan(
            id: record.entity.id,
            scope: record.entity.scope,
            ownerUserId: record.entity.ownerUserId,
            month: record.entity.month,
            currency: record.entity.currency,
            householdId: record.entity.householdId,
            summary: record.entity.summary,
            incomeSources: sources,
            allocations: record.entity.allocations,
            version: record.entity.version
        )
    }

    private func mergeAllocation(_ allocation: PlanningAllocation, into snapshot: inout FinanceLocalSnapshot) {
        guard let index = snapshot.planningPlans.firstIndex(where: { $0.entity.id == allocation.planId }) else { return }
        let record = snapshot.planningPlans[index]
        var allocations = record.entity.allocations
        if let allocationIndex = allocations.firstIndex(where: { $0.id == allocation.id }) {
            allocations[allocationIndex] = allocation
        } else {
            allocations.append(allocation)
        }
        snapshot.planningPlans[index].entity = PlanningPlan(
            id: record.entity.id,
            scope: record.entity.scope,
            ownerUserId: record.entity.ownerUserId,
            month: record.entity.month,
            currency: record.entity.currency,
            householdId: record.entity.householdId,
            summary: record.entity.summary,
            incomeSources: record.entity.incomeSources,
            allocations: allocations,
            version: record.entity.version
        )
    }

    private func removeEntity(entityType: SyncEntityType, entityId: String, from snapshot: inout FinanceLocalSnapshot) {
        switch entityType {
        case .transactions:
            snapshot.transactions.removeAll { $0.metadata.entityId == entityId }
        case .accounts:
            snapshot.accounts.removeAll { $0.metadata.entityId == entityId }
        case .categories:
            snapshot.categories.removeAll { $0.metadata.entityId == entityId }
        case .assetCategories:
            snapshot.assetCategories.removeAll { $0.metadata.entityId == entityId }
        case .planningPlans:
            snapshot.planningPlans.removeAll { $0.metadata.entityId == entityId }
        case .planningIncomeSources:
            snapshot.planningIncomeSources.removeAll { $0.metadata.entityId == entityId }
        case .planningAllocations:
            snapshot.planningAllocations.removeAll { $0.metadata.entityId == entityId }
        case .investmentMigrations:
            break
        }
    }

    private func metadata(
        _ entityType: SyncEntityType,
        _ entityId: String,
        _ version: Int?,
        syncStatus: LocalRecordSyncStatus = .synced,
        pendingMutationId: String? = nil
    ) -> LocalRecordMetadata {
        let now = Date().ISO8601Format()
        LocalRecordMetadata(
            entityType: entityType,
            entityId: entityId,
            serverVersion: version,
            syncStatus: syncStatus,
            pendingMutationId: pendingMutationId,
            updatedAt: now,
            lastSyncedAt: syncStatus == .synced ? now : nil
        )
    }

    private func decode<Entity: Decodable>(_ payload: [String: SyncJSONValue]) throws -> Entity {
        do {
            return try decoder.decode(Entity.self, from: SyncJSONValue.data(from: payload))
        } catch {
            throw LocalStoreError.invalidPullPayload("\(Entity.self): \(error.localizedDescription)")
        }
    }

    private func upsert<Entity: Identifiable & Codable & Sendable>(
        _ record: LocalRecord<Entity>,
        in records: inout [LocalRecord<Entity>]
    ) where Entity.ID == String {
        if let index = records.firstIndex(where: { $0.entity.id == record.entity.id }) {
            records[index] = record
        } else {
            records.append(record)
        }
    }

    private func compactAppliedMutations(in snapshot: inout FinanceLocalSnapshot) -> Int {
        let appliedIds = Set(snapshot.pendingMutations
            .filter { $0.status == .applied }
            .map(\.clientMutationId))
        guard !appliedIds.isEmpty else { return 0 }

        snapshot.pendingMutations.removeAll { appliedIds.contains($0.clientMutationId) }
        snapshot.planningMutationMetadata.removeAll { appliedIds.contains($0.pendingMutationId) }
        snapshot.tombstones.removeAll { tombstone in
            guard let pendingMutationId = tombstone.pendingMutationId else { return false }
            return appliedIds.contains(pendingMutationId)
        }
        return appliedIds.count
    }

    private func migrateLegacySnapshots(
        scope: LocalStoreScope,
        deviceId: String
    ) async throws -> FinanceLocalSnapshot? {
        let legacy = try legacySnapshots(for: scope)
        guard !legacy.isEmpty else { return nil }

        var migrated = FinanceLocalSnapshot.empty(scope: scope, deviceId: deviceId)
        for (_, source) in legacy.sorted(by: { $0.snapshot.updatedAt < $1.snapshot.updatedAt }) {
            mergeLegacySnapshot(source.snapshot, into: &migrated, scope: scope)
        }
        migrated.syncState.deviceId = deviceId
        try await saveSnapshot(migrated)
        for (url, _) in legacy where fileManager.fileExists(atPath: url.path) {
            try fileManager.removeItem(at: url)
        }
        return migrated
    }

    private func legacySnapshots(for scope: LocalStoreScope) throws -> [(url: URL, snapshot: FinanceLocalSnapshot)] {
        guard fileManager.fileExists(atPath: rootURL.path) else { return [] }
        let currentURL = snapshotURL(scope: scope)
        return try fileManager.contentsOfDirectory(
            at: rootURL,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ).compactMap { url in
            guard url != currentURL,
                  url.pathExtension == "json",
                  (try? url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true else {
                return nil
            }
            try? protectAndExcludeFromBackup(url)
            guard let data = try? Data(contentsOf: url),
                  let snapshot = try? decoder.decode(FinanceLocalSnapshot.self, from: data),
                  snapshot.scope.viewerUserId == scope.viewerUserId,
                  snapshot.scope.sessionId != nil || snapshot.scope.householdId != nil else {
                return nil
            }
            return (url, snapshot)
        }
    }

    private func mergeLegacySnapshot(
        _ source: FinanceLocalSnapshot,
        into target: inout FinanceLocalSnapshot,
        scope: LocalStoreScope
    ) {
        for record in source.accounts where record.entity.ownershipType == .personal &&
            record.entity.ownerUserId == scope.viewerUserId && record.entity.householdId == nil {
            upsert(record, in: &target.accounts)
        }
        for record in source.categories where record.entity.scope == .personal &&
            record.entity.ownerUserId == scope.viewerUserId && record.entity.householdId == nil {
            upsert(record, in: &target.categories)
        }
        for record in source.assetCategories where record.entity.scopeType == .personal &&
            record.entity.ownerUserId == scope.viewerUserId && record.entity.householdId == nil {
            upsert(record, in: &target.assetCategories)
        }
        let accountIds = Set(target.accounts.map { $0.entity.id })
        let categoryIds = Set(target.categories.map { $0.entity.id })
        for record in source.transactions where accountIds.contains(record.entity.accountId) &&
            record.entity.counterpartyAccountId.map(accountIds.contains) != false &&
            record.entity.categoryId.map(categoryIds.contains) != false {
            upsert(record, in: &target.transactions)
        }
        for record in source.planningPlans where record.entity.scope == .personal &&
            record.entity.ownerUserId == scope.viewerUserId && record.entity.householdId == nil {
            upsert(record, in: &target.planningPlans)
        }
        let planIds = Set(target.planningPlans.map { $0.entity.id })
        for record in source.planningIncomeSources where planIds.contains(record.entity.planId) {
            upsert(record, in: &target.planningIncomeSources)
        }
        for record in source.planningAllocations where planIds.contains(record.entity.planId) {
            let targetId = record.entity.targetId
            let allowedTarget: Bool
            switch record.entity.targetType {
            case .expense_category:
                allowedTarget = targetId.map(categoryIds.contains) ?? true
            case .account:
                allowedTarget = targetId.map(accountIds.contains) ?? true
            case .asset, .investment_asset_category:
                allowedTarget = targetId.map { Set(target.assetCategories.map { $0.entity.id }).contains($0) } ?? true
            }
            if allowedTarget { upsert(record, in: &target.planningAllocations) }
        }

        for sourceMutation in source.pendingMutations {
            var mutation = sourceMutation
            mutation.scope = scope
            guard PersonalSyncOwnershipValidator.allows(mutation: mutation, snapshot: target),
                  !target.pendingMutations.contains(where: { $0.clientMutationId == mutation.clientMutationId }) else {
                continue
            }
            target.pendingMutations.append(mutation)
        }
        target.planningMutationMetadata.append(contentsOf: source.planningMutationMetadata.filter { metadata in
            target.pendingMutations.contains(where: { $0.clientMutationId == metadata.pendingMutationId })
        })

        let knownTombstones = Set(
            target.accounts.map { "\(SyncEntityType.accounts.rawValue):\($0.entity.id)" } +
            target.categories.map { "\(SyncEntityType.categories.rawValue):\($0.entity.id)" } +
            target.assetCategories.map { "\(SyncEntityType.assetCategories.rawValue):\($0.entity.id)" } +
            target.transactions.map { "\(SyncEntityType.transactions.rawValue):\($0.entity.id)" } +
            target.planningPlans.map { "\(SyncEntityType.planningPlans.rawValue):\($0.entity.id)" } +
            target.planningIncomeSources.map { "\(SyncEntityType.planningIncomeSources.rawValue):\($0.entity.id)" } +
            target.planningAllocations.map { "\(SyncEntityType.planningAllocations.rawValue):\($0.entity.id)" }
        )
        for tombstone in source.tombstones {
            let key = "\(tombstone.entityType.rawValue):\(tombstone.entityId)"
            let matchesPendingDelete = tombstone.pendingMutationId.map { pendingMutationId in
                target.pendingMutations.contains { mutation in
                    mutation.clientMutationId == pendingMutationId
                        && mutation.entityType == tombstone.entityType
                        && mutation.entityId == tombstone.entityId
                        && mutation.operation == .delete
                }
            } ?? false
            guard knownTombstones.contains(key) || matchesPendingDelete else { continue }
            addTombstone(
                entityType: tombstone.entityType,
                entityId: tombstone.entityId,
                operation: tombstone.operation,
                baseVersion: tombstone.baseVersion,
                pendingMutationId: tombstone.pendingMutationId,
                createdAt: tombstone.createdAt,
                to: &target
            )
        }
        for issue in source.issues where !target.issues.contains(where: { $0.id == issue.id }) {
            target.issues.append(issue)
        }
        target.syncState.cursor = max(target.syncState.cursor, source.syncState.cursor)
        target.syncState.lastPulledAt = maxOptionalISO(target.syncState.lastPulledAt, source.syncState.lastPulledAt)
        target.syncState.lastPushedAt = maxOptionalISO(target.syncState.lastPushedAt, source.syncState.lastPushedAt)
        target.syncState.issueIds = target.issues.map(\.id)
    }

    private func maxOptionalISO(_ lhs: String?, _ rhs: String?) -> String? {
        switch (lhs, rhs) {
        case (nil, _): return rhs
        case (_, nil): return lhs
        case let (lhs?, rhs?): return max(lhs, rhs)
        }
    }

    private func ensureRootExists() throws {
        try fileManager.createDirectory(at: rootURL, withIntermediateDirectories: true)
        try protectAndExcludeFromBackup(rootURL)
    }

    private func protectAndExcludeFromBackup(_ url: URL) throws {
        try fileManager.setAttributes(
            [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
            ofItemAtPath: url.path
        )
        var protectedURL = url
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try protectedURL.setResourceValues(values)
    }

    private func snapshotURL(scope: LocalStoreScope) -> URL {
        rootURL.appendingPathComponent("\(scope.storageKey).json")
    }
}

enum LocalStoreError: Error, LocalizedError {
    case unsupportedOfflineMutation(entityType: String, operation: String)
    case invalidOfflinePayload(String)
    case invalidPullPayload(String)
    case uncertainPersonalOwnership(entityType: String)
    case accountScopeMismatch

    var errorDescription: String? {
        switch self {
        case .unsupportedOfflineMutation(let entityType, let operation):
            return "Offline-очередь не поддерживает операцию \(entityType):\(operation)."
        case .invalidOfflinePayload(let reason):
            return "Изменение нельзя безопасно поставить в очередь: \(reason)."
        case .invalidPullPayload:
            return "Серверное изменение не удалось безопасно применить локально."
        case .uncertainPersonalOwnership(let entityType):
            return "Не удалось подтвердить личную принадлежность \(entityType). Изменение не отправлено."
        case .accountScopeMismatch:
            return "Локальные данные принадлежат другому аккаунту и не были открыты."
        }
    }
}

private extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
