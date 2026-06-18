package com.finance.mvp.api

import com.finance.mvp.BuildConfig
import org.junit.Assert.assertFalse
import org.junit.Test

class BuildConfigApiBaseUrlTest {
    @Test
    fun debugBuildConfigDoesNotTargetProductionApi() {
        val baseUrl = BuildConfig.FINANCE_API_BASE_URL.trim().trimEnd('/')

        assertFalse(
            "Debug FINANCE_API_BASE_URL must not target the public production host.",
            baseUrl.contains("45.10.110.42"),
        )
        assertFalse(
            "Debug FINANCE_API_BASE_URL must not target the production /finance-api path.",
            baseUrl.endsWith("/finance-api"),
        )
    }
}
