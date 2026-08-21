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
            .joined(separator: "_")
            .map { char in
                char.isLetter || char.isNumber || char == "-" || char == "_" ? char : "_"
            }
            .reduce(into: "") { $0.append($1) }
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
    let scope: LocalStoreScope
    let entityType: SyncEntityType
    let entityId: String
    let operation: SyncOperation
    let baseVersion: Int?
    let payload: [String: SyncJSONValue]?
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

protocol FinanceLocalStore: Sendable {
    func loadSnapshot(scope: LocalStoreScope, deviceId: String) async throws -> FinanceLocalSnapshot
    func saveSnapshot(_ snapshot: FinanceLocalSnapshot) async throws
    func enqueueMutation(_ mutation: PendingMutation, planningMetadata: PlanningMutationMetadata?) async throws
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
    func issues(scope: LocalStoreScope, deviceId: String) async throws -> [SyncIssue]
    func wipe(scope: LocalStoreScope) async throws
    func wipeAllProtectedData() async throws
}

actor FileBackedFinanceLocalStore: FinanceLocalStore {
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
        let url = snapshotURL(scope: scope)
        guard fileManager.fileExists(atPath: url.path) else {
            return .empty(scope: scope, deviceId: deviceId)
        }
        let data = try Data(contentsOf: url)
        var snapshot = try decoder.decode(FinanceLocalSnapshot.self, from: data)
        if snapshot.syncState.deviceId != deviceId {
            snapshot.syncState.deviceId = deviceId
        }
        return snapshot
    }

    func saveSnapshot(_ snapshot: FinanceLocalSnapshot) async throws {
        try ensureRootExists()
        var snapshot = snapshot
        snapshot.updatedAt = Date().ISO8601Format()
        let data = try encoder.encode(snapshot)
        try data.write(to: snapshotURL(scope: snapshot.scope), options: [.atomic])
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
        if mutation.operation == .delete || mutation.operation == .archive {
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
        applyPayload(
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
        return snapshot.pendingMutations
            .filter(\.canPush)
            .prefix(limit)
            .map { $0 }
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
        if let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == result.clientMutationId }) {
            snapshot.pendingMutations[index].status = .applied
            snapshot.pendingMutations[index].lastError = nil
            snapshot.pendingMutations[index].updatedAt = Date().ISO8601Format()
        }
        snapshot.issues.removeAll { $0.mutationId == result.clientMutationId }
        snapshot.syncState.issueIds = snapshot.issues.map(\.id)
        if let data = result.data {
            applyPayload(data, entityType: result.entityType, entityId: result.entityId, version: result.serverVersion, to: &snapshot)
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
        var snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        for change in response.changes.sorted(by: { $0.seq < $1.seq }) {
            if change.tombstonePayload != nil || change.changeType == "delete" || change.changeType == "archive" {
                applyTombstone(change, to: &snapshot)
            } else if let payload = change.payload {
                applyPayload(payload, entityType: change.entityType, entityId: change.entityId, version: change.entityVersion, to: &snapshot)
            }
        }
        snapshot.syncState.cursor = response.nextCursor
        snapshot.syncState.lastPulledAt = response.serverTime
        snapshot.syncState.lastError = nil
        try await saveSnapshot(snapshot)
    }

    func issues(scope: LocalStoreScope, deviceId: String) async throws -> [SyncIssue] {
        (try await loadSnapshot(scope: scope, deviceId: deviceId)).issues
    }

    func wipe(scope: LocalStoreScope) async throws {
        let url = snapshotURL(scope: scope)
        if fileManager.fileExists(atPath: url.path) {
            try fileManager.removeItem(at: url)
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
    ) {
        if hasPendingTombstone(entityType: entityType, entityId: entityId, in: snapshot) {
            return
        }
        switch entityType {
        case .transactions:
            if let entity: Transaction = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.transactions)
            }
        case .accounts:
            if let entity: Account = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.accounts)
            }
        case .categories:
            if let entity: Category = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.categories)
            }
        case .assetCategories:
            if let entity: AssetCategory = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.assetCategories)
            }
        case .planningPlans:
            if let entity: PlanningPlan = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.planningPlans)
            }
        case .planningIncomeSources:
            if let entity: PlanningIncomeSource = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.planningIncomeSources)
            }
        case .planningAllocations:
            if let entity: PlanningAllocation = decode(payload) {
                upsert(LocalRecord(entity: entity, metadata: metadata(entityType, entityId, version, syncStatus: syncStatus, pendingMutationId: pendingMutationId)), in: &snapshot.planningAllocations)
            }
        case .investmentMigrations:
            break
        }
    }

    private func applyTombstone(_ change: SyncChange, to snapshot: inout FinanceLocalSnapshot) {
        snapshot.tombstones.append(
            SyncTombstone(
                entityType: change.entityType,
                entityId: change.entityId,
                operation: .delete,
                baseVersion: change.entityVersion,
                pendingMutationId: change.clientMutationId,
                createdAt: change.createdAt,
                safeError: nil
            )
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

    private func decode<Entity: Decodable>(_ payload: [String: SyncJSONValue]) -> Entity? {
        guard let data = try? SyncJSONValue.data(from: payload) else { return nil }
        return try? decoder.decode(Entity.self, from: data)
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

    private func ensureRootExists() throws {
        try fileManager.createDirectory(at: rootURL, withIntermediateDirectories: true)
    }

    private func snapshotURL(scope: LocalStoreScope) -> URL {
        rootURL.appendingPathComponent("\(scope.storageKey).json")
    }
}

enum LocalStoreError: Error, LocalizedError {
    case unsupportedOfflineMutation(entityType: String, operation: String)

    var errorDescription: String? {
        switch self {
        case .unsupportedOfflineMutation(let entityType, let operation):
            return "Offline-очередь не поддерживает операцию \(entityType):\(operation)."
        }
    }
}

private extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
