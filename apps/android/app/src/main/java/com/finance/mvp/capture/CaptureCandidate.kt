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
            occurredAt = occurredAt,
            captureSource = captureSource,
            idempotencyKey = idempotencyKey,
            confidence = confidence,
            sourceAppPackage = sourceAppPackage,
            sourceAppLabel = sourceAppLabel,
            evidenceHash = evidenceHash,
        )
    }
}

