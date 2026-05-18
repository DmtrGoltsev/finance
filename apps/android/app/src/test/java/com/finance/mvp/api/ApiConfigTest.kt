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
    fun keepsEmulatorDefaultShape() {
        val config = ApiConfig("http://10.0.2.2:8000")

        assertEquals("http://10.0.2.2:8000", config.normalizedBaseUrl)
    }

    @Test
    fun rejectsNonHttpBaseUrl() {
        assertThrows(IllegalArgumentException::class.java) {
            ApiConfig("localhost:8000")
        }
    }
}
