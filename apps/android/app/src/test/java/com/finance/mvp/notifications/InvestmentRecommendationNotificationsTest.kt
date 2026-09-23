package com.finance.mvp.notifications

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class InvestmentRecommendationNotificationsTest {
    @Test fun destinationOpensInvestmentRecommendationsWithoutFirebaseDependency() {
        val intent = investmentRecommendationsIntent(ApplicationProvider.getApplicationContext<Context>())
        assertEquals(INVESTMENT_RECOMMENDATIONS_DEEP_LINK, intent.dataString)
        assertTrue(intent.getBooleanExtra("openInvestmentRecommendations", false))
        assertEquals("investment_recommendations", intent.getStringExtra("openSection"))
    }
}
