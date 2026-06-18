package com.finance.mvp.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class ApiConfigTest {
    @Test
    fun normalizesTrailingSlash() {
        val config = ApiConfig("http://localhost:8000/")

        assertEquals("http://localhost:8000", config.normalizedBaseUrl)
    }

    @Test
    fun normalizesProdBaseTrailingSlash() {
        val config = ApiConfig("http://45.10.110.42/finance-api/")

        assertEquals("http://45.10.110.42/finance-api", config.normalizedBaseUrl)
    }

    @Test
    fun buildsProdSessionLoginUrlWithFinanceApiBase() {
        val config = ApiConfig("http://45.10.110.42/finance-api/")

        assertEquals(
            "http://45.10.110.42/finance-api/api/v1/sessions",
            "${config.normalizedBaseUrl}/api/v1/sessions",
        )
    }

    @Test
    fun rejectsNonHttpBaseUrl() {
        assertThrows(IllegalArgumentException::class.java) {
            ApiConfig("localhost:8000")
        }
    }
}
