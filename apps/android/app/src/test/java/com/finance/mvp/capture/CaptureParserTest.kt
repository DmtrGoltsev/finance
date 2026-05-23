package com.finance.mvp.capture

import org.junit.Assert.assertEquals
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
