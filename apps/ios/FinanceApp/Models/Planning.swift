import Foundation

enum PlanningScope: String, Codable, Sendable {
    case personal, household
}

enum IncomeConfirmationState: String, Codable, Sendable {
    case planned, confirmed
}

enum AllocationTargetType: String, Codable, Sendable {
    case expense_category, account, asset, investment_asset_category
}

enum AllocationMode: String, Codable, Sendable {
    case amount, percent
}

enum AllocationRecurrenceType: String, Codable, Sendable {
    case regular, one_off
}

enum AllocationProgressStatus: String, Codable, Sendable {
    case on_track, needs_attention, no_actuals, target_attention, not_applicable
}

enum JSONValue: Codable, Sendable, Equatable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    var stringValue: String? {
        if case .string(let v) = self { return v }
        return nil
    }
}

struct PlanningPlan: Codable, Identifiable, Sendable {
    let id: String
    let scope: PlanningScope
    let ownerUserId: String?
    let month: String
    let currency: CurrencyCode
    let householdId: String?
    let summary: PlanningSummary
    let incomeSources: [PlanningIncomeSource]
    let allocations: [PlanningAllocation]
    let version: Int?
}

struct PlanningSummary: Codable, Sendable {
    let totalPlannedIncome: String
    let totalConfirmedIncome: String
    let totalAllocatedAmount: String
    let unallocatedAmount: String
    let previousMonthSurplus: String
    let underallocated: Bool
    let overallocated: Bool
}

struct PlanningPlanSummaryDTO: Decodable, Sendable {
    let id: String
    let scope: PlanningScope
    let ownerUserId: String?
    let householdId: String?
    let month: String
    let currency: CurrencyCode
    let summary: PlanningSummary
    let createdAt: String
    let updatedAt: String
    let version: Int

    var historyItem: PlanningPlanHistoryItem {
        PlanningPlanHistoryItem(
            id: id,
            scope: scope,
            ownerUserId: ownerUserId,
            householdId: householdId,
            month: month,
            currency: currency,
            summary: summary,
            version: version,
            detail: nil
        )
    }
}

struct PlanningPlanHistoryItem: Identifiable, Sendable {
    let id: String
    let scope: PlanningScope
    let ownerUserId: String?
    let householdId: String?
    let month: String
    let currency: CurrencyCode
    let summary: PlanningSummary
    let version: Int?
    let detail: PlanningPlan?

    init(plan: PlanningPlan) {
        id = plan.id
        scope = plan.scope
        ownerUserId = plan.ownerUserId
        householdId = plan.householdId
        month = plan.month
        currency = plan.currency
        summary = plan.summary
        version = plan.version
        detail = plan
    }

    fileprivate init(
        id: String,
        scope: PlanningScope,
        ownerUserId: String?,
        householdId: String?,
        month: String,
        currency: CurrencyCode,
        summary: PlanningSummary,
        version: Int?,
        detail: PlanningPlan?
    ) {
        self.id = id
        self.scope = scope
        self.ownerUserId = ownerUserId
        self.householdId = householdId
        self.month = month
        self.currency = currency
        self.summary = summary
        self.version = version
        self.detail = detail
    }

    func resolvedDetail(
        fetch: (String) async throws -> PlanningPlan
    ) async throws -> PlanningPlan {
        if let detail { return detail }
        return try await fetch(id)
    }
}

struct PlanningIncomeSource: Codable, Identifiable, Sendable {
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
}

struct PlanningAllocation: Codable, Identifiable, Sendable {
    let id: String
    let planId: String
    let targetType: AllocationTargetType
    let targetId: String?
    let targetSnapshot: [String: JSONValue]?
    let requiresAttention: Bool
    let attentionReason: String?
    let comment: String?
    let allocationMode: AllocationMode
    let allocationValue: String
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool
    let goalTargetAmount: String?
    let goalDueMonth: String?
    let goalMonthlyAmount: String?
    let calculatedAmount: String
    let actualAmount: String?
    let varianceAmount: String?
    let progressPercent: String?
    let progressStatus: AllocationProgressStatus?
    let status: String?
    let version: Int?
}

struct PlanningPlanCreateRequest: Codable, Sendable {
    let scope: PlanningScope
    let month: String
    let currency: CurrencyCode
    let householdId: String?
}

struct PlanningPlanCopyRequest: Codable, Sendable {
    let targetMonth: String
}

struct PlanningIncomeSourceCreateRequest: Codable, Sendable {
    let amount: String
    let source: String
    let description: String?
    let dayOfMonth: Int
}

struct PlanningIncomeSourceUpdateRequest: Codable, Sendable {
    let amount: String?
    let source: String?
    let description: String?
    let dayOfMonth: Int?
    let version: Int?
}

struct PlanningIncomeSourceOfflineUpdateRequest: Codable, Sendable {
    let amount: String?
    let source: String?
    let description: String?
    let dayOfMonth: Int?

    init(_ request: PlanningIncomeSourceUpdateRequest) {
        amount = request.amount
        source = request.source
        description = request.description
        dayOfMonth = request.dayOfMonth
    }
}

struct PlanningAllocationCreateRequest: Codable, Sendable {
    let targetType: AllocationTargetType
    let targetId: String
    let comment: String?
    let allocationMode: AllocationMode
    let allocationValue: String
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool?
    let goalTargetAmount: String?
    let goalDueMonth: String?
}

struct PlanningAllocationUpdateRequest: Codable, Sendable {
    let targetType: AllocationTargetType?
    let targetId: String?
    let comment: String?
    let allocationMode: AllocationMode?
    let allocationValue: String?
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool?
    let goalTargetAmount: String?
    let goalDueMonth: String?
    let version: Int?
}

struct PlanningAllocationOfflineUpdateRequest: Codable, Sendable {
    let targetType: AllocationTargetType?
    let targetId: String?
    let comment: String?
    let allocationMode: AllocationMode?
    let allocationValue: String?
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool?
    let goalTargetAmount: String?
    let goalDueMonth: String?

    init(_ request: PlanningAllocationUpdateRequest) {
        targetType = request.targetType
        targetId = request.targetId
        comment = request.comment
        allocationMode = request.allocationMode
        allocationValue = request.allocationValue
        recurrenceType = request.recurrenceType
        isSavingsGoal = request.isSavingsGoal
        goalTargetAmount = request.goalTargetAmount
        goalDueMonth = request.goalDueMonth
    }
}
