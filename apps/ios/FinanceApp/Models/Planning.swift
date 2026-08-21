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
