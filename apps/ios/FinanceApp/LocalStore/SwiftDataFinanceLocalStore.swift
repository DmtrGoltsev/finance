import Foundation
import SwiftData

@Model
final class SwiftDataFinanceSnapshotRecord {
    @Attribute(.unique) var accountScopeKey: String
    var viewerUserId: String
    var accessVersion: String?
    var schemaVersion: Int
    var updatedAt: String
    var scopeData: Data
    var entitiesData: Data
    var pendingMutationsData: Data
    var tombstonesData: Data
    var syncStateData: Data
    var issuesData: Data
    var planningMetadataData: Data
    var migrationState: String
    var migrationReceiptData: Data?

    init(
        accountScopeKey: String,
        viewerUserId: String,
        accessVersion: String?,
        schemaVersion: Int,
        updatedAt: String,
        scopeData: Data,
        entitiesData: Data,
        pendingMutationsData: Data,
        tombstonesData: Data,
        syncStateData: Data,
        issuesData: Data,
        planningMetadataData: Data,
        migrationState: String,
        migrationReceiptData: Data?
    ) {
        self.accountScopeKey = accountScopeKey
        self.viewerUserId = viewerUserId
        self.accessVersion = accessVersion
        self.schemaVersion = schemaVersion
        self.updatedAt = updatedAt
        self.scopeData = scopeData
        self.entitiesData = entitiesData
        self.pendingMutationsData = pendingMutationsData
        self.tombstonesData = tombstonesData
        self.syncStateData = syncStateData
        self.issuesData = issuesData
        self.planningMetadataData = planningMetadataData
        self.migrationState = migrationState
        self.migrationReceiptData = migrationReceiptData
    }
}

private struct SwiftDataEntitySnapshot: Codable {
    var accounts: [LocalRecord<Account>]
    var categories: [LocalRecord<Category>]
    var assetCategories: [LocalRecord<AssetCategory>]
    var transactions: [LocalRecord<Transaction>]
    var planningPlans: [LocalRecord<PlanningPlan>]
    var planningIncomeSources: [LocalRecord<PlanningIncomeSource>]
    var planningAllocations: [LocalRecord<PlanningAllocation>]
}

private struct SwiftDataMigrationReceipt: Codable {
    let completedAt: String
    let retainedRecoveryFiles: [String]
}

enum SwiftDataFinanceLocalStoreError: Error, LocalizedError {
    case duplicateScopeRecord
    case corruptRecord
    case injectedFailure

    var errorDescription: String? {
        switch self {
        case .duplicateScopeRecord:
            return "Локальная БД содержит конфликтующие записи одного аккаунта."
        case .corruptRecord:
            return "Локальная БД повреждена и не была изменена."
        case .injectedFailure:
            return "Тестовый сбой транзакции SwiftData."
        }
    }
}

actor SwiftDataFinanceLocalStore: FinanceLocalStore {
    enum FailurePoint {
        case beforeSave
    }

    private let container: ModelContainer
    private let legacyRootURL: URL
    private let fileManager: FileManager
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private var nextFailurePoint: FailurePoint?

    init(
        modelContainer: ModelContainer,
        legacyRootURL: URL? = nil,
        fileManager: FileManager = .default
    ) {
        self.container = modelContainer
        self.fileManager = fileManager
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory
        self.legacyRootURL = legacyRootURL
            ?? appSupport.appendingPathComponent("FinanceApp/OfflineStore", isDirectory: true)
    }

    static func live(
        rootURL: URL? = nil,
        fileManager: FileManager = .default
    ) throws -> SwiftDataFinanceLocalStore {
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory
        let root = rootURL ?? appSupport.appendingPathComponent("FinanceApp/OfflineStore", isDirectory: true)
        try fileManager.createDirectory(at: root, withIntermediateDirectories: true)
        try fileManager.setAttributes(
            [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
            ofItemAtPath: root.path
        )
        var protectedRoot = root
        var resourceValues = URLResourceValues()
        resourceValues.isExcludedFromBackup = true
        try protectedRoot.setResourceValues(resourceValues)
        let schema = Schema([SwiftDataFinanceSnapshotRecord.self])
        let configuration = ModelConfiguration(
            "FinanceOfflineStore",
            schema: schema,
            url: root.appendingPathComponent("finance-offline.store")
        )
        let container = try ModelContainer(for: schema, configurations: [configuration])
        return SwiftDataFinanceLocalStore(
            modelContainer: container,
            legacyRootURL: root,
            fileManager: fileManager
        )
    }

    func injectFailureOnceForTesting(_ point: FailurePoint) {
        nextFailurePoint = point
    }

    func loadSnapshot(scope: LocalStoreScope, deviceId: String) async throws -> FinanceLocalSnapshot {
        try validate(scope)
        let context = makeContext()
        if let record = try fetchRecord(scope: scope, context: context) {
            var snapshot = try decodeSnapshot(record)
            try validateLoaded(snapshot, requestedScope: scope)
            if snapshot.syncState.deviceId != deviceId {
                snapshot.syncState.deviceId = deviceId
                try persist(snapshot, migrationReceipt: nil, context: context)
                try commit(context)
            }
            return snapshot
        }

        let migration = try legacySnapshot(scope: scope, deviceId: deviceId)
        let snapshot = migration?.snapshot ?? .empty(scope: normalized(scope), deviceId: deviceId)
        try persist(snapshot, migrationReceipt: migration?.receipt, context: context)
        try commit(context)
        return snapshot
    }

    func saveSnapshot(_ snapshot: FinanceLocalSnapshot) async throws {
        try validate(snapshot.scope)
        let context = makeContext()
        try persist(snapshot, migrationReceipt: nil, context: context)
        try commit(context)
    }

    func enqueueMutation(_ mutation: PendingMutation, planningMetadata: PlanningMutationMetadata?) async throws {
        try transact(scope: mutation.scope, deviceId: mutation.deviceId) { snapshot in
            guard SyncQueuePolicy.isSyncable(entityType: mutation.entityType, operation: mutation.operation) else {
                throw LocalStoreError.unsupportedOfflineMutation(
                    entityType: mutation.entityType.rawValue,
                    operation: mutation.operation.rawValue
                )
            }
            snapshot.pendingMutations.append(mutation)
            if let planningMetadata { snapshot.planningMutationMetadata.append(planningMetadata) }
            if mutation.operation == .delete || mutation.operation == .archive {
                addTombstone(
                    entityType: mutation.entityType,
                    entityId: mutation.entityId,
                    operation: mutation.operation,
                    baseVersion: mutation.baseVersion,
                    pendingMutationId: mutation.clientMutationId,
                    to: &snapshot
                )
            }
        }
    }

    func commitOptimisticMutation(
        _ mutation: PendingMutation,
        planningMetadata: PlanningMutationMetadata?,
        optimisticPayload: [String: SyncJSONValue]
    ) async throws {
        try transact(scope: mutation.scope, deviceId: mutation.deviceId) { snapshot in
            guard SyncQueuePolicy.isSyncable(entityType: mutation.entityType, operation: mutation.operation) else {
                throw LocalStoreError.unsupportedOfflineMutation(
                    entityType: mutation.entityType.rawValue,
                    operation: mutation.operation.rawValue
                )
            }

            if let createIndex = snapshot.pendingMutations.lastIndex(where: {
                $0.entityType == mutation.entityType &&
                    $0.entityId == mutation.entityId &&
                    $0.operation == .create &&
                    $0.canPush
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
                    return
                case .delete, .archive:
                    let createMutationId = snapshot.pendingMutations[createIndex].clientMutationId
                    snapshot.pendingMutations.remove(at: createIndex)
                    snapshot.planningMutationMetadata.removeAll { $0.pendingMutationId == createMutationId }
                    snapshot.tombstones.removeAll { $0.pendingMutationId == createMutationId }
                    removeEntity(entityType: mutation.entityType, entityId: mutation.entityId, from: &snapshot)
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
            if let planningMetadata { snapshot.planningMutationMetadata.append(planningMetadata) }
        }
    }

    func optimisticUpsert(
        scope: LocalStoreScope,
        deviceId: String,
        entityType: SyncEntityType,
        entityId: String,
        baseVersion: Int?,
        pendingMutationId: String?,
        payload: [String: SyncJSONValue]
    ) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            try applyPayload(
                payload,
                entityType: entityType,
                entityId: entityId,
                version: baseVersion,
                syncStatus: .pending,
                pendingMutationId: pendingMutationId,
                to: &snapshot
            )
        }
    }

    func optimisticDelete(
        scope: LocalStoreScope,
        deviceId: String,
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int?,
        pendingMutationId: String?
    ) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            addTombstone(
                entityType: entityType,
                entityId: entityId,
                operation: operation,
                baseVersion: baseVersion,
                pendingMutationId: pendingMutationId,
                to: &snapshot
            )
            removeEntity(entityType: entityType, entityId: entityId, from: &snapshot)
        }
    }

    func compactAppliedMutations(scope: LocalStoreScope, deviceId: String) async throws -> Int {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            compactAppliedMutations(in: &snapshot)
        }
    }

    func pendingMutations(scope: LocalStoreScope, deviceId: String, limit: Int) async throws -> [PendingMutation] {
        let snapshot = try await loadSnapshot(scope: scope, deviceId: deviceId)
        var entityKeys = Set<String>()
        var ready: [PendingMutation] = []
        for mutation in snapshot.pendingMutations where mutation.canPush {
            let entityKey = "\(mutation.entityType.rawValue):\(mutation.entityId)"
            guard entityKeys.insert(entityKey).inserted else { continue }
            ready.append(mutation)
            if ready.count == limit { break }
        }
        return ready
    }

    func recordAttempt(scope: LocalStoreScope, deviceId: String, mutationId: String) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            guard let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) else {
                return
            }
            snapshot.pendingMutations[index].attemptCount += 1
            snapshot.pendingMutations[index].lastAttemptAt = Date().ISO8601Format()
            snapshot.pendingMutations[index].updatedAt = snapshot.pendingMutations[index].lastAttemptAt
                ?? snapshot.pendingMutations[index].updatedAt
        }
    }

    func markApplied(scope: LocalStoreScope, deviceId: String, result: SyncMutationResult) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
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
                try? applyPayload(
                    data,
                    entityType: result.entityType,
                    entityId: result.entityId,
                    version: result.serverVersion,
                    to: &snapshot
                )
            }
            if result.operation == .delete || result.operation == .archive || result.operation == .restore {
                snapshot.tombstones.removeAll {
                    $0.entityType == result.entityType && $0.entityId == result.entityId
                }
            }
            _ = compactAppliedMutations(in: &snapshot)
        }
    }

    func markRejected(
        scope: LocalStoreScope,
        deviceId: String,
        mutationId: String,
        issue: SyncIssue
    ) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            if let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) {
                snapshot.pendingMutations[index].status = .rejected
                snapshot.pendingMutations[index].lastError = issue.safeDescription
                snapshot.pendingMutations[index].updatedAt = Date().ISO8601Format()
            }
            upsertIssue(issue, in: &snapshot)
        }
    }

    func markFailed(
        scope: LocalStoreScope,
        deviceId: String,
        mutationId: String,
        message: String?
    ) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            guard let index = snapshot.pendingMutations.firstIndex(where: { $0.clientMutationId == mutationId }) else {
                return
            }
            snapshot.pendingMutations[index].status = .retry
            snapshot.pendingMutations[index].lastError = SyncSafeMessage.describe(message)
            snapshot.pendingMutations[index].updatedAt = Date().ISO8601Format()
            upsertIssue(SyncIssue.failed(from: snapshot.pendingMutations[index], message: message), in: &snapshot)
        }
    }

    func retryIssue(scope: LocalStoreScope, deviceId: String, issueId: String) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            guard let issue = snapshot.issues.first(where: { $0.id == issueId }),
                  issue.decision == .retryAllowed,
                  let mutationId = issue.mutationId,
                  let mutationIndex = snapshot.pendingMutations.firstIndex(where: {
                      $0.clientMutationId == mutationId
                  }) else {
                return
            }
            snapshot.pendingMutations[mutationIndex].status = .retry
            snapshot.pendingMutations[mutationIndex].lastError = nil
            snapshot.pendingMutations[mutationIndex].updatedAt = Date().ISO8601Format()
            snapshot.issues.removeAll { $0.id == issueId }
            snapshot.syncState.issueIds = snapshot.issues.map(\.id)
        }
    }

    func applyPullResponse(scope: LocalStoreScope, deviceId: String, response: SyncPullResponse) async throws {
        try await applyPullPage(scope: scope, deviceId: deviceId, response: response, quarantined: [])
    }

    func applyPullPage(
        scope: LocalStoreScope,
        deviceId: String,
        response: SyncPullResponse,
        quarantined: [SyncPullQuarantine]
    ) async throws {
        try transact(scope: scope, deviceId: deviceId) { snapshot in
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
            for item in quarantined { addQuarantine(item, to: &snapshot) }

            let handledSequences = (response.changes.map(\.seq) + quarantined.map { $0.change.seq }).sorted()
            let expectedCursor = handledSequences.last ?? snapshot.syncState.cursor
            guard Set(handledSequences).count == handledSequences.count,
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
                return
            }
            snapshot.syncState.cursor = response.nextCursor
            snapshot.syncState.lastPulledAt = response.serverTime
            snapshot.syncState.lastError = nil
        }
    }

    func quarantinePullChanges(
        scope: LocalStoreScope,
        deviceId: String,
        changes: [SyncChange]
    ) async throws {
        guard !changes.isEmpty else { return }
        try transact(scope: scope, deviceId: deviceId) { snapshot in
            for change in changes {
                addQuarantine(.personalScope(change), to: &snapshot)
            }
        }
    }

    func issues(scope: LocalStoreScope, deviceId: String) async throws -> [SyncIssue] {
        try await loadSnapshot(scope: scope, deviceId: deviceId).issues
    }

    func wipe(scope: LocalStoreScope) async throws {
        let context = makeContext()
        let viewerUserId = scope.viewerUserId
        let descriptor = FetchDescriptor<SwiftDataFinanceSnapshotRecord>(
            predicate: #Predicate { $0.viewerUserId == viewerUserId }
        )
        for record in try context.fetch(descriptor) { context.delete(record) }
        try commit(context)
        try removeLegacyFiles(viewerUserId: viewerUserId)
    }

    func wipeAllProtectedData() async throws {
        let context = makeContext()
        for record in try context.fetch(FetchDescriptor<SwiftDataFinanceSnapshotRecord>()) {
            context.delete(record)
        }
        try commit(context)
        if fileManager.fileExists(atPath: legacyRootURL.path) {
            for url in try fileManager.contentsOfDirectory(at: legacyRootURL, includingPropertiesForKeys: nil)
                where url.pathExtension == "json" {
                try fileManager.removeItem(at: url)
            }
        }
    }

    private func makeContext() -> ModelContext {
        let context = ModelContext(container)
        context.autosaveEnabled = false
        return context
    }

    private func transact<Result>(
        scope: LocalStoreScope,
        deviceId: String,
        _ update: (inout FinanceLocalSnapshot) throws -> Result
    ) throws -> Result {
        try validate(scope)
        let context = makeContext()
        let existing = try fetchRecord(scope: scope, context: context)
        let migration = existing == nil ? try legacySnapshot(scope: scope, deviceId: deviceId) : nil
        var snapshot: FinanceLocalSnapshot
        if let existing {
            snapshot = try decodeSnapshot(existing)
        } else if let migration {
            snapshot = migration.snapshot
        } else {
            snapshot = .empty(scope: normalized(scope), deviceId: deviceId)
        }
        try validateLoaded(snapshot, requestedScope: scope)
        snapshot.syncState.deviceId = deviceId
        let result = try update(&snapshot)
        try persist(snapshot, migrationReceipt: migration?.receipt, context: context)
        try commit(context)
        return result
    }

    private func commit(_ context: ModelContext) throws {
        if nextFailurePoint == .beforeSave {
            nextFailurePoint = nil
            context.rollback()
            throw SwiftDataFinanceLocalStoreError.injectedFailure
        }
        do {
            try context.save()
        } catch {
            context.rollback()
            throw error
        }
    }

    private func fetchRecord(
        scope: LocalStoreScope,
        context: ModelContext
    ) throws -> SwiftDataFinanceSnapshotRecord? {
        let key = accountScopeKey(scope)
        var descriptor = FetchDescriptor<SwiftDataFinanceSnapshotRecord>(
            predicate: #Predicate { $0.accountScopeKey == key }
        )
        descriptor.fetchLimit = 2
        let records = try context.fetch(descriptor)
        guard records.count <= 1 else { throw SwiftDataFinanceLocalStoreError.duplicateScopeRecord }
        return records.first
    }

    private func persist(
        _ input: FinanceLocalSnapshot,
        migrationReceipt: SwiftDataMigrationReceipt?,
        context: ModelContext
    ) throws {
        var snapshot = input
        snapshot.updatedAt = Date().ISO8601Format()
        snapshot.schemaVersion = financeSyncSchemaVersion
        let scope = normalized(snapshot.scope)
        let entities = SwiftDataEntitySnapshot(
            accounts: snapshot.accounts,
            categories: snapshot.categories,
            assetCategories: snapshot.assetCategories,
            transactions: snapshot.transactions,
            planningPlans: snapshot.planningPlans,
            planningIncomeSources: snapshot.planningIncomeSources,
            planningAllocations: snapshot.planningAllocations
        )
        let record = try fetchRecord(scope: scope, context: context) ?? SwiftDataFinanceSnapshotRecord(
            accountScopeKey: accountScopeKey(scope),
            viewerUserId: scope.viewerUserId,
            accessVersion: scope.accessVersion,
            schemaVersion: snapshot.schemaVersion,
            updatedAt: snapshot.updatedAt,
            scopeData: Data(),
            entitiesData: Data(),
            pendingMutationsData: Data(),
            tombstonesData: Data(),
            syncStateData: Data(),
            issuesData: Data(),
            planningMetadataData: Data(),
            migrationState: migrationReceipt == nil ? "native" : "completed",
            migrationReceiptData: nil
        )
        if record.modelContext == nil { context.insert(record) }
        record.viewerUserId = scope.viewerUserId
        record.accessVersion = scope.accessVersion
        record.schemaVersion = snapshot.schemaVersion
        record.updatedAt = snapshot.updatedAt
        record.scopeData = try encoder.encode(scope)
        record.entitiesData = try encoder.encode(entities)
        record.pendingMutationsData = try encoder.encode(snapshot.pendingMutations)
        record.tombstonesData = try encoder.encode(snapshot.tombstones)
        record.syncStateData = try encoder.encode(snapshot.syncState)
        record.issuesData = try encoder.encode(snapshot.issues)
        record.planningMetadataData = try encoder.encode(snapshot.planningMutationMetadata)
        if let migrationReceipt {
            record.migrationState = "completed"
            record.migrationReceiptData = try encoder.encode(migrationReceipt)
        }
    }

    private func decodeSnapshot(_ record: SwiftDataFinanceSnapshotRecord) throws -> FinanceLocalSnapshot {
        do {
            let scope = try decoder.decode(LocalStoreScope.self, from: record.scopeData)
            let entities = try decoder.decode(SwiftDataEntitySnapshot.self, from: record.entitiesData)
            return FinanceLocalSnapshot(
                schemaVersion: record.schemaVersion,
                scope: scope,
                updatedAt: record.updatedAt,
                accounts: entities.accounts,
                categories: entities.categories,
                assetCategories: entities.assetCategories,
                transactions: entities.transactions,
                planningPlans: entities.planningPlans,
                planningIncomeSources: entities.planningIncomeSources,
                planningAllocations: entities.planningAllocations,
                planningMutationMetadata: try decoder.decode([PlanningMutationMetadata].self, from: record.planningMetadataData),
                tombstones: try decoder.decode([SyncTombstone].self, from: record.tombstonesData),
                pendingMutations: try decoder.decode([PendingMutation].self, from: record.pendingMutationsData),
                syncState: try decoder.decode(LocalSyncState.self, from: record.syncStateData),
                issues: try decoder.decode([SyncIssue].self, from: record.issuesData)
            )
        } catch {
            throw SwiftDataFinanceLocalStoreError.corruptRecord
        }
    }

    private func validate(_ scope: LocalStoreScope) throws {
        guard !scope.viewerUserId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              scope.householdId == nil else {
            throw LocalStoreError.accountScopeMismatch
        }
    }

    private func validateLoaded(_ snapshot: FinanceLocalSnapshot, requestedScope: LocalStoreScope) throws {
        guard snapshot.scope.viewerUserId == requestedScope.viewerUserId,
              snapshot.scope.accessVersion == requestedScope.accessVersion,
              snapshot.scope.householdId == nil else {
            throw LocalStoreError.accountScopeMismatch
        }
    }

    private func normalized(_ scope: LocalStoreScope) -> LocalStoreScope {
        LocalStoreScope(
            viewerUserId: scope.viewerUserId,
            sessionId: nil,
            householdId: nil,
            accessVersion: scope.accessVersion
        )
    }

    private func accountScopeKey(_ scope: LocalStoreScope) -> String {
        let user = Data(scope.viewerUserId.utf8).base64EncodedString()
        let access = Data((scope.accessVersion ?? "").utf8).base64EncodedString()
        return "viewer:\(user)|access:\(access)"
    }

    private func legacySnapshot(
        scope: LocalStoreScope,
        deviceId: String
    ) throws -> (snapshot: FinanceLocalSnapshot, receipt: SwiftDataMigrationReceipt)? {
        guard fileManager.fileExists(atPath: legacyRootURL.path) else { return nil }
        let candidates = try fileManager.contentsOfDirectory(
            at: legacyRootURL,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ).compactMap { url -> (URL, FinanceLocalSnapshot)? in
            guard url.pathExtension == "json",
                  (try? url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true,
                  let data = try? Data(contentsOf: url),
                  let snapshot = try? decoder.decode(FinanceLocalSnapshot.self, from: data),
                  snapshot.scope.viewerUserId == scope.viewerUserId,
                  snapshot.scope.householdId == nil,
                  snapshot.scope.accessVersion == scope.accessVersion || snapshot.scope.sessionId != nil else {
                return nil
            }
            return (url, snapshot)
        }
        guard !candidates.isEmpty else { return nil }

        var merged = FinanceLocalSnapshot.empty(scope: normalized(scope), deviceId: deviceId)
        for (_, source) in candidates.sorted(by: { $0.1.updatedAt < $1.1.updatedAt }) {
            mergeLegacy(source, into: &merged, scope: scope)
        }
        merged.syncState.deviceId = deviceId
        let receipt = SwiftDataMigrationReceipt(
            completedAt: Date().ISO8601Format(),
            retainedRecoveryFiles: candidates.map { $0.0.path }.sorted()
        )
        return (merged, receipt)
    }

    private func mergeLegacy(
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
        for record in source.transactions { upsert(record, in: &target.transactions) }
        for record in source.planningPlans where record.entity.scope == .personal &&
            record.entity.ownerUserId == scope.viewerUserId && record.entity.householdId == nil {
            upsert(record, in: &target.planningPlans)
        }
        for record in source.planningIncomeSources { upsert(record, in: &target.planningIncomeSources) }
        for record in source.planningAllocations { upsert(record, in: &target.planningAllocations) }

        for sourceMutation in source.pendingMutations {
            var mutation = sourceMutation
            mutation.scope = normalized(scope)
            if let index = target.pendingMutations.firstIndex(where: {
                $0.clientMutationId == mutation.clientMutationId
            }) {
                if target.pendingMutations[index].updatedAt < mutation.updatedAt {
                    target.pendingMutations[index] = mutation
                }
            } else {
                target.pendingMutations.append(mutation)
            }
        }
        for metadata in source.planningMutationMetadata where
            !target.planningMutationMetadata.contains(where: { $0.id == metadata.id }) {
            target.planningMutationMetadata.append(metadata)
        }
        for tombstone in source.tombstones where !target.tombstones.contains(where: {
            $0.entityType == tombstone.entityType &&
                $0.entityId == tombstone.entityId &&
                $0.pendingMutationId == tombstone.pendingMutationId
        }) {
            target.tombstones.append(tombstone)
        }
        for issue in source.issues where !target.issues.contains(where: { $0.id == issue.id }) {
            target.issues.append(issue)
        }
        target.syncState.cursor = max(target.syncState.cursor, source.syncState.cursor)
        target.syncState.lastPulledAt = maxISO(target.syncState.lastPulledAt, source.syncState.lastPulledAt)
        target.syncState.lastPushedAt = maxISO(target.syncState.lastPushedAt, source.syncState.lastPushedAt)
        target.syncState.issueIds = target.issues.map(\.id)
    }

    private func removeLegacyFiles(viewerUserId: String) throws {
        guard fileManager.fileExists(atPath: legacyRootURL.path) else { return }
        for url in try fileManager.contentsOfDirectory(at: legacyRootURL, includingPropertiesForKeys: nil)
            where url.pathExtension == "json" {
            guard let data = try? Data(contentsOf: url),
                  let snapshot = try? decoder.decode(FinanceLocalSnapshot.self, from: data),
                  snapshot.scope.viewerUserId == viewerUserId else {
                continue
            }
            try fileManager.removeItem(at: url)
        }
    }

    private func maxISO(_ lhs: String?, _ rhs: String?) -> String? {
        switch (lhs, rhs) {
        case (nil, _): return rhs
        case (_, nil): return lhs
        case let (lhs?, rhs?): return max(lhs, rhs)
        }
    }
}

private extension SwiftDataFinanceLocalStore {
    func upsertIssue(_ issue: SyncIssue, in snapshot: inout FinanceLocalSnapshot) {
        if let index = snapshot.issues.firstIndex(where: { $0.id == issue.id }) {
            snapshot.issues[index] = issue
        } else {
            snapshot.issues.append(issue)
        }
        snapshot.syncState.issueIds = snapshot.issues.map(\.id)
    }

    func applyPayload(
        _ payload: [String: SyncJSONValue],
        entityType: SyncEntityType,
        entityId: String,
        version: Int?,
        syncStatus: LocalRecordSyncStatus = .synced,
        pendingMutationId: String? = nil,
        to snapshot: inout FinanceLocalSnapshot
    ) throws {
        if hasPendingTombstone(entityType: entityType, entityId: entityId, in: snapshot) { return }
        snapshot.tombstones.removeAll {
            $0.entityType == entityType && $0.entityId == entityId && $0.pendingMutationId == nil
        }
        switch entityType {
        case .transactions:
            let entity: Transaction = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.transactions
            )
        case .accounts:
            let entity: Account = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.accounts
            )
        case .categories:
            let entity: Category = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.categories
            )
        case .assetCategories:
            let entity: AssetCategory = try decode(payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.assetCategories
            )
        case .planningPlans:
            let existing = snapshot.planningPlans.first(where: {
                $0.metadata.entityId == entityId
            })?.entity
            let entity = try PlanningDomainChangeDTO.plan(from: payload, existing: existing)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.planningPlans
            )
        case .planningIncomeSources:
            let entity = try PlanningDomainChangeDTO.incomeSource(from: payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.planningIncomeSources
            )
            mergeIncomeSource(entity, into: &snapshot)
        case .planningAllocations:
            let entity = try PlanningDomainChangeDTO.allocation(from: payload)
            try validateEntityId(entity.id, expected: entityId, entityType: entityType)
            upsert(
                LocalRecord(
                    entity: entity,
                    metadata: metadata(
                        entityType,
                        entityId,
                        version,
                        syncStatus: syncStatus,
                        pendingMutationId: pendingMutationId
                    )
                ),
                in: &snapshot.planningAllocations
            )
            mergeAllocation(entity, into: &snapshot)
        case .investmentMigrations:
            break
        }
    }

    func applyPullChange(_ change: SyncChange, to snapshot: inout FinanceLocalSnapshot) throws {
        if change.tombstonePayload != nil || change.changeType == "delete" || change.changeType == "archive" {
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
            return
        }
        guard let payload = change.payload else {
            throw LocalStoreError.invalidPullPayload(
                "Missing payload for \(change.entityType.rawValue) \(change.changeType)"
            )
        }
        try applyPayload(
            payload,
            entityType: change.entityType,
            entityId: change.entityId,
            version: change.entityVersion,
            to: &snapshot
        )
    }

    func addQuarantine(_ quarantine: SyncPullQuarantine, to snapshot: inout FinanceLocalSnapshot) {
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

    func addTombstone(
        entityType: SyncEntityType,
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int?,
        pendingMutationId: String?,
        createdAt: String = Date().ISO8601Format(),
        to snapshot: inout FinanceLocalSnapshot
    ) {
        snapshot.tombstones.removeAll {
            $0.entityType == entityType &&
                $0.entityId == entityId &&
                $0.pendingMutationId == pendingMutationId
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

    func mergeCreatePayload(
        _ createPayload: [String: SyncJSONValue]?,
        with newerPayload: [String: SyncJSONValue]?
    ) -> [String: SyncJSONValue]? {
        guard var createPayload else { return newerPayload }
        for (key, value) in newerPayload ?? [:] { createPayload[key] = value }
        return createPayload
    }

    func hasPendingTombstone(
        entityType: SyncEntityType,
        entityId: String,
        in snapshot: FinanceLocalSnapshot
    ) -> Bool {
        snapshot.tombstones.contains {
            $0.entityType == entityType && $0.entityId == entityId && $0.pendingMutationId != nil
        }
    }

    func validateEntityId(
        _ actual: String,
        expected: String,
        entityType: SyncEntityType
    ) throws {
        guard actual == expected else {
            throw LocalStoreError.invalidPullPayload(
                "\(entityType.rawValue) id does not match sync envelope"
            )
        }
    }

    func mergeIncomeSource(_ source: PlanningIncomeSource, into snapshot: inout FinanceLocalSnapshot) {
        guard let index = snapshot.planningPlans.firstIndex(where: {
            $0.entity.id == source.planId
        }) else { return }
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

    func mergeAllocation(_ allocation: PlanningAllocation, into snapshot: inout FinanceLocalSnapshot) {
        guard let index = snapshot.planningPlans.firstIndex(where: {
            $0.entity.id == allocation.planId
        }) else { return }
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

    func removeEntity(
        entityType: SyncEntityType,
        entityId: String,
        from snapshot: inout FinanceLocalSnapshot
    ) {
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

    func metadata(
        _ entityType: SyncEntityType,
        _ entityId: String,
        _ version: Int?,
        syncStatus: LocalRecordSyncStatus = .synced,
        pendingMutationId: String? = nil
    ) -> LocalRecordMetadata {
        let now = Date().ISO8601Format()
        return LocalRecordMetadata(
            entityType: entityType,
            entityId: entityId,
            serverVersion: version,
            syncStatus: syncStatus,
            pendingMutationId: pendingMutationId,
            updatedAt: now,
            lastSyncedAt: syncStatus == .synced ? now : nil
        )
    }

    func decode<Entity: Decodable>(_ payload: [String: SyncJSONValue]) throws -> Entity {
        do {
            return try decoder.decode(Entity.self, from: SyncJSONValue.data(from: payload))
        } catch {
            throw LocalStoreError.invalidPullPayload("\(Entity.self): \(error.localizedDescription)")
        }
    }

    func upsert<Entity: Identifiable & Codable & Sendable>(
        _ record: LocalRecord<Entity>,
        in records: inout [LocalRecord<Entity>]
    ) where Entity.ID == String {
        if let index = records.firstIndex(where: { $0.entity.id == record.entity.id }) {
            records[index] = record
        } else {
            records.append(record)
        }
    }

    func compactAppliedMutations(in snapshot: inout FinanceLocalSnapshot) -> Int {
        let appliedIds = Set(
            snapshot.pendingMutations
                .filter { $0.status == .applied }
                .map(\.clientMutationId)
        )
        guard !appliedIds.isEmpty else { return 0 }
        snapshot.pendingMutations.removeAll { appliedIds.contains($0.clientMutationId) }
        snapshot.planningMutationMetadata.removeAll { appliedIds.contains($0.pendingMutationId) }
        snapshot.tombstones.removeAll {
            guard let pendingMutationId = $0.pendingMutationId else { return false }
            return appliedIds.contains(pendingMutationId)
        }
        return appliedIds.count
    }
}
