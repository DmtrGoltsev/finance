package com.finance.mvp.capture

import java.math.BigDecimal
import java.math.RoundingMode
import java.security.MessageDigest
import java.time.Instant
import java.util.Locale

object CaptureParser {
    private val expenseSignals = listOf(
        "purchase",
        "payment",
        "paid",
        "spent",
        "debit",
        "card charge",
        "spisanie",
        "oplata",
        "pokupka",
        "списание",
        "оплата",
        "покупка",
        "потрачено",
    )
    private val incomeSignals = listOf(
        "refund",
        "reversal",
        "cashback",
        "deposit",
        "credited",
        "income",
        "salary",
        "vozvrat",
        "zachislen",
        "popolnen",
        "возврат",
        "зачислен",
        "зачисление",
        "поступление",
        "пополнение",
        "зарплата",
    )
    private val amountAfterRegex = Regex(
        """(?i)(\d[\d\s.,]*\d|\d)(?:\s*)(₽|руб\.?|rub|rur|usd|\$|eur|€)\b?""",
    )
    private val amountBeforeRegex = Regex(
        """(?i)(₽|руб\.?|rub|rur|usd|\$|eur|€)(?:\s*)(\d[\d\s.,]*\d|\d)\b""",
    )
    private val merchantPatterns = listOf(
        Regex("""(?i)\b(?:at|in)\s+([A-Za-z0-9][A-Za-z0-9 ._&'-]{1,48})"""),
        Regex("""(?i)\bmerchant[:\s]+([A-Za-z0-9][A-Za-z0-9 ._&'-]{1,48})"""),
        Regex("""(?i)\b(?:v|vo|в)\s+([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 ._&'-]{1,48})"""),
        Regex("""(?i)\b(?:место|магазин)[:\s]+([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 ._&'-]{1,48})"""),
    )

    fun parseSms(
        body: String,
        sender: String?,
        receivedAtMillis: Long,
    ): CaptureCandidate? {
        return parse(
            text = body,
            title = null,
            capturedAtMillis = receivedAtMillis,
            source = "sms",
            sourceAppPackage = null,
            sourceAppLabel = "SMS",
        )
    }

    fun parseNotification(
        title: String?,
        text: String?,
        packageName: String,
        appLabel: String?,
        postedAtMillis: Long,
    ): CaptureCandidate? {
        val joined = listOfNotNull(title, text).joinToString(" ").trim()
        if (joined.isBlank()) {
            return null
        }
        return parse(
            text = joined,
            title = title,
            capturedAtMillis = postedAtMillis,
            source = "notification",
            sourceAppPackage = packageName.take(160),
            sourceAppLabel = appLabel?.take(80),
        )
    }

    fun syntheticCandidate(nowMillis: Long = System.currentTimeMillis()): CaptureCandidate {
        return parseNotification(
            title = "Payment",
            text = "Paid 12.34 USD at Test Market",
            packageName = "com.finance.synthetic",
            appLabel = "Synthetic capture",
            postedAtMillis = nowMillis,
        ) ?: error("Synthetic capture fixture must parse")
    }

    private fun parse(
        text: String,
        title: String?,
        capturedAtMillis: Long,
        source: String,
        sourceAppPackage: String?,
        sourceAppLabel: String?,
    ): CaptureCandidate? {
        val normalizedText = normalizeText(text)
        if (normalizedText.isBlank() || looksLikeIncome(normalizedText)) {
            return null
        }
        val amount = findAmount(normalizedText) ?: return null
        val merchant = extractMerchant(normalizedText)
            ?: title?.takeUnless { it.equals("payment", ignoreCase = true) }?.trim()?.take(64)
        val occurredAt = Instant.ofEpochMilli(capturedAtMillis).toString()
        val timeBucket = (capturedAtMillis / 60_000L).toString()
        val evidenceInput = listOf(
            source,
            sourceAppPackage.orEmpty(),
            sourceAppLabel.orEmpty(),
            normalizedText,
            amount.amount,
            amount.currency,
            merchant.orEmpty(),
            timeBucket,
        ).joinToString("|")
        val evidenceHash = sha256Hex(evidenceInput)
        val idempotencyKey = listOf(
            "capture-v1",
            source,
            sourceAppPackage.orEmpty().lowercase(Locale.US),
            timeBucket,
            amount.amount,
            amount.currency,
            normalizeKeyPart(merchant),
            evidenceHash.take(16),
        ).joinToString(":")
        val confidence = confidenceFor(normalizedText, merchant)

        return CaptureCandidate(
            amount = amount.amount,
            currency = amount.currency,
            description = merchant ?: "Captured ${source.replaceFirstChar { it.uppercase(Locale.US) }} payment",
            merchantName = merchant,
            capturedAt = occurredAt,
            occurredAt = occurredAt,
            captureSource = source,
            idempotencyKey = idempotencyKey,
            confidence = confidence,
            sourceAppPackage = sourceAppPackage,
            sourceAppLabel = sourceAppLabel,
            evidenceHash = evidenceHash,
        )
    }

    private fun looksLikeIncome(text: String): Boolean {
        val lower = text.lowercase(Locale.getDefault())
        return incomeSignals.any { it in lower }
    }

    private fun confidenceFor(text: String, merchant: String?): Double {
        val lower = text.lowercase(Locale.getDefault())
        var confidence = 0.45
        if (expenseSignals.any { it in lower }) {
            confidence += 0.25
        }
        if (!merchant.isNullOrBlank()) {
            confidence += 0.2
        }
        if (Regex("""(?i)\b(card|visa|mastercard|мир|карта)\b""").containsMatchIn(text)) {
            confidence += 0.05
        }
        return confidence.coerceIn(0.0, 0.95)
    }

    private fun findAmount(text: String): ParsedAmount? {
        amountAfterRegex.find(text)?.let { match ->
            return normalizeAmount(match.groupValues[1], match.groupValues[2])
        }
        amountBeforeRegex.find(text)?.let { match ->
            return normalizeAmount(match.groupValues[2], match.groupValues[1])
        }
        return null
    }

    private fun normalizeAmount(rawAmount: String, rawCurrency: String): ParsedAmount? {
        val decimal = rawAmount
            .replace(" ", "")
            .replace(Regex("""(?<=\d)[,.](?=\d{3}(\D|$))"""), "")
            .replace(',', '.')
        val value = runCatching { BigDecimal(decimal) }.getOrNull()
            ?.takeIf { it > BigDecimal.ZERO }
            ?: return null
        return ParsedAmount(
            amount = value.setScale(2, RoundingMode.HALF_UP).toPlainString(),
            currency = normalizeCurrency(rawCurrency),
        )
    }

    private fun normalizeCurrency(raw: String): String {
        val lower = raw.lowercase(Locale.US)
        return when {
            raw == "$" || lower == "usd" -> "USD"
            raw == "€" || lower == "eur" -> "EUR"
            else -> "RUB"
        }
    }

    private fun extractMerchant(text: String): String? {
        return merchantPatterns.firstNotNullOfOrNull { pattern ->
            pattern.find(text)?.groupValues?.getOrNull(1)?.trimMerchant()
        }
    }

    private fun String.trimMerchant(): String? {
        val cleaned = replace(Regex("""\s+(?:amount|sum|card|остаток|balance)\b.*$""", RegexOption.IGNORE_CASE), "")
            .trim(' ', '.', ',', ';', ':', '-')
            .take(64)
        return cleaned.takeIf { it.length >= 2 }
    }

    private fun normalizeText(value: String): String {
        return value.replace(Regex("""\s+"""), " ").trim()
    }

    private fun normalizeKeyPart(value: String?): String {
        return value.orEmpty()
            .lowercase(Locale.getDefault())
            .replace(Regex("""[^a-zа-я0-9]+"""), "-")
            .trim('-')
            .take(48)
    }

    private fun sha256Hex(value: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }

    private data class ParsedAmount(
        val amount: String,
        val currency: String,
    )
}
