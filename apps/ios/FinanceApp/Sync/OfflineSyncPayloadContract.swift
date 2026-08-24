import Foundation

enum OfflineSyncPayloadContract {
    static func payload<Request: Encodable>(
        entityType: SyncEntityType,
        operation: SyncOperation,
        request: Request,
        planId: String? = nil
    ) throws -> [String: SyncJSONValue] {
        var payload = try SyncJSONValue.object(from: request)
        if operation == .create,
           (entityType == .planningIncomeSources || entityType == .planningAllocations) {
            guard let planId, !planId.isEmpty else {
                throw LocalStoreError.invalidOfflinePayload("planId is required")
            }
            payload["planId"] = .string(planId)
        }
        try validate(payload: payload, entityType: entityType, operation: operation)
        return payload
    }

    static func validate(
        payload: [String: SyncJSONValue]?,
        entityType: SyncEntityType,
        operation: SyncOperation
    ) throws {
        guard let specification = specification(entityType: entityType, operation: operation) else {
            throw LocalStoreError.unsupportedOfflineMutation(
                entityType: entityType.rawValue,
                operation: operation.rawValue
            )
        }
        guard specification.requiresPayload else {
            guard payload == nil || payload?.isEmpty == true else {
                throw LocalStoreError.invalidOfflinePayload(
                    "\(entityType.rawValue):\(operation.rawValue) must not contain payload"
                )
            }
            return
        }
        guard let payload else {
            throw LocalStoreError.invalidOfflinePayload(
                "\(entityType.rawValue):\(operation.rawValue) requires payload"
            )
        }
        if operation == .update, payload.isEmpty {
            throw LocalStoreError.invalidOfflinePayload("update payload must contain at least one changed field")
        }

        let keys = Set(payload.keys)
        let extras = keys.subtracting(specification.allowedKeys)
        guard extras.isEmpty else {
            throw LocalStoreError.invalidOfflinePayload(
                "Unsupported keys: \(extras.sorted().joined(separator: ", "))"
            )
        }
        let missing = specification.requiredKeys.subtracting(keys)
        guard missing.isEmpty else {
            throw LocalStoreError.invalidOfflinePayload(
                "Missing keys: \(missing.sorted().joined(separator: ", "))"
            )
        }

        if entityType == .transactions, operation == .create,
           payload["transactionDate"] == nil, payload["occurredAt"] == nil {
            throw LocalStoreError.invalidOfflinePayload("transactionDate or occurredAt is required")
        }
    }

    static func validateEnvelope(
        entityId: String,
        operation: SyncOperation,
        baseVersion: Int?
    ) throws {
        guard UUID(uuidString: entityId) != nil else {
            throw LocalStoreError.invalidOfflinePayload("entityId must be UUID")
        }
        if operation == .create {
            guard baseVersion == nil else {
                throw LocalStoreError.invalidOfflinePayload("create must not contain baseVersion")
            }
        } else {
            guard let baseVersion, baseVersion >= 1 else {
                throw LocalStoreError.invalidOfflinePayload("baseVersion is required outside create")
            }
        }
    }

    private struct Specification {
        let allowedKeys: Set<String>
        let requiredKeys: Set<String>
        let requiresPayload: Bool
    }

    private static func specification(
        entityType: SyncEntityType,
        operation: SyncOperation
    ) -> Specification? {
        let noPayload = Specification(allowedKeys: [], requiredKeys: [], requiresPayload: false)
        switch (entityType, operation) {
        case (.transactions, .create):
            return required(
                ["transactionType", "accountId", "amount", "currency", "sourceType"],
                optional: ["counterpartyAccountId", "categoryId", "occurredAt", "transactionDate", "description"]
            )
        case (.transactions, .update):
            return optional([
                "transactionType", "accountId", "counterpartyAccountId", "categoryId", "amount",
                "currency", "occurredAt", "transactionDate", "description", "sourceType",
            ])
        case (.transactions, .delete), (.transactions, .restore):
            return noPayload

        case (.accounts, .create):
            return required(
                ["name", "accountType", "ownershipType", "currency", "initialBalance"],
                optional: ["householdId", "assetCategoryId", "isPaymentAccount"]
            )
        case (.accounts, .update):
            return optional(["name", "currency", "accountType", "assetCategoryId", "isPaymentAccount"])
        case (.accounts, .archive), (.accounts, .delete), (.accounts, .restore):
            return noPayload

        case (.categories, .create):
            return required(["name", "type", "scope"], optional: ["householdId", "iconKey", "color"])
        case (.categories, .update):
            return optional(["name", "iconKey", "color"])
        case (.categories, .archive), (.categories, .delete), (.categories, .restore):
            return noPayload

        case (.assetCategories, .create):
            return required(
                ["name", "scopeType", "currency"],
                optional: ["householdId", "assetType", "iconKey", "manualAmount", "isInvestment"]
            )
        case (.assetCategories, .update):
            return optional(["name", "manualAmount", "assetType", "iconKey", "isInvestment"])
        case (.assetCategories, .archive), (.assetCategories, .delete), (.assetCategories, .restore):
            return noPayload

        case (.investmentMigrations, .create):
            return required(
                ["assetCategoryId", "name", "assetType", "currency", "accountIds", "accountVersions"],
                optional: ["icon", "color", "scope", "householdId"]
            )

        case (.planningPlans, .create):
            return required(["scope", "month", "currency"], optional: ["householdId"])

        case (.planningIncomeSources, .create):
            return required(
                ["planId", "amount", "source", "dayOfMonth"],
                optional: ["description"]
            )
        case (.planningIncomeSources, .update):
            return optional(["amount", "source", "description", "dayOfMonth"])
        case (.planningIncomeSources, .confirm), (.planningIncomeSources, .delete):
            return noPayload

        case (.planningAllocations, .create):
            return required(
                ["planId", "targetType", "targetId", "allocationMode", "allocationValue"],
                optional: ["comment", "recurrenceType", "isSavingsGoal", "goalTargetAmount", "goalDueMonth"]
            )
        case (.planningAllocations, .update):
            return optional([
                "targetType", "targetId", "comment", "allocationMode", "allocationValue",
                "recurrenceType", "isSavingsGoal", "goalTargetAmount", "goalDueMonth",
            ])
        case (.planningAllocations, .delete):
            return noPayload
        default:
            return nil
        }
    }

    private static func required(_ required: Set<String>, optional: Set<String>) -> Specification {
        Specification(allowedKeys: required.union(optional), requiredKeys: required, requiresPayload: true)
    }

    private static func optional(_ keys: Set<String>) -> Specification {
        Specification(allowedKeys: keys, requiredKeys: [], requiresPayload: true)
    }
}
