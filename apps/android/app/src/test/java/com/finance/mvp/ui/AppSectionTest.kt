package com.finance.mvp.ui

import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AppSectionTest {
    @Test
    fun exposesManualFirstMvpSections() {
        val titles = mvpSections().map { it.title }

        assertEquals(
            listOf("Обзор", "Счета", "Категории", "Операции", "Переводы", "Отчеты"),
            titles,
        )
    }

    @Test
    fun excludesNonMvpBankingSurfaces() {
        val allText = mvpSections().joinToString(" ") { "${it.title} ${it.subtitle}" }

        assertTrue(!allText.contains("SMS", ignoreCase = true))
        assertTrue(!allText.contains("push", ignoreCase = true))
        assertTrue(!allText.contains("broker", ignoreCase = true))
        assertTrue(!allText.contains("импорт", ignoreCase = true))
        assertTrue(!allText.contains("банк", ignoreCase = true))
    }

    @Test
    fun exposesTransferProofInOverviewOperationsAndReports() {
        val dashboard = FinanceDashboard(
            session = SessionStatus(true, "Пользователь demo", "household"),
            accounts = listOf(AccountSummary("Наличные", "cash", "personal", "USD", "925.50")),
            categories = listOf(CategorySummary("Продукты", "expense", "personal")),
            transactions = listOf(
                TransactionSummary(
                    type = "transfer",
                    amount = "25.00",
                    currency = "USD",
                    occurredAt = "2026-05-18T08:30:00Z",
                    description = "Dev same-household transfer",
                    transferScope = "household_same_household",
                    transferStatus = "posted",
                ),
            ),
            totals = listOf(MoneyTotal("USD", "250.00", "69.75", "180.25")),
            reportTransferCount = 1,
        )

        val overviewText = sectionCards(AppSection.Overview, dashboard).joinToString(" ") { it.body }
        val operationText = sectionCards(AppSection.Operations, dashboard).joinToString(" ") { "${it.title} ${it.body}" }
        val transferText = sectionCards(AppSection.Transfers, dashboard).joinToString(" ") { "${it.title} ${it.body} ${it.status}" }
        val reportText = sectionCards(AppSection.Reports, dashboard).joinToString(" ") { "${it.title} ${it.body}" }

        assertTrue(overviewText.contains("переводов: 1"))
        assertTrue(operationText.contains("Перевод"))
        assertTrue(operationText.contains("household_same_household"))
        assertTrue(operationText.contains("posted"))
        assertTrue(transferText.contains("Перевод"))
        assertTrue(transferText.contains("transfer row"))
        assertTrue(reportText.contains("Report transactions transfer count: 1"))
    }
}
