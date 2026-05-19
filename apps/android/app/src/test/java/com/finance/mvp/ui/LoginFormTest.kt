package com.finance.mvp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LoginFormTest {
    @Test
    fun loginCredentialsUseUserEnteredEmailAndPassword() {
        val credentials = loginCredentialsOrNull("  finance.qa@local.test  ", "typed-password")

        assertEquals("finance.qa@local.test", credentials?.email)
        assertEquals("typed-password".length, credentials?.password?.length)
    }

    @Test
    fun loginCredentialsRejectBlankEmailOrPassword() {
        assertNull(loginCredentialsOrNull("", "typed-password"))
        assertNull(loginCredentialsOrNull("finance.qa@local.test", ""))
        assertNull(loginCredentialsOrNull("   ", "typed-password"))
    }
}
