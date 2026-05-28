package com.finance.mvp.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CaptureParserTest {
    @Test
    fun bankSmsPurchaseParsesStructuredFields() {
        val candidate = CaptureParser.parseSms(
            body = "Card *1234 purchase 1 234,56 RUB at Perekrestok. Balance hidden",
            sender = "Bank",
            receivedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("1234.56", candidate.amount)
        assertEquals("RUB", candidate.currency)
        assertEquals("Perekrestok", candidate.merchantName)
        assertEquals("sms", candidate.captureSource)
        assertEquals("SMS", candidate.sourceAppLabel)
        assertNull(candidate.sourceAppPackage)
        assertTrue(candidate.confidence >= 0.85)
        assertTrue(candidate.evidenceHash.length == 64)
    }

    @Test
    fun smsSenderIsNotStoredAsMetadata() {
        val candidate = CaptureParser.parseSms(
            body = "Card *1234 purchase 1 234,56 RUB at Perekrestok. Balance hidden",
            sender = "+15551234567",
            receivedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("SMS", candidate.sourceAppLabel)
        assertNull(candidate.sourceAppPackage)
        assertNotEquals("+15551234567", candidate.sourceAppLabel)
    }

    @Test
    fun bankNotificationPurchaseParsesTitleAndText() {
        val candidate = CaptureParser.parseNotification(
            title = "Bank card",
            text = "Payment 45.90 USD at Coffee Place",
            packageName = "com.bank.app",
            appLabel = "Bank",
            postedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("45.90", candidate.amount)
        assertEquals("USD", candidate.currency)
        assertEquals("Coffee Place", candidate.merchantName)
        assertEquals("notification", candidate.captureSource)
        assertEquals("com.bank.app", candidate.sourceAppPackage)
    }

    @Test
    fun paymentAppNotificationParsesCurrencyBeforeAmount() {
        val candidate = CaptureParser.parseNotification(
            title = "Wallet",
            text = "You paid $8.15 at App Store",
            packageName = "com.wallet.pay",
            appLabel = "Wallet",
            postedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("8.15", candidate.amount)
        assertEquals("USD", candidate.currency)
        assertEquals("App Store", candidate.merchantName)
    }

    @Test
    fun refundsAndIncomeAreIgnored() {
        assertNull(
            CaptureParser.parseSms(
                body = "Refund 12.00 USD from Shop",
                sender = "Bank",
                receivedAtMillis = FIXED_TIME,
            ),
        )
        assertNull(
            CaptureParser.parseNotification(
                title = "Bank",
                text = "Salary credited 2500.00 USD",
                packageName = "com.bank.app",
                appLabel = "Bank",
                postedAtMillis = FIXED_TIME,
            ),
        )
    }

    @Test
    fun ambiguousAmountHasLowConfidence() {
        val candidate = CaptureParser.parseSms(
            body = "Card message 19.99 USD",
            sender = "Bank",
            receivedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        assertTrue(candidate!!.confidence < 0.7)
    }

    @Test
    fun screenshotBankPurchaseParsesStructuredFields() {
        val candidate = CaptureParser.parseScreenshotOcr(
            text = """
                Bank card
                Purchase 987.65 RUB at Fresh Market
                Balance 12 000.00 RUB
            """.trimIndent(),
            capturedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("987.65", candidate.amount)
        assertEquals("RUB", candidate.currency)
        assertEquals("Fresh Market", candidate.merchantName)
        assertEquals("screenshot", candidate.captureSource)
        assertNull(candidate.sourceAppPackage)
        assertEquals("Photo Picker", candidate.sourceAppLabel)
        assertTrue(candidate.confidence >= 0.85)
        assertTrue(candidate.evidenceHash.length == 64)
        assertTrue(candidate.idempotencyKey.startsWith("capture-v1:screenshot:"))
    }

    @Test
    fun screenshotBrokerOperationParsesAsDraftCandidate() {
        val candidate = CaptureParser.parseScreenshotOcr(
            text = "Broker order executed. Buy ETF FXUS. Total 120.50 USD. Portfolio updated.",
            capturedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("120.50", candidate.amount)
        assertEquals("USD", candidate.currency)
        assertEquals("Brokerage operation", candidate.merchantName)
        assertEquals("screenshot", candidate.captureSource)
        assertTrue(candidate.confidence >= 0.75)
    }

    @Test
    fun screenshotTransferOrAmbiguousTextIsIgnored() {
        assertNull(
            CaptureParser.parseScreenshotOcr(
                text = "Transfer between accounts 500.00 USD completed",
                capturedAtMillis = FIXED_TIME,
            ),
        )
        assertNull(
            CaptureParser.parseScreenshotOcr(
                text = "Statement screen amount 19.99 USD",
                capturedAtMillis = FIXED_TIME,
            ),
        )
    }

    @Test
    fun screenshotMultipleAmountsPrefersPaymentAmountOverBalance() {
        val candidate = CaptureParser.parseScreenshotOcr(
            text = "Balance 10 000.00 RUB. Payment 345.67 RUB at Pharmacy. Cashback 3.45 RUB.",
            capturedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        assertEquals("345.67", candidate!!.amount)
        assertEquals("Pharmacy", candidate.merchantName)
    }

    @Test
    fun screenshotEmptyOrLowConfidenceTextIsIgnored() {
        assertNull(CaptureParser.parseScreenshotOcr(text = "", capturedAtMillis = FIXED_TIME))
        assertNull(
            CaptureParser.parseScreenshotOcr(
                text = "Receipt-like screen 42.00 USD",
                capturedAtMillis = FIXED_TIME,
            ),
        )
    }

    @Test
    fun screenshotCreateRequestDoesNotCarryRawOcrText() {
        val rawOcr = "Payment 45.90 USD at Coffee Place internal receipt line"
        val candidate = CaptureParser.parseScreenshotOcr(rawOcr, FIXED_TIME)

        assertNotNull(candidate)
        val requestText = candidate!!.toCreateRequest().toString()
        assertEquals("screenshot", candidate.captureSource)
        assertEquals("Coffee Place", candidate.merchantName)
        assertEquals("Coffee Place", candidate.description)
        assertFalse(requestText.contains(rawOcr))
        assertFalse(requestText.contains("internal receipt line", ignoreCase = true))
        assertFalse(requestText.contains("rawOcr", ignoreCase = true))
        assertFalse(requestText.contains("image", ignoreCase = true))
    }

    @Test
    fun screenshotSuspiciousMerchantHintFallsBackToGenericDescription() {
        val candidate = CaptureParser.parseScreenshotOcr(
            text = "Payment 45.90 USD at internal receipt line",
            capturedAtMillis = FIXED_TIME,
        )

        assertNotNull(candidate)
        candidate!!
        assertEquals("45.90", candidate.amount)
        assertEquals("USD", candidate.currency)
        assertEquals("screenshot", candidate.captureSource)
        assertNull(candidate.merchantName)
        assertEquals("Screenshot capture", candidate.description)
        assertTrue(candidate.confidence >= 0.55)
    }

    @Test
    fun screenshotSensitiveMerchantHintsFallBackToGenericDescription() {
        val sensitiveHints = listOf(
            "4111111111111111",
            "account 123456789",
            "555 123 4567",
            "customer@example.com",
            "+1 (555) 123-4567",
        )

        sensitiveHints.forEach { hint ->
            val candidate = CaptureParser.parseScreenshotOcr(
                text = "Payment 45.90 USD at $hint",
                capturedAtMillis = FIXED_TIME,
            )

            assertNotNull("Expected screenshot candidate for $hint", candidate)
            candidate!!
            assertEquals("45.90", candidate.amount)
            assertEquals("USD", candidate.currency)
            assertEquals("screenshot", candidate.captureSource)
            assertNull("Sensitive hint must not become merchantName: $hint", candidate.merchantName)
            assertEquals("Screenshot capture", candidate.description)
            assertFalse(candidate.description.orEmpty().contains(hint, ignoreCase = true))
            assertTrue(candidate.confidence >= 0.55)
        }
    }

    @Test
    fun idempotencyIsStableForSameMinuteAndChangesForDifferentEvidence() {
        val first = CaptureParser.parseNotification(
            title = "Bank",
            text = "Payment 9.99 USD at Market",
            packageName = "com.bank.app",
            appLabel = "Bank",
            postedAtMillis = FIXED_TIME,
        )
        val duplicate = CaptureParser.parseNotification(
            title = "Bank",
            text = "Payment   9.99 USD at Market",
            packageName = "com.bank.app",
            appLabel = "Bank",
            postedAtMillis = FIXED_TIME + 1_000,
        )
        val different = CaptureParser.parseNotification(
            title = "Bank",
            text = "Payment 10.99 USD at Market",
            packageName = "com.bank.app",
            appLabel = "Bank",
            postedAtMillis = FIXED_TIME,
        )

        assertEquals(first!!.idempotencyKey, duplicate!!.idempotencyKey)
        assertEquals(first.evidenceHash, duplicate.evidenceHash)
        assertNotEquals(first.idempotencyKey, different!!.idempotencyKey)
    }

    private companion object {
        const val FIXED_TIME: Long = 1_779_558_000_000L
    }
}
