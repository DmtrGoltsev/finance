package com.finance.mvp.ui

import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.AssetCategory
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

        assertEquals(listOf("Главная", "Операции", "Активы", "Категории расходов", "Аналитика"), titles)
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
        assertEquals("Перед отправкой выберите два личных счёта.", transferPairValidationMessage(personal, shared))
        assertEquals("Перед отправкой выберите счета в одной валюте: конвертация в переводе недоступна.", transferPairValidationMessage(personal, eur))
        assertEquals(null, transferPairValidationMessage(personal, personal.copy(id = "personal-2")))
    }

    @Test
    fun writableModesAreAlwaysPersonalEvenWhenSessionHasHousehold() {
        assertEquals(listOf(FinanceMode.Personal), writableFinanceModes(hasHousehold = false))
        assertEquals(listOf(FinanceMode.Personal), writableFinanceModes(hasHousehold = true))
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

        assertTrue(overviewReason.orEmpty().contains("личных финансах"))
        assertTrue(missingCategoryReason.orEmpty().contains("нет категории", ignoreCase = true))
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
    fun legacyGroupSaveActionMigratesWhenInvestmentIsChecked() {
        val action = legacyGroupSaveAction("  Брокер  ", isInvestmentChecked = true)

        assertTrue(action is LegacyGroupSaveAction.MigrateToInvestment)
        assertEquals("Брокер", (action as LegacyGroupSaveAction.MigrateToInvestment).name)
    }

    @Test
    fun legacyGroupSaveActionRenamesWhenInvestmentIsNotChecked() {
        val action = legacyGroupSaveAction("  Брокер  ", isInvestmentChecked = false)

        assertTrue(action is LegacyGroupSaveAction.Rename)
        assertEquals("Брокер", (action as LegacyGroupSaveAction.Rename).name)
    }

    @Test
    fun legacyGroupSaveActionRejectsBlankNameBeforeRenameOrMigration() {
        val action = legacyGroupSaveAction("   ", isInvestmentChecked = true)

        assertTrue(action is LegacyGroupSaveAction.Invalid)
    }

    @Test
    fun assetCategoryGroupEditPreservesIconAndUpdatesInvestmentFlag() {
        val category = AssetCategory(
            id = "asset-broker",
            name = "Брокер",
            scopeType = "personal",
            currency = "RUB",
            manualAmount = "0",
            isInvestment = true,
            assetType = "brokerage",
            iconKey = "chart",
            version = 7,
        )

        val updated = updatedAssetCategoryFromGroupEdit(
            category = category,
            nameDraft = "  Карта  ",
            isInvestmentChecked = false,
        )

        requireNotNull(updated)
        assertEquals("Карта", updated.name)
        assertFalse(updated.isInvestment)
        assertEquals("chart", updated.iconKey)
        assertEquals("brokerage", updated.assetType)
        assertEquals("0", updated.manualAmount)
        assertEquals(7, updated.version)
    }

    @Test
    fun assetCategoryGroupEditUpdatesManualAmountForManualOnlyCategory() {
        val category = AssetCategory(
            id = "asset-cash",
            name = "Manual cash",
            scopeType = "personal",
            currency = "RUB",
            manualAmount = "100",
            isInvestment = false,
            assetType = "cash",
            iconKey = "cash",
            version = 3,
        )

        val updated = updatedAssetCategoryFromGroupEdit(
            category = category,
            nameDraft = "Manual cash",
            isInvestmentChecked = false,
            manualAmountDraft = " 1234,50 ",
            canEditManualAmount = true,
        )

        requireNotNull(updated)
        assertEquals("1234.50", updated.manualAmount)
        assertEquals("cash", updated.iconKey)
        assertEquals("cash", updated.assetType)
        assertEquals("RUB", updated.currency)
    }

    @Test
    fun assetCategoryGroupEditPreservesManualAmountForAccountBackedCategory() {
        val category = AssetCategory(
            id = "asset-broker",
            name = "Broker",
            scopeType = "personal",
            currency = "RUB",
            manualAmount = "100",
            isInvestment = true,
            assetType = "brokerage",
            iconKey = "chart",
        )

        val updated = updatedAssetCategoryFromGroupEdit(
            category = category,
            nameDraft = "Broker",
            isInvestmentChecked = true,
            manualAmountDraft = "999",
            canEditManualAmount = false,
        )

        requireNotNull(updated)
        assertEquals("100", updated.manualAmount)
    }

    @Test
    fun d401LegacyMetalSummaryWithNoAccountsAllowsManualAmountCreation() {
        val summary = AssetSummary(
            kind = AssetKind.Metal,
            balance = BigDecimal.ZERO,
            currency = "RUB",
            count = 0,
        )

        assertTrue(shouldEditLegacyAssetGroupManualAmount(summary, emptyList()))

        val request = legacyManualAssetCategoryCreateRequest(
            kind = summary.kind,
            nameDraft = " Металл ",
            manualAmountDraft = "777,70",
            isInvestmentChecked = false,
            target = LegacyAssetCategoryMigrationTarget(
                scopeType = "personal",
                householdId = null,
                currency = "RUB",
            ),
        )

        requireNotNull(request)
        assertEquals("Металл", request.name)
        assertEquals("777.70", request.manualAmount)
        assertEquals("metal", request.assetType)
        assertFalse(request.isInvestment)
        assertEquals("personal", request.scopeType)
    }

    @Test
    fun legacyManualAmountCreationUsesAssetKindNotDisplayName() {
        val summary = AssetSummary(
            kind = AssetKind.Metal,
            balance = BigDecimal.ZERO,
            currency = "RUB",
            count = 0,
        )

        val request = legacyManualAssetCategoryCreateRequest(
            kind = summary.kind,
            nameDraft = "QA legacy bullion",
            manualAmountDraft = "1.23",
            isInvestmentChecked = true,
            target = LegacyAssetCategoryMigrationTarget("personal", null, "RUB"),
        )

        requireNotNull(request)
        assertEquals("QA legacy bullion", request.name)
        assertEquals("metal", request.assetType)
        assertTrue(request.isInvestment)
    }

    @Test
    fun accountBackedBrokerAndCardLegacyGroupsDoNotAllowManualAmountCreation() {
        val brokerAccount = AccountSummary(
            "Брокер",
            "brokerage",
            "personal",
            "RUB",
            "150000.00",
            id = "acc-broker",
        )
        val cardAccount = AccountSummary(
            "Карта",
            "card",
            "personal",
            "RUB",
            "25000.00",
            id = "acc-card",
        )

        assertFalse(
            shouldEditLegacyAssetGroupManualAmount(
                AssetSummary(AssetKind.Brokerage, BigDecimal("150000.00"), "RUB", 1),
                listOf(brokerAccount),
            ),
        )
        assertFalse(
            shouldEditLegacyAssetGroupManualAmount(
                AssetSummary(AssetKind.Card, BigDecimal("25000.00"), "RUB", 1),
                listOf(cardAccount),
            ),
        )
        assertFalse(
            shouldEditLegacyAssetGroupManualAmount(
                AssetSummary(AssetKind.Bank, BigDecimal.ZERO, "RUB", 0),
                emptyList(),
            ),
        )
    }

    @Test
    fun legacyMetalManualOnlyCategoryAllowsManualAmountEditing() {
        val row = AssetCategoryUiRow(
            category = AssetCategory(
                id = "asset-metal",
                name = "Металл",
                scopeType = "personal",
                currency = "RUB",
                manualAmount = "300.00",
                isInvestment = false,
                assetType = "metal",
                iconKey = "gold",
            ),
            totalAmount = "300.00",
            manualAmount = "300.00",
            accountsTotal = "0",
            linkedAccountCount = 0,
            currency = "RUB",
            scopeTitle = "Личные",
        )
        val staleLocalAccount = AccountSummary(
            "Металл",
            "metal",
            "personal",
            "RUB",
            "300.00",
            id = "acc-metal",
            assetCategoryId = "asset-metal",
        )

        assertTrue(shouldEditAssetCategoryManualAmount(row, listOf(staleLocalAccount)))
        val updated = updatedAssetCategoryFromGroupEdit(
            category = row.category,
            nameDraft = "Металл",
            isInvestmentChecked = false,
            manualAmountDraft = "777,70",
            canEditManualAmount = shouldEditAssetCategoryManualAmount(row, listOf(staleLocalAccount)),
        )

        requireNotNull(updated)
        assertEquals("777.70", updated.manualAmount)
        assertEquals("gold", updated.iconKey)
    }

    @Test
    fun accountBackedAssetCategoryDoesNotAllowManualAmountEditing() {
        val row = AssetCategoryUiRow(
            category = AssetCategory(
                id = "asset-broker",
                name = "Брокер",
                scopeType = "personal",
                currency = "RUB",
                manualAmount = "0",
                isInvestment = true,
                assetType = "brokerage",
                iconKey = "chart",
            ),
            totalAmount = "2200.00",
            manualAmount = "0",
            accountsTotal = "2200.00",
            linkedAccountCount = 1,
            currency = "RUB",
            scopeTitle = "Личные",
        )
        val account = AccountSummary(
            "Брокер",
            "brokerage",
            "personal",
            "RUB",
            "2200.00",
            id = "acc-broker",
            assetCategoryId = "asset-broker",
        )

        assertFalse(shouldEditAssetCategoryManualAmount(row, listOf(account)))
        val updated = updatedAssetCategoryFromGroupEdit(
            category = row.category,
            nameDraft = "Брокер",
            isInvestmentChecked = true,
            manualAmountDraft = "999",
            canEditManualAmount = shouldEditAssetCategoryManualAmount(row, listOf(account)),
        )

        requireNotNull(updated)
        assertEquals("0", updated.manualAmount)
        assertEquals("chart", updated.iconKey)
    }

    @Test
    fun assetCategoryGroupEditRejectsInvalidManualAmountForManualOnlyCategory() {
        val category = AssetCategory(
            id = "asset-cash",
            name = "Manual cash",
            scopeType = "personal",
            currency = "RUB",
            manualAmount = "100",
            isInvestment = false,
            assetType = "cash",
            iconKey = "cash",
        )

        assertEquals(
            null,
            updatedAssetCategoryFromGroupEdit(
                category = category,
                nameDraft = "Manual cash",
                isInvestmentChecked = false,
                manualAmountDraft = "",
                canEditManualAmount = true,
            ),
        )
    }

    @Test
    fun assetCategoryGroupEditRejectsBlankName() {
        val category = AssetCategory(
            id = "asset-broker",
            name = "Брокер",
            scopeType = "personal",
            currency = "RUB",
            manualAmount = "0",
            isInvestment = true,
            assetType = "brokerage",
            iconKey = "chart",
        )

        assertEquals(null, updatedAssetCategoryFromGroupEdit(category, "   ", isInvestmentChecked = false))
        assertTrue(assetCategoryGroupEditError("   ", "0", canEditManualAmount = false).contains("название"))
    }

    @Test
    fun legacyInvestmentMigrationUsesAccountsWhenOverviewIsUnambiguous() {
        val selection = selectLegacyAssetCategoryMigrationTarget(
            selectedMode = FinanceMode.Overview,
            accounts = listOf(
                AccountSummary("Брокер", "brokerage", "personal", "usd", "2200.00", id = "acc-broker"),
            ),
            sessionHouseholdId = "household",
            fallbackCurrency = "RUB",
            groupName = "Брокер",
        )

        assertTrue(selection is LegacyAssetCategoryMigrationTargetSelection.Ready)
        val target = (selection as LegacyAssetCategoryMigrationTargetSelection.Ready).target
        assertEquals("personal", target.scopeType)
        assertEquals(null, target.householdId)
        assertEquals("USD", target.currency)
    }

    @Test
    fun legacyInvestmentMigrationRequestCarriesAccountVersions() {
        val selection = legacyInvestmentMigrationCreateRequest(
            kind = AssetKind.Brokerage,
            nameDraft = "  Брокер  ",
            target = LegacyAssetCategoryMigrationTarget("personal", null, "RUB"),
            accounts = listOf(
                AccountSummary(
                    "Брокер",
                    "brokerage",
                    "personal",
                    "RUB",
                    "2200.00",
                    id = "acc-broker",
                    version = 7,
                ),
            ),
            assetCategoryId = "asset-cat-broker",
        )

        assertTrue(selection is LegacyInvestmentMigrationRequestSelection.Ready)
        val request = (selection as LegacyInvestmentMigrationRequestSelection.Ready).request
        assertEquals("asset-cat-broker", request.assetCategoryId)
        assertEquals("Брокер", request.name)
        assertEquals("brokerage", request.assetType)
        assertEquals(listOf("acc-broker"), request.accountIds)
        assertEquals(7, request.accountVersions["acc-broker"])
    }

    @Test
    fun legacyInvestmentMigrationRequestBlocksAccountsWithoutVersions() {
        val selection = legacyInvestmentMigrationCreateRequest(
            kind = AssetKind.Brokerage,
            nameDraft = "Брокер",
            target = LegacyAssetCategoryMigrationTarget("personal", null, "RUB"),
            accounts = listOf(
                AccountSummary(
                    "Брокер",
                    "brokerage",
                    "personal",
                    "RUB",
                    "2200.00",
                    id = "acc-broker",
                    version = null,
                ),
            ),
            assetCategoryId = "asset-cat-broker",
        )

        assertTrue(selection is LegacyInvestmentMigrationRequestSelection.Blocked)
        assertTrue((selection as LegacyInvestmentMigrationRequestSelection.Blocked).message.contains("версии"))
    }

    @Test
    fun legacyInvestmentMigrationBlocksMixedScopeOverview() {
        val selection = selectLegacyAssetCategoryMigrationTarget(
            selectedMode = FinanceMode.Overview,
            accounts = listOf(
                AccountSummary("Личный брокер", "brokerage", "personal", "RUB", "100.00", id = "acc-personal"),
                AccountSummary(
                    "Общий брокер",
                    "brokerage",
                    "shared",
                    "RUB",
                    "200.00",
                    id = "acc-shared",
                    householdId = "household",
                ),
            ),
            sessionHouseholdId = "household",
            fallbackCurrency = "RUB",
            groupName = "Брокер",
        )

        assertTrue(selection is LegacyAssetCategoryMigrationTargetSelection.Blocked)
        assertTrue((selection as LegacyAssetCategoryMigrationTargetSelection.Blocked).message.contains("личные и общие"))
    }

    @Test
    fun emptyPersonalLegacyInvestmentMigrationCreatesTargetFromModeAndFallbackCurrency() {
        val selection = selectLegacyAssetCategoryMigrationTarget(
            selectedMode = FinanceMode.Personal,
            accounts = emptyList(),
            sessionHouseholdId = null,
            fallbackCurrency = "usd",
            groupName = "Брокер",
        )

        assertTrue(selection is LegacyAssetCategoryMigrationTargetSelection.Ready)
        val target = (selection as LegacyAssetCategoryMigrationTargetSelection.Ready).target
        assertEquals("personal", target.scopeType)
        assertEquals(null, target.householdId)
        assertEquals("USD", target.currency)
    }

    @Test
    fun emptyLegacyInvestmentMigrationFallsBackToPersonalScope() {
        val selection = selectLegacyAssetCategoryMigrationTarget(
            selectedMode = FinanceMode.Overview,
            accounts = emptyList(),
            sessionHouseholdId = "household",
            fallbackCurrency = "RUB",
            groupName = "Брокер",
        )

        assertTrue(selection is LegacyAssetCategoryMigrationTargetSelection.Ready)
        val target = (selection as LegacyAssetCategoryMigrationTargetSelection.Ready).target
        assertEquals("personal", target.scopeType)
        assertEquals(null, target.householdId)
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

    @Test
    fun expenseOperationAccountsUseOnlyPaymentAccounts() {
        val payment = AccountSummary("Card", "card", "personal", "USD", "10.00", id = "acc-card")
        val savings = AccountSummary(
            "Savings",
            "deposit",
            "personal",
            "USD",
            "100.00",
            id = "acc-save",
            isPaymentAccount = false,
        )
        val accounts = listOf(payment, savings)

        assertEquals(listOf("acc-card"), accounts.operationAccountsFor(QuickEntryType.Expense).map { it.id })
        assertEquals(listOf("acc-card", "acc-save"), accounts.operationAccountsFor(QuickEntryType.Income).map { it.id })
    }

    @Test
    fun writableOperationAccountsExcludeNonPaymentOnlyForExpense() {
        val payment = AccountSummary("Card", "card", "personal", "USD", "10.00", id = "acc-card")
        val nonPayment = AccountSummary(
            "QANonPay0836",
            "deposit",
            "personal",
            "USD",
            "100.00",
            id = "acc-nonpay",
            isPaymentAccount = false,
        )
        val sharedNonPayment = nonPayment.copy(
            name = "Shared savings",
            ownershipType = "shared",
            householdId = "household",
            id = "acc-shared-nonpay",
        )
        val archivedPayment = payment.copy(id = "acc-archived", status = "archived")
        val accounts = listOf(payment, nonPayment, sharedNonPayment, archivedPayment)

        assertEquals(
            listOf("acc-card"),
            accounts.writableOperationAccountsFor(QuickEntryType.Expense, FinanceMode.Personal).map { it.id },
        )
        assertEquals(
            listOf("acc-card", "acc-nonpay"),
            accounts.writableOperationAccountsFor(QuickEntryType.Income, FinanceMode.Personal).map { it.id },
        )
        assertEquals(
            listOf("acc-shared-nonpay"),
            accounts.writableOperationAccountsFor(QuickEntryType.Income, FinanceMode.Shared).map { it.id },
        )
    }

    @Test
    fun reportMonthBoundaryUsesDateOnlyMonthStartAndEnd() {
        val boundary = "2026-02".reportMonthBoundary()

        assertEquals("2026-02-01", boundary.startDate)
        assertEquals("2026-02-28", boundary.endDate)
        assertTrue("2026-02-28".isDateOnly())
        assertFalse("2026-02-28T00:00:00Z".isDateOnly())
    }

    @Test
    fun reportMonthSwitcherKeepsMonthNavigationCompactAndDeterministic() {
        val state = reportMonthSwitcherState(
            selectedMonth = "2026-08",
            currentMonth = "2026-08",
        )

        assertEquals("Август 2026", state.label)
        assertEquals("2026-07", state.previousMonth)
        assertEquals("2026-08", state.currentMonth)
        assertEquals("2026-09", state.nextMonth)
    }

    @Test
    fun operationsSortNewestByDateThenOccurredCreatedAndId() {
        val oldest = TransactionSummary(
            type = "income",
            amount = "1",
            currency = "USD",
            occurredAt = "2026-08-22T12:00:00Z",
            description = "oldest",
            transferScope = null,
            transferStatus = null,
            id = "a",
            accountId = "payment",
            transactionDate = "2026-08-22",
            createdAt = "2026-08-22T12:01:00Z",
        )
        val newerExpense = oldest.copy(
            type = "expense",
            description = "newer expense",
            id = "b",
            createdAt = "2026-08-22T12:02:00Z",
        )
        val newestTransfer = oldest.copy(
            type = "transfer",
            description = "newest transfer",
            id = "c",
            counterpartyAccountId = "broker",
            createdAt = "2026-08-22T12:03:00Z",
        )

        assertEquals(
            listOf("c", "b", "a"),
            listOf(oldest, newestTransfer, newerExpense).sortedNewestFirst().map { it.id },
        )
    }

    @Test
    fun categorySearchMatchesPartialTextAndSortsVerticalOptions() {
        val categories = listOf(
            CategorySummary("Супермаркеты", "expense", "personal", id = "market"),
            CategorySummary("Кафе и рестораны", "expense", "personal", id = "cafe"),
            CategorySummary("Такси", "expense", "personal", id = "taxi"),
        )

        assertEquals(listOf("cafe"), categories.filterCategories("рест").map { it.id })
        assertEquals(listOf("cafe", "market", "taxi"), categories.filterCategories("").map { it.id })
    }

    @Test
    fun quickAddSelectionImmediatelyAdoptsNewlyLoadedPaymentAccount() {
        assertEquals("", resolvedSelectionId("", emptyList()))
        assertEquals("payment", resolvedSelectionId("", listOf("payment")))
        assertEquals("payment", resolvedSelectionId("stale", listOf("payment", "cash")))
        assertEquals("cash", resolvedSelectionId("cash", listOf("payment", "cash")))
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
