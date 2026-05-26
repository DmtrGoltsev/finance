package com.finance.mvp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
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

    @Test
    fun registrationCredentialsNormalizeOptionalDisplayName() {
        val result = registrationCredentialsOrError(
            email = "  finance.qa@local.test  ",
            password = "typed-password",
            confirmPassword = "typed-password",
            displayName = "  Finance QA  ",
        )

        assertTrue(result is RegistrationValidationResult.Valid)
        val credentials = (result as RegistrationValidationResult.Valid).credentials
        assertEquals("finance.qa@local.test", credentials.email)
        assertEquals("typed-password".length, credentials.password.length)
        assertEquals("Finance QA", credentials.displayName)
    }

    @Test
    fun registrationCredentialsRejectBlankAndMismatchedFields() {
        assertRegistrationError("Введите email", registrationCredentialsOrError("", "password", "password", ""))
        assertRegistrationError("Введите пароль", registrationCredentialsOrError("finance.qa@local.test", "", "", ""))
        assertRegistrationError("Повторите пароль", registrationCredentialsOrError("finance.qa@local.test", "password", "", ""))
        assertRegistrationError("Пароль должен быть не короче 12 символов", registrationCredentialsOrError("finance.qa@local.test", "short-pass", "short-pass", ""))
        assertRegistrationError("Пароли не совпадают", registrationCredentialsOrError("finance.qa@local.test", "valid-password", "different-password", ""))
    }

    @Test
    fun acceptedRegistrationSwitchesToLoginWithoutAuthenticatedState() {
        val update = registrationAcceptedUiUpdate()

        assertEquals(AuthMode.Login, update.mode)
        assertEquals(REGISTRATION_ACCEPTED_MESSAGE, update.state.message)
        assertNull(update.state.session)
        assertNull(update.state.dashboard)
    }

    private fun assertRegistrationError(expected: String, result: RegistrationValidationResult) {
        assertTrue(result is RegistrationValidationResult.Invalid)
        assertEquals(expected, (result as RegistrationValidationResult.Invalid).message)
    }
}
