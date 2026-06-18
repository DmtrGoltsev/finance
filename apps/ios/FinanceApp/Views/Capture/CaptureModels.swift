import Foundation

struct ScreenshotAggregateDraftUi: Identifiable, Sendable {
    var id: String { candidate.idempotencyKey }
    let candidate: ScreenshotOcrCandidate
    var selectedCategoryId: String
    var include: Bool
}

extension ScreenshotOcrCandidate {
    func toCreateRequest(categoryId: String) -> CaptureDraftCreateRequest {
        CaptureDraftCreateRequest(
            idempotencyKey: idempotencyKey,
            captureSource: .screenshot,
            capturedAt: DateHelpers.nowISO(),
            occurredAt: nil,
            occurredDate: nil,
            amount: amount,
            currency: currency,
            description: externalLabel,
            merchantName: nil,
            accountId: nil,
            categoryId: categoryId,
            confidence: confidence,
            sourceAppPackage: nil,
            sourceAppLabel: nil,
            evidenceHash: evidenceHash
        )
    }
}
