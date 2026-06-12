import Foundation

enum CaptureDraftStatus: String, Codable, Sendable {
    case pending, confirmed, discarded
}

enum CaptureSource: String, Codable, Sendable {
    case screenshot
}

struct CaptureDraft: Codable, Identifiable, Sendable {
    let id: String
    let status: CaptureDraftStatus
    let idempotencyKey: String
    let captureSource: CaptureSource
    let capturedAt: String
    let occurredAt: String?
    let occurredDate: String?
    let amount: String
    let currency: CurrencyCode
    let description: String
    let merchantName: String?
    let accountId: String?
    let categoryId: String?
    let transactionId: String?
    let confidence: String?
    let sourceAppPackage: String?
    let sourceAppLabel: String?
    let evidenceHash: String?
    let version: Int?
}

struct CaptureDraftCreateRequest: Codable, Sendable {
    let idempotencyKey: String
    let captureSource: CaptureSource
    let capturedAt: String
    let occurredAt: String?
    let occurredDate: String?
    let amount: String
    let currency: CurrencyCode
    let description: String
    let merchantName: String?
    let accountId: String?
    let categoryId: String?
    let confidence: String?
    let sourceAppPackage: String?
    let sourceAppLabel: String?
    let evidenceHash: String?
}

struct CaptureDraftUpdateRequest: Codable, Sendable {
    let occurredAt: String?
    let occurredDate: String?
    let amount: String?
    let currency: CurrencyCode?
    let description: String?
    let merchantName: String?
    let accountId: String?
    let categoryId: String?
    let confidence: String?
}

struct ScreenshotOcrCandidate: Codable, Identifiable, Sendable {
    var id: String { idempotencyKey }
    let candidateType: String
    let externalLabel: String
    let amount: String
    let currency: CurrencyCode
    let operationCount: Int
    let description: String
    let confidence: String
    let idempotencyKey: String
    let evidenceHash: String
    let suggestedCategoryId: String?

    enum CodingKeys: String, CodingKey {
        case candidateType, amount, currency, operationCount
        case description, confidence, idempotencyKey, evidenceHash
        case suggestedCategoryId
        case externalLabel = "categoryAggregate"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        candidateType = try c.decode(String.self, forKey: .candidateType)
        amount = try c.decodeStringDecimal(forKey: .amount)
        currency = try c.decode(CurrencyCode.self, forKey: .currency)
        operationCount = try c.decode(Int.self, forKey: .operationCount)
        description = try c.decode(String.self, forKey: .description)
        confidence = try c.decodeStringDecimal(forKey: .confidence)
        idempotencyKey = try c.decode(String.self, forKey: .idempotencyKey)
        evidenceHash = try c.decode(String.self, forKey: .evidenceHash)
        suggestedCategoryId = try c.decodeIfPresent(String.self, forKey: .suggestedCategoryId)
        if let agg = try? c.decodeNestedObject(forKey: .externalLabel) {
            externalLabel = agg["externalLabel"] as? String ?? ""
        } else {
            externalLabel = try c.decodeIfPresent(String.self, forKey: .externalLabel) ?? ""
        }
    }
}

private extension KeyedDecodingContainer {
    func decodeStringDecimal(forKey key: Key) throws -> String {
        if let s = try? decode(String.self, forKey: key) { return s }
        if let d = try? decode(Double.self, forKey: key) { return String(d) }
        return "0"
    }

    func decodeNestedObject(forKey key: Key) throws -> [String: Any]? {
        guard let dict = try? decode([String: AnyCodableValue].self, forKey: key) else { return nil }
        return dict.mapValues { $0.value }
    }
}

private struct AnyCodableValue: Codable {
    let value: Any

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { value = s }
        else if let i = try? c.decode(Int.self) { value = i }
        else if let d = try? c.decode(Double.self) { value = d }
        else if let b = try? c.decode(Bool.self) { value = b }
        else { value = "" }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        if let v = value as? String { try c.encode(v) }
        else if let v = value as? Int { try c.encode(v) }
        else if let v = value as? Double { try c.encode(v) }
        else if let v = value as? Bool { try c.encode(v) }
        else { try c.encodeNil() }
    }
}

struct ScreenshotOcrResponse: Codable, Sendable {
    let captureSource: CaptureSource
    let parseVersion: String
    let recognizedAt: String
    let items: [ScreenshotOcrCandidate]
    let warnings: [ScreenshotOcrWarning]
}

struct ScreenshotOcrWarning: Codable, Sendable {
    let code: String
    let message: String
}
