import Foundation

struct SyncOwnershipEvidence: Codable, Equatable, Sendable {
    let viewerUserId: String
    let subjectEntityType: SyncEntityType?
    let subjectEntityId: String?
    let referencedAccountIds: [String]
    let referencedCategoryIds: [String]
    let referencedAssetCategoryIds: [String]
    let referencedPlanIds: [String]
    let attestedPersonalPlanIds: [String]
    let attestedPersonalAccountIds: [String]
    let attestedPersonalCategoryIds: [String]
    let attestedPersonalAssetCategoryIds: [String]
}

struct PersonalOwnershipContext: Sendable {
    var accountIds: Set<String> = []
    var categoryIds: Set<String> = []
    var assetCategoryIds: Set<String> = []
    var planIds: Set<String> = []

    static let empty = PersonalOwnershipContext()

    init(
        viewerUserId: String? = nil,
        accounts: [Account] = [],
        categories: [Category] = [],
        assetCategories: [AssetCategory] = [],
        plans: [PlanningPlan] = []
    ) {
        guard let viewerUserId = viewerUserId?.trimmingCharacters(in: .whitespacesAndNewlines),
              !viewerUserId.isEmpty else {
            return
        }
        accountIds = Set(accounts.compactMap {
            $0.ownershipType == .personal && $0.ownerUserId == viewerUserId && $0.householdId == nil ? $0.id : nil
        })
        categoryIds = Set(categories.compactMap {
            $0.scope == .personal && $0.ownerUserId == viewerUserId && $0.householdId == nil ? $0.id : nil
        })
        assetCategoryIds = Set(assetCategories.compactMap {
            $0.scopeType == .personal && $0.ownerUserId == viewerUserId && $0.householdId == nil ? $0.id : nil
        })
        planIds = Set(plans.compactMap {
            $0.scope == .personal && $0.ownerUserId == viewerUserId && $0.householdId == nil ? $0.id : nil
        })
    }
}

struct PersonalOwnershipIndex: Sendable {
    var accountIds: Set<String>
    var categoryIds: Set<String>
    var assetCategoryIds: Set<String>
    var planIds: Set<String>

    init(snapshot: FinanceLocalSnapshot) {
        accountIds = Set(snapshot.accounts.compactMap { record in
            let entity = record.entity
            return entity.ownershipType == .personal
                && entity.ownerUserId == snapshot.scope.viewerUserId
                && entity.householdId == nil ? entity.id : nil
        })
        categoryIds = Set(snapshot.categories.compactMap { record in
            let entity = record.entity
            return entity.scope == .personal
                && entity.ownerUserId == snapshot.scope.viewerUserId
                && entity.householdId == nil ? entity.id : nil
        })
        assetCategoryIds = Set(snapshot.assetCategories.compactMap { record in
            let entity = record.entity
            return entity.scopeType == .personal
                && entity.ownerUserId == snapshot.scope.viewerUserId
                && entity.householdId == nil ? entity.id : nil
        })
        planIds = Set(snapshot.planningPlans.compactMap { record in
            let entity = record.entity
            return entity.scope == .personal
                && entity.ownerUserId == snapshot.scope.viewerUserId
                && entity.householdId == nil ? entity.id : nil
        })
    }

    mutating func includeClearlyPersonalParents(
        from changes: [SyncChange],
        viewerUserId: String
    ) {
        let orderedParentTypes: [SyncEntityType] = [
            .assetCategories,
            .categories,
            .planningPlans,
            .accounts,
        ]
        for entityType in orderedParentTypes {
            for change in changes where change.entityType == entityType {
                guard let payload = change.payload,
                      PersonalSyncOwnershipValidator.payloadMatchesEntity(payload, change: change),
                      (try? PersonalSyncOwnershipValidator.references(
                        entityType: entityType,
                        payload: payload,
                        viewerUserId: viewerUserId,
                        index: self
                      )) != nil else {
                    continue
                }
                switch entityType {
                case .accounts: accountIds.insert(change.entityId)
                case .categories: categoryIds.insert(change.entityId)
                case .assetCategories: assetCategoryIds.insert(change.entityId)
                case .planningPlans: planIds.insert(change.entityId)
                default: break
                }
            }
        }
    }
}

enum PersonalSyncOwnershipValidator {
    static func evidence(
        scope: LocalStoreScope,
        entityType: SyncEntityType,
        entityId: String,
        ownershipPayload: [String: SyncJSONValue],
        snapshot: FinanceLocalSnapshot,
        trustedContext: PersonalOwnershipContext = .empty
    ) throws -> SyncOwnershipEvidence {
        let payloadEntityId = string(ownershipPayload["id"])
        guard scope.householdId == nil,
              !scope.viewerUserId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              UUID(uuidString: entityId) != nil,
              payloadEntityId == entityId || (entityType == .investmentMigrations && payloadEntityId == nil) else {
            throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
        }
        var index = PersonalOwnershipIndex(snapshot: snapshot)
        index.accountIds.formUnion(trustedContext.accountIds)
        index.categoryIds.formUnion(trustedContext.categoryIds)
        index.assetCategoryIds.formUnion(trustedContext.assetCategoryIds)
        index.planIds.formUnion(trustedContext.planIds)
        let references = try references(
            entityType: entityType,
            payload: ownershipPayload,
            viewerUserId: scope.viewerUserId,
            index: index
        )
        return SyncOwnershipEvidence(
            viewerUserId: scope.viewerUserId,
            subjectEntityType: entityType,
            subjectEntityId: entityId,
            referencedAccountIds: references.accounts.sorted(),
            referencedCategoryIds: references.categories.sorted(),
            referencedAssetCategoryIds: references.assetCategories.sorted(),
            referencedPlanIds: references.plans.sorted(),
            attestedPersonalPlanIds: references.plans.subtracting(PersonalOwnershipIndex(snapshot: snapshot).planIds).sorted(),
            attestedPersonalAccountIds: references.accounts.subtracting(PersonalOwnershipIndex(snapshot: snapshot).accountIds).sorted(),
            attestedPersonalCategoryIds: references.categories.subtracting(PersonalOwnershipIndex(snapshot: snapshot).categoryIds).sorted(),
            attestedPersonalAssetCategoryIds: references.assetCategories.subtracting(PersonalOwnershipIndex(snapshot: snapshot).assetCategoryIds).sorted()
        )
    }

    static func allows(
        mutation: PendingMutation,
        snapshot: FinanceLocalSnapshot
    ) -> Bool {
        guard mutation.scope.householdId == nil,
              mutation.scope.viewerUserId == snapshot.scope.viewerUserId,
              let evidence = mutation.ownershipEvidence,
              evidence.viewerUserId == mutation.scope.viewerUserId,
              evidence.subjectEntityType == mutation.entityType,
              evidence.subjectEntityId == mutation.entityId else {
            return false
        }
        guard (try? OfflineSyncPayloadContract.validateEnvelope(
            entityId: mutation.entityId,
            operation: mutation.operation,
            baseVersion: mutation.baseVersion
        )) != nil else {
            return false
        }
        guard (try? OfflineSyncPayloadContract.validate(
            payload: mutation.payload,
            entityType: mutation.entityType,
            operation: mutation.operation
        )) != nil else {
            return false
        }
        let index = PersonalOwnershipIndex(snapshot: snapshot)
        let knownPlanIds = index.planIds.union(evidence.attestedPersonalPlanIds)
        let knownAccountIds = index.accountIds.union(evidence.attestedPersonalAccountIds)
        let knownCategoryIds = index.categoryIds.union(evidence.attestedPersonalCategoryIds)
        let knownAssetCategoryIds = index.assetCategoryIds.union(evidence.attestedPersonalAssetCategoryIds)
        return Set(evidence.referencedAccountIds).isSubset(of: knownAccountIds)
            && Set(evidence.referencedCategoryIds).isSubset(of: knownCategoryIds)
            && Set(evidence.referencedAssetCategoryIds).isSubset(of: knownAssetCategoryIds)
            && Set(evidence.referencedPlanIds).isSubset(of: knownPlanIds)
    }

    static func allows(
        change: SyncChange,
        snapshot: FinanceLocalSnapshot,
        index: PersonalOwnershipIndex
    ) -> Bool {
        if let payload = change.payload {
            guard payloadMatchesEntity(payload, change: change) else { return false }
            return (try? references(
                entityType: change.entityType,
                payload: payload,
                viewerUserId: snapshot.scope.viewerUserId,
                index: index
            )) != nil
        }
        guard change.changeType == SyncOperation.delete.rawValue,
              let tombstone = change.tombstonePayload,
              string(tombstone["id"]) == change.entityId,
              string(tombstone["entityType"]) == change.entityType.rawValue else {
            return false
        }
        return ownsExistingEntity(
            entityType: change.entityType,
            entityId: change.entityId,
            snapshot: snapshot
        )
    }

    fileprivate struct References {
        var accounts: Set<String> = []
        var categories: Set<String> = []
        var assetCategories: Set<String> = []
        var plans: Set<String> = []
    }

    fileprivate static func references(
        entityType: SyncEntityType,
        payload: [String: SyncJSONValue],
        viewerUserId: String,
        index: PersonalOwnershipIndex
    ) throws -> References {
        guard hasNoHousehold(payload) else {
            throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
        }
        var result = References()
        switch entityType {
        case .accounts:
            guard string(payload["ownershipType"]) == OwnershipType.personal.rawValue,
                  ownerMatches(payload, viewerUserId: viewerUserId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
            if let assetCategoryId = string(payload["assetCategoryId"]) {
                guard index.assetCategoryIds.contains(assetCategoryId) else {
                    throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
                }
                result.assetCategories.insert(assetCategoryId)
            }
        case .categories:
            guard string(payload["scope"]) == CategoryScope.personal.rawValue,
                  ownerMatches(payload, viewerUserId: viewerUserId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
        case .assetCategories:
            guard string(payload["scopeType"]) == AssetCategoryScope.personal.rawValue,
                  ownerMatches(payload, viewerUserId: viewerUserId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
        case .transactions:
            guard let accountId = string(payload["accountId"]), index.accountIds.contains(accountId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
            result.accounts.insert(accountId)
            if let counterpartyId = string(payload["counterpartyAccountId"]) {
                guard index.accountIds.contains(counterpartyId) else {
                    throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
                }
                result.accounts.insert(counterpartyId)
            }
            if let categoryId = string(payload["categoryId"]) {
                guard index.categoryIds.contains(categoryId) else {
                    throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
                }
                result.categories.insert(categoryId)
            }
        case .planningPlans:
            guard string(payload["scope"]) == PlanningScope.personal.rawValue,
                  ownerMatches(payload, viewerUserId: viewerUserId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
        case .planningIncomeSources:
            guard let planId = string(payload["planId"]),
                  index.planIds.contains(planId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
            result.plans.insert(planId)
        case .planningAllocations:
            guard let planId = string(payload["planId"]),
                  index.planIds.contains(planId) else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
            result.plans.insert(planId)
            if let targetId = string(payload["targetId"]), let targetType = string(payload["targetType"]) {
                switch targetType {
                case AllocationTargetType.expense_category.rawValue:
                    guard index.categoryIds.contains(targetId) else { throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue) }
                    result.categories.insert(targetId)
                case AllocationTargetType.account.rawValue:
                    guard index.accountIds.contains(targetId) else { throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue) }
                    result.accounts.insert(targetId)
                case AllocationTargetType.asset.rawValue, AllocationTargetType.investment_asset_category.rawValue:
                    guard index.assetCategoryIds.contains(targetId) else { throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue) }
                    result.assetCategories.insert(targetId)
                default:
                    throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
                }
            }
        case .investmentMigrations:
            guard string(payload["scope"]) == AssetCategoryScope.personal.rawValue else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
            guard case .array(let accountValues)? = payload["accountIds"] else {
                throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
            }
            for value in accountValues {
                guard let accountId = string(value), index.accountIds.contains(accountId) else {
                    throw LocalStoreError.uncertainPersonalOwnership(entityType: entityType.rawValue)
                }
                result.accounts.insert(accountId)
            }
        }
        return result
    }

    fileprivate static func string(_ value: SyncJSONValue?) -> String? {
        guard case .string(let value)? = value else { return nil }
        return value
    }

    fileprivate static func hasNoHousehold(_ payload: [String: SyncJSONValue]) -> Bool {
        payload["householdId"] == nil || payload["householdId"] == .null
    }

    fileprivate static func ownerMatches(
        _ payload: [String: SyncJSONValue],
        viewerUserId: String
    ) -> Bool {
        return string(payload["ownerUserId"]) == viewerUserId
    }

    fileprivate static func payloadMatchesEntity(
        _ payload: [String: SyncJSONValue],
        change: SyncChange
    ) -> Bool {
        string(payload["id"]) == change.entityId
    }

    private static func ownsExistingEntity(
        entityType: SyncEntityType,
        entityId: String,
        snapshot: FinanceLocalSnapshot
    ) -> Bool {
        let index = PersonalOwnershipIndex(snapshot: snapshot)
        switch entityType {
        case .accounts:
            return index.accountIds.contains(entityId)
        case .categories:
            return index.categoryIds.contains(entityId)
        case .assetCategories:
            return index.assetCategoryIds.contains(entityId)
        case .transactions:
            guard let transaction = snapshot.transactions.first(where: { $0.entity.id == entityId })?.entity else { return false }
            return index.accountIds.contains(transaction.accountId)
                && transaction.counterpartyAccountId.map(index.accountIds.contains) != false
                && transaction.categoryId.map(index.categoryIds.contains) != false
        case .planningPlans:
            return index.planIds.contains(entityId)
        case .planningIncomeSources:
            guard let entity = snapshot.planningIncomeSources.first(where: { $0.entity.id == entityId })?.entity else { return false }
            return index.planIds.contains(entity.planId)
        case .planningAllocations:
            guard let entity = snapshot.planningAllocations.first(where: { $0.entity.id == entityId })?.entity else { return false }
            guard index.planIds.contains(entity.planId), let targetId = entity.targetId else { return false }
            switch entity.targetType {
            case .expense_category: return index.categoryIds.contains(targetId)
            case .account: return index.accountIds.contains(targetId)
            case .asset, .investment_asset_category: return index.assetCategoryIds.contains(targetId)
            }
        case .investmentMigrations:
            return false
        }
    }
}
