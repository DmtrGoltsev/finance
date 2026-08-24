package com.finance.mvp.ui

import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.finance.mvp.ui.theme.FinanceTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class ReportMonthSwitcherInstrumentedTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun monthSwitcherUsesOneLineLabelAndAccessibleIconActions() {
        var selectedMonth = "2026-08"

        composeRule.setContent {
            FinanceTheme {
                ReportMonthSwitcher(
                    selectedMonth = "2026-08",
                    onSelected = { selectedMonth = it },
                )
            }
        }

        composeRule.onNodeWithTag("report-month-label")
            .assertTextEquals("Август 2026")

        composeRule.onNodeWithContentDescription("Предыдущий месяц").performClick()
        assertEquals("2026-07", selectedMonth)
        composeRule.onNodeWithContentDescription("Текущий месяц").performClick()
        assertEquals(currentReportMonth(), selectedMonth)
        composeRule.onNodeWithContentDescription("Следующий месяц").performClick()
        assertEquals("2026-09", selectedMonth)
    }
}
