package com.finance.mvp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlanningUiStatusTest {
    @Test
    fun investmentAttentionUsesIconAndHidesRawReason() {
        assertTrue(
            shouldShowInvestmentAttentionIcon(
                targetType = "investment_asset_category",
                requiresAttention = true,
            ),
        )
        assertNull(
            planningAllocationAttentionText(
                targetType = "investment_asset_category",
                requiresAttention = true,
                attentionReason = "INVESTMENT_UNDER_PLAN",
            ),
        )
        assertEquals(
            "Инвестиции ниже плана",
            planningAllocationStatusLabel(
                targetType = "investment_asset_category",
                progressStatus = "INVESTMENT_UNDER_PLAN",
                status = null,
                requiresAttention = true,
            ),
        )
    }

    @Test
    fun expenseAttentionSanitizesRawReason() {
        assertFalse(
            shouldShowInvestmentAttentionIcon(
                targetType = "expense_category",
                requiresAttention = true,
            ),
        )
        assertEquals(
            "Эта цель требует внимания",
            planningAllocationAttentionText(
                targetType = "expense_category",
                requiresAttention = true,
                attentionReason = "UNDER_PLAN",
            ),
        )
    }

    @Test
    fun noActualsStatusUsesShortFactLabel() {
        assertEquals("Факт", "no_actuals".localizedPlanningStatus())
    }
}
