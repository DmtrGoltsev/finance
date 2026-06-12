package com.finance.mvp.capture

import com.finance.mvp.api.CaptureDraftCreateRequest

data class CaptureCandidate(
    val amount: String,
    val currency: String,
    val description: String?,
    val merchantName: String?,
    val capturedAt: String,
    val occurredAt: String,
    val captureSource: String,
    val idempotencyKey: String,
    val confidence: Double,
    val sourceAppPackage: String?,
    val sourceAppLabel: String?,
    val evidenceHash: String,
) {
    fun toCreateRequest(): CaptureDraftCreateRequest {
        return CaptureDraftCreateRequest(
            amount = amount,
            currency = currency,
            description = description,
            merchantName = merchantName,
            capturedAt = capturedAt,
            occurredDate = occurredAt.take(10),
            captureSource = captureSource,
            idempotencyKey = idempotencyKey,
            confidence = confidence,
            sourceAppPackage = sourceAppPackage,
            sourceAppLabel = sourceAppLabel,
            evidenceHash = evidenceHash,
        )
    }
}

data class CategoryAggregateCandidate(
    val externalLabel: String,
    val amount: String,
    val currency: String,
    val operationCount: Int,
    val capturedAt: String,
    val occurredAt: String,
    val idempotencyKey: String,
    val confidence: Double,
    val evidenceHash: String,
) {
    fun toCreateRequest(categoryId: String): CaptureDraftCreateRequest {
        return CaptureDraftCreateRequest(
            amount = amount,
            currency = currency,
            description = "Скрин: $externalLabel",
            merchantName = null,
            capturedAt = capturedAt,
            occurredDate = occurredAt.take(10),
            captureSource = "screenshot",
            idempotencyKey = idempotencyKey,
            confidence = confidence,
            sourceAppPackage = null,
            sourceAppLabel = "Photo Picker",
            evidenceHash = evidenceHash,
            categoryId = categoryId,
        )
    }
}

data class ScreenshotOcrParseResult(
    val aggregateCandidates: List<CategoryAggregateCandidate>,
    val singleCandidate: CaptureCandidate?,
)
