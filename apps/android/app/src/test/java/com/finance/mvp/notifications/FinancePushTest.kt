package com.finance.mvp.notifications

import org.junit.Assert.*
import org.junit.Test
import java.util.UUID

class FinancePushTest {
    private val session = UUID.randomUUID().toString()
    private fun data() = mapOf("type" to "investment_recommendation", "sessionId" to session,
        "eventId" to UUID.randomUUID().toString(), "jobId" to UUID.randomUUID().toString())

    @Test fun neutralMessageCarriesValidatedIdentifiers() {
        val data = data()
        val push = parseReadyPush(data, session)!!
        assertEquals(data["jobId"], push.jobId)
        assertEquals(data["eventId"], push.eventId)
    }

    @Test fun logoutAndAccountSwitchSuppressOldMessages() {
        assertNull(parseReadyPush(data(), null))
        assertNull(parseReadyPush(data(), UUID.randomUUID().toString()))
    }

    @Test fun malformedOrUnrelatedMessageIsIgnored() {
        assertNull(parseReadyPush(data() + ("jobId" to "arbitrary-url"), session))
        assertNull(parseReadyPush(data() + ("type" to "other"), session))
    }
}
