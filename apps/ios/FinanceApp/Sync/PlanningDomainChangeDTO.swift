import Foundation

/// The sync change log carries normalized planning records, not the expanded
/// planning-screen DTO returned by the planning endpoints.
enum PlanningDomainChangeDTO {
    static func plan(
        from payload: [String: SyncJSONValue],
        existing: PlanningPlan?
    ) throws -> PlanningPlan {
        let dto = try decode(PlanRecord.self, from: payload)
        return PlanningPlan(
            id: dto.id,
            scope: dto.scope,
            ownerUserId: dto.ownerUserId,
            month: dto.month,
            currency: dto.currency,
            householdId: dto.householdId,
            summary: existing?.summary ?? .empty,
            incomeSources: existing?.incomeSources ?? [],
            allocations: existing?.allocations ?? [],
            version: dto.version
        )
    }

    static func incomeSource(from payload: [String: SyncJSONValue]) throws -> PlanningIncomeSource {
        let dto = try decode(IncomeSourceRecord.self, from: payload)
        return PlanningIncomeSource(
            id: dto.id,
            planId: dto.planId,
            amount: dto.amount,
            source: dto.source,
            description: dto.description,
            dayOfMonth: dto.dayOfMonth,
            effectiveDate: dto.effectiveDate,
            confirmationState: dto.confirmationState,
            confirmedAt: dto.confirmedAt,
            version: dto.version
        )
    }

    static func allocation(from payload: [String: SyncJSONValue]) throws -> PlanningAllocation {
        let dto = try decode(AllocationRecord.self, from: payload)
        return PlanningAllocation(
            id: dto.id,
            planId: dto.planId,
            targetType: dto.targetType,
            targetId: dto.targetId,
            targetSnapshot: dto.targetSnapshot?.mapValues { JSONValue(syncValue: $0) },
            requiresAttention: dto.requiresAttention,
            attentionReason: dto.attentionReason,
            comment: dto.comment,
            allocationMode: dto.allocationMode,
            allocationValue: dto.allocationValue,
            recurrenceType: dto.recurrenceType,
            isSavingsGoal: dto.isSavingsGoal,
            goalTargetAmount: dto.goalTargetAmount,
            goalDueMonth: dto.goalDueMonth,
            goalMonthlyAmount: nil,
            calculatedAmount: dto.allocationMode == .amount ? dto.allocationValue : "0",
            actualAmount: nil,
            varianceAmount: nil,
            progressPercent: nil,
            progressStatus: nil,
            status: dto.recordStatus,
            version: dto.version
        )
    }

    private static func decode<T: Decodable>(
        _ type: T.Type,
        from payload: [String: SyncJSONValue]
    ) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: SyncJSONValue.data(from: payload))
        } catch {
            throw LocalStoreError.invalidPullPayload("\(T.self): \(error.localizedDescription)")
        }
    }

    private struct PlanRecord: Decodable {
        let id: String
        let scope: PlanningScope
        let ownerUserId: String?
        let householdId: String?
        let month: String
        let currency: CurrencyCode
        let version: Int?
    }

    private struct IncomeSourceRecord: Decodable {
        let id: String
        let planId: String
        let amount: String
        let source: String
        let description: String?
        let dayOfMonth: Int
        let effectiveDate: String?
        let confirmationState: IncomeConfirmationState
        let confirmedAt: String?
        let version: Int?

        private enum CodingKeys: String, CodingKey {
            case id, planId, amount, source, description, dayOfMonth
            case effectiveDate, confirmationState, confirmedAt, version
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            id = try container.decode(String.self, forKey: .id)
            planId = try container.decode(String.self, forKey: .planId)
            amount = try container.decode(String.self, forKey: .amount)
            source = try container.decode(String.self, forKey: .source)
            description = try container.decodeIfPresent(String.self, forKey: .description)
            dayOfMonth = try container.decode(Int.self, forKey: .dayOfMonth)
            effectiveDate = try container.decodeIfPresent(String.self, forKey: .effectiveDate)
            confirmationState = try container.decodeIfPresent(IncomeConfirmationState.self, forKey: .confirmationState) ?? .planned
            confirmedAt = try container.decodeIfPresent(String.self, forKey: .confirmedAt)
            version = try container.decodeIfPresent(Int.self, forKey: .version)
        }
    }

    private struct AllocationRecord: Decodable {
        let id: String
        let planId: String
        let targetType: AllocationTargetType
        let targetId: String?
        let targetSnapshot: [String: SyncJSONValue]?
        let requiresAttention: Bool
        let attentionReason: String?
        let comment: String?
        let allocationMode: AllocationMode
        let allocationValue: String
        let recurrenceType: AllocationRecurrenceType?
        let isSavingsGoal: Bool
        let goalTargetAmount: String?
        let goalDueMonth: String?
        let recordStatus: String?
        let version: Int?

        private enum CodingKeys: String, CodingKey {
            case id, planId, targetType, targetId, targetSnapshot
            case requiresAttention, attentionReason, comment, allocationMode, allocationValue
            case recurrenceType, isSavingsGoal, goalTargetAmount, goalDueMonth, recordStatus, version
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            id = try container.decode(String.self, forKey: .id)
            planId = try container.decode(String.self, forKey: .planId)
            targetType = try container.decode(AllocationTargetType.self, forKey: .targetType)
            targetId = try container.decodeIfPresent(String.self, forKey: .targetId)
            targetSnapshot = try container.decodeIfPresent([String: SyncJSONValue].self, forKey: .targetSnapshot)
            requiresAttention = try container.decodeIfPresent(Bool.self, forKey: .requiresAttention) ?? false
            attentionReason = try container.decodeIfPresent(String.self, forKey: .attentionReason)
            comment = try container.decodeIfPresent(String.self, forKey: .comment)
            allocationMode = try container.decode(AllocationMode.self, forKey: .allocationMode)
            allocationValue = try container.decode(String.self, forKey: .allocationValue)
            recurrenceType = try container.decodeIfPresent(AllocationRecurrenceType.self, forKey: .recurrenceType)
            isSavingsGoal = try container.decodeIfPresent(Bool.self, forKey: .isSavingsGoal) ?? false
            goalTargetAmount = try container.decodeIfPresent(String.self, forKey: .goalTargetAmount)
            goalDueMonth = try container.decodeIfPresent(String.self, forKey: .goalDueMonth)
            recordStatus = try container.decodeIfPresent(String.self, forKey: .recordStatus)
            version = try container.decodeIfPresent(Int.self, forKey: .version)
        }
    }
}

fileprivate extension PlanningSummary {
    static let empty = PlanningSummary(
        totalPlannedIncome: "0",
        totalConfirmedIncome: "0",
        totalAllocatedAmount: "0",
        unallocatedAmount: "0",
        previousMonthSurplus: "0",
        underallocated: false,
        overallocated: false
    )
}

fileprivate extension JSONValue {
    init(syncValue value: SyncJSONValue) {
        switch value {
        case .string(let value): self = .string(value)
        case .int(let value): self = .int(value)
        case .double(let value): self = .double(value)
        case .bool(let value): self = .bool(value)
        case .object(let value): self = .object(value.mapValues { JSONValue(syncValue: $0) })
        case .array(let value): self = .array(value.map { JSONValue(syncValue: $0) })
        case .null: self = .null
        }
    }
}
