import Foundation

let financeSyncSchemaVersion = 1

enum SyncJSONValue: Codable, Equatable, Sendable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case object([String: SyncJSONValue])
    case array([SyncJSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Int.self) {
            self = .int(value)
        } else if let value = try? container.decode(Double.self) {
            self = .double(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: SyncJSONValue].self) {
            self = .object(value)
        } else {
            self = .array(try container.decode([SyncJSONValue].self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .int(let value):
            try container.encode(value)
        case .double(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }

    static func object<T: Encodable>(from value: T) throws -> [String: SyncJSONValue] {
        let data = try JSONEncoder().encode(value)
        let json = try JSONSerialization.jsonObject(with: data)
        if let object = json as? [String: Any] {
            return object.mapValues(Self.fromAny)
        }
        return ["value": Self.fromAny(json)]
    }

    static func data(from object: [String: SyncJSONValue]) throws -> Data {
        let jsonObject = object.mapValues { $0.jsonObject }
        return try JSONSerialization.data(withJSONObject: jsonObject)
    }

    private var jsonObject: Any {
        switch self {
        case .string(let value):
            return value
        case .int(let value):
            return value
        case .double(let value):
            return value
        case .bool(let value):
            return value
        case .object(let value):
            return value.mapValues { $0.jsonObject }
        case .array(let value):
            return value.map { $0.jsonObject }
        case .null:
            return NSNull()
        }
    }

    private static func fromAny(_ value: Any) -> SyncJSONValue {
        switch value {
        case is NSNull:
            return .null
        case let value as String:
            return .string(value)
        case let value as Bool:
            return .bool(value)
        case let value as Int:
            return .int(value)
        case let value as Double:
            return .double(value)
        case let value as NSNumber:
            return .double(value.doubleValue)
        case let value as [String: Any]:
            return .object(value.mapValues(Self.fromAny))
        case let value as [Any]:
            return .array(value.map(Self.fromAny))
        default:
            return .string(String(describing: value))
        }
    }
}

enum SyncEntityType: String, Codable, CaseIterable, Sendable {
    case transactions
    case accounts
    case categories
    case assetCategories = "asset_categories"
    case investmentMigrations = "investment_migrations"
    case planningPlans = "planning_plans"
    case planningIncomeSources = "planning_income_sources"
    case planningAllocations = "planning_allocations"

    var isPlanningEntity: Bool {
        switch self {
        case .planningPlans, .planningIncomeSources, .planningAllocations:
            return true
        default:
            return false
        }
    }
}

enum SyncOperation: String, Codable, CaseIterable, Sendable {
    case create
    case update
    case archive
    case delete
    case restore
    case confirm
}

enum SyncMutationRemoteStatus: String, Codable, Sendable {
    case applied
    case rejected
}

struct SyncMutationRequest: Codable, Sendable {
    let clientMutationId: String
    let entityType: SyncEntityType
    let entityId: String
    let operation: SyncOperation
    let baseVersion: Int?
    let payload: [String: SyncJSONValue]?
}

struct SyncPushRequest: Codable, Sendable {
    let deviceId: String
    let clientSchemaVersion: Int
    let mutations: [SyncMutationRequest]

    init(deviceId: String, clientSchemaVersion: Int = financeSyncSchemaVersion, mutations: [SyncMutationRequest]) {
        self.deviceId = deviceId
        self.clientSchemaVersion = clientSchemaVersion
        self.mutations = mutations
    }
}

struct SyncMutationResult: Codable, Sendable {
    let clientMutationId: String
    let entityType: SyncEntityType
    let entityId: String
    let operation: SyncOperation
    let status: SyncMutationRemoteStatus
    let serverVersion: Int?
    let changeSeq: Int64?
    let errorCode: String?
    let message: String?
    let data: [String: SyncJSONValue]?
}

struct SyncPushResponse: Codable, Sendable {
    let deviceId: String
    let serverTime: String
    let results: [SyncMutationResult]
}

enum SyncPushResultCorrelation {
    static func matches(_ result: SyncMutationResult, mutation: PendingMutation) -> Bool {
        result.clientMutationId == mutation.clientMutationId &&
            result.entityType == mutation.entityType &&
            result.entityId == mutation.entityId &&
            result.operation == mutation.operation
    }
}

struct SyncPullRequest: Codable, Sendable {
    let deviceId: String
    let clientSchemaVersion: Int
    let cursor: Int64
    let limit: Int
    let entityTypes: [SyncEntityType]?

    init(
        deviceId: String,
        clientSchemaVersion: Int = financeSyncSchemaVersion,
        cursor: Int64 = 0,
        limit: Int = 100,
        entityTypes: [SyncEntityType]? = nil
    ) {
        self.deviceId = deviceId
        self.clientSchemaVersion = clientSchemaVersion
        self.cursor = cursor
        self.limit = limit
        self.entityTypes = entityTypes
    }
}

struct SyncChange: Codable, Identifiable, Sendable {
    var id: String { "\(seq):\(entityType.rawValue):\(entityId)" }
    let seq: Int64
    let entityType: SyncEntityType
    let entityId: String
    let changeType: String
    let entityVersion: Int?
    let entityUpdatedAt: String?
    let changedByUserId: String?
    let clientMutationId: String?
    let payload: [String: SyncJSONValue]?
    let tombstonePayload: [String: SyncJSONValue]?
    let createdAt: String
}

struct SyncPullResponse: Codable, Sendable {
    let changes: [SyncChange]
    let nextCursor: Int64
    let hasMore: Bool
    let serverTime: String
}

enum OnlineOnlySyncOperation: String, Codable, CaseIterable, Sendable {
    case screenshotOCR = "screenshot_ocr"
    case captureUpload = "capture_upload"
    case captureDraft = "capture_draft"
    case copyPlan = "copy_plan"
    case planningHistoryMutation = "planning_history_mutation"
    case planningTargetRepair = "planning_target_repair"
}

enum SyncQueuePolicy {
    static func isSyncable(entityType: SyncEntityType, operation: SyncOperation) -> Bool {
        switch (entityType, operation) {
        case (.transactions, .create), (.transactions, .update), (.transactions, .delete), (.transactions, .restore),
             (.accounts, .create), (.accounts, .update), (.accounts, .archive), (.accounts, .delete), (.accounts, .restore),
             (.categories, .create), (.categories, .update), (.categories, .archive), (.categories, .delete), (.categories, .restore),
             (.assetCategories, .create), (.assetCategories, .update), (.assetCategories, .archive), (.assetCategories, .delete), (.assetCategories, .restore),
             (.investmentMigrations, .create),
             (.planningPlans, .create),
             (.planningIncomeSources, .create), (.planningIncomeSources, .update), (.planningIncomeSources, .confirm), (.planningIncomeSources, .delete),
             (.planningAllocations, .create), (.planningAllocations, .update), (.planningAllocations, .delete):
            return true
        default:
            return false
        }
    }

    static func onlineOnlyReason(_ operation: OnlineOnlySyncOperation) -> String {
        switch operation {
        case .screenshotOCR, .captureUpload, .captureDraft:
            return "OCR и загрузка чеков доступны только онлайн. Сырые изображения, OCR-текст и OCR-payload нельзя сохранять локально."
        case .copyPlan:
            return "Копирование плана доступно только онлайн, потому что зависит от текущей серверной истории и прав доступа."
        case .planningHistoryMutation:
            return "История планирования является производной моделью чтения и не изменяется из offline-очереди."
        case .planningTargetRepair:
            return "Восстановление цели планирования зависит от текущего состояния сервера и не синхронизируется offline."
        }
    }
}

enum SyncIssueStatus: String, Codable, Sendable {
    case failed
    case rejected
}

enum SyncIssueDecision: String, Codable, Sendable {
    case retryAllowed
    case editOrDiscardOnly
}

struct SyncIssue: Codable, Identifiable, Sendable {
    let id: String
    let mutationId: String?
    let entityType: SyncEntityType?
    let entityId: String?
    let operation: SyncOperation?
    let status: SyncIssueStatus
    let decision: SyncIssueDecision
    let title: String
    let safeDescription: String
    let errorCode: String?
    let attempts: Int
    let createdAt: String
    let updatedAt: String

    static func failed(from mutation: PendingMutation, message: String?) -> SyncIssue {
        let now = Date().ISO8601Format()
        return SyncIssue(
            id: "issue-\(mutation.clientMutationId)",
            mutationId: mutation.clientMutationId,
            entityType: mutation.entityType,
            entityId: mutation.entityId,
            operation: mutation.operation,
            status: .failed,
            decision: .retryAllowed,
            title: "Синхронизация не удалась",
            safeDescription: SyncSafeMessage.describe(message),
            errorCode: nil,
            attempts: mutation.attemptCount,
            createdAt: now,
            updatedAt: now
        )
    }

    static func rejected(from mutation: PendingMutation, result: SyncMutationResult) -> SyncIssue {
        let now = Date().ISO8601Format()
        return SyncIssue(
            id: "issue-\(mutation.clientMutationId)",
            mutationId: mutation.clientMutationId,
            entityType: mutation.entityType,
            entityId: mutation.entityId,
            operation: mutation.operation,
            status: .rejected,
            decision: .editOrDiscardOnly,
            title: "Синхронизация отклонена",
            safeDescription: SyncSafeMessage.describe(result.message ?? result.errorCode),
            errorCode: result.errorCode,
            attempts: mutation.attemptCount,
            createdAt: now,
            updatedAt: now
        )
    }
}

enum SyncSafeMessage {
    static func describe(_ message: String?) -> String {
        let trimmed = (message ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return "Безопасная причина не указана. Повторите попытку, когда соединение стабильно."
        }
        if trimmed.localizedCaseInsensitiveContains("not ready") {
            return "Синхронизация пока не готова. Повторите попытку после обновления данных."
        }
        if trimmed.localizedCaseInsensitiveContains("offline changes") {
            return "Есть локальные изменения, ожидающие синхронизации."
        }
        if trimmed.localizedCaseInsensitiveContains("offline") ||
            trimmed.localizedCaseInsensitiveContains("network") ||
            trimmed.localizedCaseInsensitiveContains("internet connection") ||
            trimmed.localizedCaseInsensitiveContains("cannot connect") ||
            trimmed.localizedCaseInsensitiveContains("timed out") ||
            trimmed.localizedCaseInsensitiveContains("cancelled") {
            return "Нет стабильного соединения. Изменение останется в очереди и повторится позже."
        }
        if trimmed.localizedCaseInsensitiveContains("unauthorized") || trimmed.contains("401") {
            return "Сессия истекла. Войдите снова."
        }
        if trimmed.localizedCaseInsensitiveContains("forbidden") || trimmed.contains("403") {
            return "Недостаточно прав для синхронизации этого изменения."
        }
        if trimmed.localizedCaseInsensitiveContains("not found") || trimmed.contains("404") {
            return "Запись уже недоступна или была удалена."
        }
        if trimmed.localizedCaseInsensitiveContains("validation") || trimmed.contains("422") || trimmed.contains("400") {
            return "Сервер отклонил изменение. Проверьте данные в форме и повторите действие."
        }
        if trimmed.contains("{") || trimmed.contains("}") || trimmed.contains("[") || trimmed.contains("]") {
            return "Сервер отклонил изменение. Проверьте запись и повторите действие из обычной формы."
        }
        if trimmed.localizedCaseInsensitiveContains("amount") ||
            trimmed.localizedCaseInsensitiveContains("balance") ||
            trimmed.localizedCaseInsensitiveContains("payload") ||
            trimmed.localizedCaseInsensitiveContains("token") ||
            trimmed.localizedCaseInsensitiveContains("email") {
            return "Изменение нельзя безопасно синхронизировать. Проверьте запись и повторите попытку."
        }
        if trimmed.range(of: "[A-Za-z]", options: .regularExpression) != nil {
            return "Синхронизация не прошла. Проверьте запись и повторите попытку."
        }
        return String(trimmed.prefix(180))
    }
}

struct SyncSessionLease: Codable, Hashable, Sendable {
    let viewerUserId: String
    let sessionId: String?
    let generation: UInt64
    let identityNonce: String

    init(
        viewerUserId: String,
        sessionId: String? = nil,
        generation: UInt64,
        identityNonce: String = UUID().uuidString
    ) {
        self.viewerUserId = viewerUserId
        self.sessionId = sessionId
        self.generation = generation
        self.identityNonce = identityNonce
    }
}

protocol SyncSessionLeaseProvider: Sendable {
    func currentLease(for viewerUserId: String) async -> SyncSessionLease?
    func isCurrent(_ lease: SyncSessionLease) async -> Bool
}

actor SyncSessionLeaseCoordinator: SyncSessionLeaseProvider {
    private var generation: UInt64 = 0
    private var lease: SyncSessionLease?

    @discardableResult
    func activate(viewerUserId: String, sessionId: String? = nil) -> SyncSessionLease {
        generation &+= 1
        let next = SyncSessionLease(
            viewerUserId: viewerUserId,
            sessionId: sessionId,
            generation: generation
        )
        lease = next
        return next
    }

    func invalidate() {
        generation &+= 1
        lease = nil
    }

    func currentLease(for viewerUserId: String) -> SyncSessionLease? {
        guard lease?.viewerUserId == viewerUserId else { return nil }
        return lease
    }

    func isCurrent(_ candidate: SyncSessionLease) -> Bool {
        lease == candidate && candidate.generation == generation
    }
}

enum SyncSessionLeaseError: Error, LocalizedError, Equatable {
    case missing(viewerUserId: String)
    case stale

    var errorDescription: String? {
        switch self {
        case .missing:
            return "Активная сессия синхронизации отсутствует."
        case .stale:
            return "Результат синхронизации относится к завершённой сессии и был отброшен."
        }
    }
}
