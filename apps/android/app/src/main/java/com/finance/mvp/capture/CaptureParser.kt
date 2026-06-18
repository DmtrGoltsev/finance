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
        "buy",
        "bought",
        "order executed",
        "trade",
        "brokerage",
        "spisanie",
        "oplata",
        "pokupka",
    )
    private val incomeSignals = listOf(
        "refund",
        "reversal",
        "cashback credited",
        "deposit",
        "credited",
        "income",
        "salary",
        "vozvrat",
        "zachislen",
        "popolnen",
    )
    private val brokerSignals = listOf(
        "broker",
        "brokerage",
        "investment",
        "portfolio",
        "stock",
        "etf",
        "asset",
        "order executed",
    )
    private val transferSignals = listOf(
        "transfer",
        "sent to",
        "between accounts",
        "p2p",
        "card to card",
    )
    private val primaryAmountSignals = listOf(
        "purchase",
        "payment",
        "paid",
        "spent",
        "debit",
        "buy",
        "bought",
        "order",
        "total",
        "amount",
        "sum",
        "broker",
        "trade",
    )
    private val balanceSignals = listOf(
        "balance",
        "available",
        "cashback",
    )
    private val amountAfterRegex = Regex(
        "(?i)(\\d[\\d\\s.,]*\\d|\\d)(?:\\s*)(\\u20BD|rub|rur|usd|\\$|eur|\\u20AC)(?=$|[^\\p{L}\\p{Nd}_])",
    )
    private val amountBeforeRegex = Regex(
        "(?i)(\\u20BD|rub|rur|usd|\\$|eur|\\u20AC)(?:\\s*)(\\d[\\d\\s.,]*\\d|\\d)\\b",
    )
    private val aggregateOperationCountRegex = Regex(
        """(?i)(\d{1,4})\s+(?:операци[ияй]|operations?)""",
    )
    private val aggregateSummaryRegex = Regex(
        """(?i)^\s*(?:ещ[её]|more)\s+\d{1,4}\s+(?:категори[ияй]|categories)\s+""",
    )
    private val aggregateHeaderLines = setOf(
        "анализ финансов",
        "расходы",
        "доходы",
        "категории",
        "операции",
        "за месяц",
        "за период",
        "finance analysis",
        "expenses",
        "income",
        "categories",
    )
    private val screenshotMerchantPatterns = listOf(
        Regex("""(?i)\b(?:at|in)\s+([A-Za-z0-9@+][A-Za-z0-9@+ ._&'()/-]{1,79})"""),
        Regex("""(?i)\bmerchant[:\s]+([A-Za-z0-9@+][A-Za-z0-9@+ ._&'()/-]{1,79})"""),
        Regex("""(?i)\bbroker:\s+([A-Za-z0-9@+][A-Za-z0-9@+ ._&'()/-]{1,79})"""),
    )
    private val screenshotMerchantStopWords = setOf(
        "account",
        "acct",
        "amount",
        "auth",
        "available",
        "balance",
        "card",
        "cashback",
        "date",
        "internal",
        "line",
        "paid",
        "payment",
        "purchase",
        "receipt",
        "reference",
        "routing",
        "sum",
        "terminal",
        "time",
        "total",
    )

    fun parseScreenshotOcr(
        text: String,
        capturedAtMillis: Long,
    ): CaptureCandidate? {
        val normalizedText = normalizeText(text)
        if (normalizedText.isBlank() || looksLikeTransfer(normalizedText)) {
            return null
        }
        return parse(
            text = text,
            capturedAtMillis = capturedAtMillis,
            source = "screenshot",
            sourceAppPackage = null,
            sourceAppLabel = "Photo Picker",
            minimumConfidence = 0.55,
            preferContextualAmount = true,
        )
    }

    fun parseScreenshotOcrResult(
        text: String,
        capturedAtMillis: Long,
    ): ScreenshotOcrParseResult {
        val aggregateCandidates = parseCategoryAggregateScreenshotOcr(text, capturedAtMillis)
        return ScreenshotOcrParseResult(
            aggregateCandidates = aggregateCandidates,
            singleCandidate = if (aggregateCandidates.isEmpty()) {
                parseScreenshotOcr(text, capturedAtMillis)
            } else {
                null
            },
        )
    }

    fun parseCategoryAggregateScreenshotOcr(
        text: String,
        capturedAtMillis: Long,
    ): List<CategoryAggregateCandidate> {
        val lines = text.lineSequence()
            .map { it.replace(Regex("""\s+"""), " ").trim() }
            .filter { it.isNotBlank() }
            .toList()
        if (lines.isEmpty()) {
            return emptyList()
        }

        val capturedAt = Instant.ofEpochMilli(capturedAtMillis).toString()
        val timeBucket = (capturedAtMillis / 60_000L).toString()
        val candidates = mutableListOf<CategoryAggregateCandidate>()
        val labelBuffer = mutableListOf<String>()
        var skipLineIndex: Int? = null

        lines.forEachIndexed { index, line ->
            if (skipLineIndex == index) {
                skipLineIndex = null
                return@forEachIndexed
            }
            if (line.isAggregateSummaryLine()) {
                labelBuffer.clear()
                return@forEachIndexed
            }

            val amountMatch = amountMatchIn(line)
            if (amountMatch == null) {
                if (line.isAggregateLabelLine()) {
                    labelBuffer += line
                }
                return@forEachIndexed
            }

            val trailingText = line.substring(amountMatch.end).trim()
            val operationCountInSameLine = aggregateOperationCountRegex.find(trailingText)
                ?.groupValues
                ?.getOrNull(1)
                ?.toIntOrNull()
            val operationCountInNextLine = operationCountInSameLine ?: lines
                .getOrNull(index + 1)
                ?.let { nextLine ->
                    aggregateOperationCountRegex.find(nextLine)
                        ?.takeIf { match -> match.range.first <= 2 }
                        ?.groupValues
                        ?.getOrNull(1)
                        ?.toIntOrNull()
                }
            if (operationCountInSameLine == null && operationCountInNextLine != null) {
                skipLineIndex = index + 1
            }

            val labelBeforeAmount = line.substring(0, amountMatch.start).trim()
            val label = (labelBuffer + labelBeforeAmount)
                .filter { it.isAggregateLabelLine() }
                .takeLast(2)
                .joinToString(" ")
                .cleanAggregateLabel()
            labelBuffer.clear()

            val operationCount = operationCountInNextLine
            if (label.isBlank() || operationCount == null) {
                return@forEachIndexed
            }

            val amount = amountMatch.amount
            val evidenceInput = listOf(
                "screenshot",
                "category-aggregate-v1",
                normalizeAggregateLabel(label),
                amount.amount,
                amount.currency,
                operationCount.toString(),
                timeBucket,
            ).joinToString("|")
            val evidenceHash = sha256Hex(evidenceInput)
            val labelKey = sha256Hex(normalizeAggregateLabel(label)).take(16)
            val idempotencyKey = listOf(
                "capture-v1",
                "screenshot",
                "category-aggregate",
                timeBucket,
                amount.amount,
                amount.currency,
                labelKey,
                evidenceHash.take(16),
            ).joinToString(":")

            candidates += CategoryAggregateCandidate(
                externalLabel = label,
                amount = amount.amount,
                currency = amount.currency,
                operationCount = operationCount,
                capturedAt = capturedAt,
                occurredAt = capturedAt,
                idempotencyKey = idempotencyKey,
                confidence = 0.82,
                evidenceHash = evidenceHash,
            )
        }

        return candidates.distinctBy { candidate ->
            "${normalizeAggregateLabel(candidate.externalLabel)}|${candidate.amount}|${candidate.operationCount}"
        }
    }

    private fun parse(
        text: String,
        capturedAtMillis: Long,
        source: String,
        sourceAppPackage: String?,
        sourceAppLabel: String?,
        minimumConfidence: Double = 0.0,
        preferContextualAmount: Boolean = false,
    ): CaptureCandidate? {
        val normalizedText = normalizeText(text)
        if (normalizedText.isBlank() || looksLikeIncome(normalizedText)) {
            return null
        }
        val amount = findAmount(normalizedText, preferContextualAmount) ?: return null
        val merchant = extractMerchant(normalizedText)
            ?: brokerDescription(normalizedText)
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
        if (confidence < minimumConfidence) {
            return null
        }

        return CaptureCandidate(
            amount = amount.amount,
            currency = amount.currency,
            description = merchant ?: genericDescription(),
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

    private fun looksLikeTransfer(text: String): Boolean {
        val lower = text.lowercase(Locale.getDefault())
        return transferSignals.any { it in lower }
    }

    private fun confidenceFor(text: String, merchant: String?): Double {
        val lower = text.lowercase(Locale.getDefault())
        var confidence = 0.45
        if (expenseSignals.any { it in lower }) {
            confidence += 0.25
        }
        if (brokerSignals.any { it in lower }) {
            confidence += 0.15
        }
        if (!merchant.isNullOrBlank()) {
            confidence += 0.2
        }
        if (Regex("""(?i)\b(card|visa|mastercard)\b""").containsMatchIn(text)) {
            confidence += 0.05
        }
        return confidence.coerceIn(0.0, 0.95)
    }

    private fun findAmount(text: String, preferContextualAmount: Boolean = false): ParsedAmount? {
        val matches = amountMatches(text)
        if (matches.isEmpty()) {
            return null
        }
        if (!preferContextualAmount) {
            return matches.first().amount
        }
        val lower = text.lowercase(Locale.getDefault())
        return matches.firstOrNull { match ->
            val before = lower.substring((match.start - 28).coerceAtLeast(0), match.start)
            val window = lower.substring((match.start - 56).coerceAtLeast(0), (match.end + 56).coerceAtMost(text.length))
            balanceSignals.none { it in before } && primaryAmountSignals.any { it in window }
        }?.amount ?: matches.firstOrNull { match ->
            val before = lower.substring((match.start - 28).coerceAtLeast(0), match.start)
            balanceSignals.none { it in before }
        }?.amount ?: matches.first().amount
    }

    private fun amountMatches(text: String): List<ParsedAmountMatch> {
        val afterMatches = amountAfterRegex.findAll(text).mapNotNull { match ->
            normalizeAmount(match.groupValues[1], match.groupValues[2])?.let {
                ParsedAmountMatch(it, match.range.first, match.range.last + 1)
            }
        }.toList()
        val beforeMatches = amountBeforeRegex.findAll(text).mapNotNull { match ->
            normalizeAmount(match.groupValues[2], match.groupValues[1])?.let {
                ParsedAmountMatch(it, match.range.first, match.range.last + 1)
            }
        }.toList()
        return (afterMatches + beforeMatches).sortedBy { it.start }
    }

    private fun amountMatchIn(text: String): ParsedAmountMatch? {
        val afterMatch = amountAfterRegex.find(text)?.let { match ->
            normalizeAmount(match.groupValues[1], match.groupValues[2])?.let {
                ParsedAmountMatch(it, match.range.first, match.range.last + 1)
            }
        }
        val beforeMatch = amountBeforeRegex.find(text)?.let { match ->
            normalizeAmount(match.groupValues[2], match.groupValues[1])?.let {
                ParsedAmountMatch(it, match.range.first, match.range.last + 1)
            }
        }
        return listOfNotNull(afterMatch, beforeMatch).minByOrNull { it.start }
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
            raw == "\u20AC" || lower == "eur" -> "EUR"
            else -> "RUB"
        }
    }

    private fun extractMerchant(text: String): String? {
        return screenshotMerchantPatterns.firstNotNullOfOrNull { pattern ->
            pattern.find(text)?.groupValues?.getOrNull(1)?.let { raw ->
                raw.trimScreenshotMerchant()
            }
        }
    }

    private fun genericDescription(): String {
        return "Screenshot capture"
    }

    private fun brokerDescription(text: String): String? {
        val lower = text.lowercase(Locale.getDefault())
        return if (brokerSignals.any { it in lower }) "Brokerage operation" else null
    }

    private fun String.trimScreenshotMerchant(): String? {
        if (contains('@')) {
            return null
        }
        val tokens = replace(Regex("""[.,;:|/\\].*$"""), "")
            .trim(' ', '.', ',', ';', ':', '-')
            .split(Regex("""\s+"""))
            .filter { token ->
                token.isNotBlank() && token.any(Char::isLetterOrDigit)
            }
        val safeTokens = tokens.takeWhile { token ->
            token.lowercase(Locale.US).trim(' ', '.', ',', ';', ':', '-') !in screenshotMerchantStopWords
        }.take(3)
        if (safeTokens.isEmpty() || tokens.size > safeTokens.size + 4) {
            return null
        }
        val cleaned = safeTokens.joinToString(" ")
            .replace(Regex("""[^A-Za-z0-9 ._&'-]"""), "")
            .trim(' ', '.', ',', ';', ':', '-')
            .take(40)
        return cleaned.takeIf { value ->
            value.length in 2..40 &&
                value.count { it.isWhitespace() } <= 2 &&
                !value.looksLikeSensitiveScreenshotMerchant()
        }
    }

    private fun String.looksLikeSensitiveScreenshotMerchant(): Boolean {
        val digitCount = count(Char::isDigit)
        val letterCount = count(Char::isLetter)
        if (digitCount >= 6) {
            return true
        }
        if (digitCount >= 4 && letterCount == 0) {
            return true
        }
        return Regex("""(?i)(?:\+?\d[\d\s().-]{7,}\d)""").containsMatchIn(this)
    }

    private fun normalizeText(value: String): String {
        return value.replace(Regex("""\s+"""), " ").trim()
    }

    private fun normalizeKeyPart(value: String?): String {
        return value.orEmpty()
            .lowercase(Locale.getDefault())
            .replace(Regex("""[^a-z0-9]+"""), "-")
            .trim('-')
            .take(48)
    }

    internal fun normalizeAggregateLabel(value: String): String {
        return value
            .lowercase(Locale("ru", "RU"))
            .replace('ё', 'е')
            .replace(Regex("""[^\p{L}\p{Nd}]+"""), " ")
            .replace(Regex("""\s+"""), " ")
            .trim()
            .take(120)
    }

    private fun String.isAggregateSummaryLine(): Boolean {
        return aggregateSummaryRegex.containsMatchIn(normalizeAggregateLabel(this))
    }

    private fun String.isAggregateLabelLine(): Boolean {
        val normalized = normalizeAggregateLabel(this)
        if (normalized.isBlank() || normalized in aggregateHeaderLines) {
            return false
        }
        if (amountAfterRegex.containsMatchIn(this) || amountBeforeRegex.containsMatchIn(this)) {
            return false
        }
        if (aggregateOperationCountRegex.containsMatchIn(this)) {
            return false
        }
        if (isAggregateSummaryLine()) {
            return false
        }
        return any(Char::isLetter)
    }

    private fun String.cleanAggregateLabel(): String {
        return trim(' ', '.', ',', ';', ':', '-')
            .replace(Regex("""\s+"""), " ")
            .take(80)
    }

    private fun sha256Hex(value: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }

    private data class ParsedAmount(
        val amount: String,
        val currency: String,
    )

    private data class ParsedAmountMatch(
        val amount: ParsedAmount,
        val start: Int,
        val end: Int,
    )
}
