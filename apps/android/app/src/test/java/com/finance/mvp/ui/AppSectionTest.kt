package com.finance.mvp.ui

import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppSectionTest {
    @Test
    fun exposesMobileFinanceSectionsWithCategoryManagement() {
        val titles = financeSections().map { it.title }

        assertEquals(listOf("Главная", "Операции", "Активы", "Категории", "Аналитика"), titles)
    }

    @Test
    fun sectionTextDoesNotExposeDebugLanguage() {
        val allText = financeSections().joinToString(" ") { "${it.title} ${it.subtitle}" }

        listOf("MVP", "CRUD", "PATCH", "Live API", "session id", "E2E").forEach { forbidden ->
            assertFalse(allText.contains(forbidden, ignoreCase = true))
        }
    }

    @Test
    fun transfersAreSeparateFromMonthlyExpenses() {
        val dashboard = dashboardFixture()

        val view = dashboard.viewFor(FinanceMode.Overview)

        assertEquals(BigDecimal("69.75"), view.monthExpenses)
        assertEquals(BigDecimal("25.00"), view.transferTotal)
        assertTrue(sectionCards(AppSection.Home, dashboard).joinToString(" ") { it.status }.contains("переводы отдельно"))
    }

    @Test
    fun capitalIncludesDepositsBrokerageAndMetalAssets() {
        val dashboard = dashboardFixture()

        val view = dashboard.viewFor(FinanceMode.Overview)

        assertEquals(BigDecimal("3525.50"), view.capital)
        assertTrue(view.assetSummaries.any { it.kind == AssetKind.Card && it.balance == BigDecimal("925.50") })
        assertTrue(view.assetSummaries.any { it.kind == AssetKind.Deposit && it.balance == BigDecimal("100.00") })
        assertTrue(view.assetSummaries.any { it.kind == AssetKind.Brokerage && it.balance == BigDecimal("2200.00") })
        assertTrue(view.assetSummaries.any { it.kind == AssetKind.Metal && it.balance == BigDecimal("300.00") })
    }

    @Test
    fun homeViewExcludesArchivedAccountsFromCapitalAssetsAndTransactions() {
        val dashboard = dashboardFixture().copy(
            accounts = dashboardFixture().accounts + AccountSummary(
                "Архивный брокер",
                "brokerage",
                "personal",
                "USD",
                "9999.00",
                id = "acc-archived",
                status = "archived",
            ),
            transactions = dashboardFixture().transactions + TransactionSummary(
                type = "expense",
                amount = "999.00",
                currency = "USD",
                occurredAt = "2026-05-18T10:00:00Z",
                description = "Архивная операция",
                transferScope = null,
                transferStatus = null,
                id = "txn-archived",
                accountId = "acc-archived",
                categoryId = "cat-food",
            ),
        )

        val view = dashboard.viewFor(FinanceMode.Overview)

        assertEquals(BigDecimal("3525.50"), view.capital)
        assertEquals(BigDecimal("69.75"), view.monthExpenses)
        assertEquals(2, view.operationCount)
        assertTrue(view.assetSummaries.any { it.kind == AssetKind.Brokerage && it.balance == BigDecimal("2200.00") })
    }

    @Test
    fun personalSharedAndOverviewModesFilterAccountsAndTransactions() {
        val dashboard = dashboardFixture().copy(
            accounts = dashboardFixture().accounts + AccountSummary(
                "Семейный счет",
                "bank",
                "shared",
                "USD",
                "400.00",
                id = "acc-shared",
                householdId = "household",
            ),
            transactions = dashboardFixture().transactions + TransactionSummary(
                type = "expense",
                amount = "30.00",
                currency = "USD",
                occurredAt = "2026-05-18T10:00:00Z",
                description = "Дом",
                transferScope = null,
                transferStatus = null,
                id = "txn-shared",
                accountId = "acc-shared",
                categoryId = "cat-food",
            ),
        )

        val personal = dashboard.viewFor(FinanceMode.Personal)
        val shared = dashboard.viewFor(FinanceMode.Shared)
        val overview = dashboard.viewFor(FinanceMode.Overview)

        assertEquals(BigDecimal("3525.50"), personal.capital)
        assertEquals(2, personal.operationCount)
        assertEquals(BigDecimal("400.00"), shared.capital)
        assertEquals(1, shared.operationCount)
        assertEquals(BigDecimal("3925.50"), overview.capital)
        assertEquals(3, overview.operationCount)
    }

    @Test
    fun overviewHidesOneSidedTransfersButKeepsBothSidedTransfers() {
        val dashboard = dashboardFixture().copy(
            transactions = dashboardFixture().transactions + TransactionSummary(
                type = "transfer",
                amount = "40.00",
                currency = "USD",
                occurredAt = "2026-05-18T10:00:00Z",
                description = "External transfer",
                transferScope = "personal_same_owner",
                transferStatus = "posted",
                id = "txn-one-sided-transfer",
                accountId = "acc-card",
                counterpartyAccountId = "acc-hidden",
            ),
        )

        val overview = dashboard.viewFor(FinanceMode.Overview)
        val overviewTransactionIds = overview.recentTransactions.map { it.id }

        assertEquals(BigDecimal("25.00"), overview.transferTotal)
        assertEquals(2, overview.operationCount)
        assertTrue(overviewTransactionIds.contains("txn-transfer"))
        assertFalse(overviewTransactionIds.contains("txn-one-sided-transfer"))
    }

    @Test
    fun reportModeAggregationDoesNotFallbackAcrossPersonalAndSharedScopes() {
        val dashboard = dashboardFixture().copy(
            accounts = listOf(
                AccountSummary("Личная карта", "card", "personal", "USD", "100.00", id = "acc-personal"),
                AccountSummary(
                    "Семейный счет",
                    "bank",
                    "shared",
                    "USD",
                    "200.00",
                    id = "acc-shared",
                    householdId = "household",
                ),
            ),
            transactions = listOf(
                TransactionSummary(
                    type = "income",
                    amount = "250.00",
                    currency = "USD",
                    occurredAt = "2026-05-18T08:00:00Z",
                    description = "Зарплата",
                    transferScope = null,
                    transferStatus = null,
                    id = "txn-personal-income",
                    accountId = "acc-personal",
                    categoryId = "cat-food",
                ),
                TransactionSummary(
                    type = "expense",
                    amount = "30.00",
                    currency = "USD",
                    occurredAt = "2026-05-18T10:00:00Z",
                    description = "Дом",
                    transferScope = null,
                    transferStatus = null,
                    id = "txn-shared-expense",
                    accountId = "acc-shared",
                    categoryId = "cat-food",
                ),
            ),
            totals = listOf(MoneyTotal("USD", "250.00", "30.00", "220.00")),
        )

        val personal = dashboard.viewFor(FinanceMode.Personal)
        val shared = dashboard.viewFor(FinanceMode.Shared)

        assertEquals(BigDecimal("250.00"), personal.monthIncome)
        assertEquals(BigDecimal.ZERO, personal.monthExpenses)
        assertEquals(BigDecimal.ZERO, shared.monthIncome)
        assertEquals(BigDecimal("30.00"), shared.monthExpenses)
    }

    @Test
    fun invalidTransferPairsReturnActionableMessages() {
        val personal = AccountSummary("Личная карта", "card", "personal", "USD", "10.00", id = "personal")
        val shared = AccountSummary(
            "Семейный счет",
            "bank",
            "shared",
            "USD",
            "10.00",
            id = "shared",
            householdId = "household",
        )
        val eur = personal.copy(id = "eur", currency = "EUR")

        assertEquals("Для перевода нужны два совместимых счета в одном scope и одной валюте.", transferPairValidationMessage(personal, null))
        assertEquals("Выберите два разных счета", transferPairValidationMessage(personal, personal))
        assertEquals("Перед отправкой выберите счета одного scope: Личное с Личным или Общее с Общим.", transferPairValidationMessage(personal, shared))
        assertEquals("Перед отправкой выберите счета в одной валюте: конвертация в переводе недоступна.", transferPairValidationMessage(personal, eur))
        assertEquals(null, transferPairValidationMessage(personal, personal.copy(id = "personal-2")))
    }

    @Test
    fun writableModesExcludeOverviewForWriteFlows() {
        assertEquals(listOf(FinanceMode.Personal), writableFinanceModes(hasHousehold = false))
        assertEquals(listOf(FinanceMode.Personal, FinanceMode.Shared), writableFinanceModes(hasHousehold = true))
        assertFalse(writableFinanceModes(hasHousehold = true).contains(FinanceMode.Overview))
    }

    @Test
    fun quickAddRequiresExplicitWritableScope() {
        val account = AccountSummary("Личная карта", "card", "personal", "USD", "10.00", id = "personal")
        val category = CategorySummary("Продукты", "expense", "personal", id = "cat-food")

        val overviewReason = quickAddDisabledReason(
            type = QuickEntryType.Expense,
            amount = "10",
            visibility = FinanceMode.Overview,
            accounts = listOf(account),
            categories = listOf(category),
            transferValidation = null,
        )
        val missingCategoryReason = quickAddDisabledReason(
            type = QuickEntryType.Expense,
            amount = "10",
            visibility = FinanceMode.Personal,
            accounts = listOf(account),
            categories = emptyList(),
            transferValidation = null,
        )

        assertTrue(overviewReason.orEmpty().contains("Мой обзор read-only"))
        assertTrue(missingCategoryReason.orEmpty().contains("нет категории"))
        assertFalse(quickAddEntryTypes().contains(QuickEntryType.Asset))
    }

    @Test
    fun analyticsCardsExposeMonthPlanEntry() {
        val cards = sectionCards(AppSection.Analytics, dashboardFixture())

        assertTrue(cards.any { it.title == "План месяца" && it.status.contains("Android") })
    }

    @Test
    fun sectionCardsDoNotExposeDevSeedText() {
        val dashboard = dashboardFixture().copy(
            categories = listOf(
                CategorySummary("Dev Home", "expense", "household", id = "cat-home", iconKey = "home", color = "#E35D4F"),
            ),
            transactions = listOf(
                TransactionSummary(
                    type = "expense",
                    amount = "69.75",
                    currency = "USD",
                    occurredAt = "2026-05-17T12:30:00Z",
                    description = "Dev household supplies",
                    transferScope = null,
                    transferStatus = null,
                    id = "txn-expense",
                    accountId = "acc-card",
                    categoryId = "cat-home",
                ),
            ),
        )

        val renderedText = buildString {
            append(sectionCards(AppSection.Operations, dashboard).joinToString(" ") { "${it.title} ${it.body} ${it.status}" })
            append(" ")
            append(sectionCards(AppSection.Analytics, dashboard).joinToString(" ") { "${it.title} ${it.body} ${it.status}" })
        }

        assertFalse(renderedText.contains("Dev ", ignoreCase = true))
        assertTrue(renderedText.contains("Домашние покупки"))
        assertTrue(renderedText.contains("Дом"))
    }

    @Test
    fun assetKindsUseBackendAccountTypeValues() {
        assertEquals("card", AssetKind.Card.apiValue)
        assertEquals("metal", AssetKind.Metal.apiValue)
    }

    @Test
    fun quickAddIncomeDoesNotFallbackToExpenseCategory() {
        val categories = listOf(
            CategorySummary("Продукты", "expense", "personal", id = "cat-food", iconKey = "food", color = "#E35D4F"),
            CategorySummary("Зарплата", "income", "personal", id = "cat-salary", iconKey = "income", color = "#2E7D62"),
        )

        assertEquals("cat-salary", categories.quickAddCategoryFor("", "income")?.id)
        assertEquals("cat-salary", categories.quickAddCategoryFor("cat-salary", "income")?.id)
        assertEquals("cat-food", categories.quickAddCategoryFor("cat-salary", "expense")?.id)
    }

    @Test
    fun quickAddIncomeCreatesFallbackWhenOnlyExpenseCategoriesExist() {
        val categories = listOf(
            CategorySummary("Продукты", "expense", "personal", id = "cat-food", iconKey = "food", color = "#E35D4F"),
        )

        assertEquals(null, categories.quickAddCategoryFor("cat-food", "income"))
    }

    private fun dashboardFixture(): FinanceDashboard {
        return FinanceDashboard(
            session = SessionStatus(true, "Пользователь", "household"),
            accounts = listOf(
                AccountSummary("Карта", "card", "personal", "USD", "925.50", id = "acc-card"),
                AccountSummary("Вклад", "deposit", "personal", "USD", "100.00", id = "acc-save"),
                AccountSummary("Брокер", "brokerage", "personal", "USD", "2200.00", id = "acc-broker"),
                AccountSummary("Металл", "metal", "personal", "USD", "300.00", id = "acc-metal"),
            ),
            categories = listOf(
                CategorySummary("Продукты", "expense", "personal", id = "cat-food", iconKey = "food", color = "#E35D4F"),
            ),
            transactions = listOf(
                TransactionSummary(
                    type = "transfer",
                    amount = "25.00",
                    currency = "USD",
                    occurredAt = "2026-05-18T08:30:00Z",
                    description = "На вклад",
                    transferScope = "personal_same_owner",
                    transferStatus = "posted",
                    id = "txn-transfer",
                    accountId = "acc-card",
                    counterpartyAccountId = "acc-save",
                ),
                TransactionSummary(
                    type = "expense",
                    amount = "69.75",
                    currency = "USD",
                    occurredAt = "2026-05-17T12:30:00Z",
                    description = "Супермаркет",
                    transferScope = null,
                    transferStatus = null,
                    id = "txn-expense",
                    accountId = "acc-card",
                    categoryId = "cat-food",
                ),
            ),
            totals = listOf(MoneyTotal("USD", "250.00", "69.75", "180.25")),
            reportTransferCount = 1,
        )
    }
}
