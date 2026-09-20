package com.finance.mvp.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.investments.InvestmentOverview
import com.finance.mvp.ui.investments.InvestmentPortfolioContent
import com.finance.mvp.ui.theme.FinanceTheme
import org.junit.Rule
import org.junit.Test

class InvestmentPortfolioUiTest {
    @get:Rule val compose = createComposeRule()

    @Test fun showsCombinedAndBrokerPortfolioWithRecommendationAction() {
        compose.setContent {
            FinanceTheme {
                InvestmentPortfolioContent(
                    overview = InvestmentOverview(
                        snapshots = listOf(
                            PortfolioSnapshot(
                                id = "snap", importId = "import", brokerage = Brokerage.Finam,
                                observedAt = "2026-09-20T10:00:00Z", currency = "RUB",
                                freeCash = "100", monthlyContribution = "1000", totalValue = "5000",
                                positions = emptyList(), createdAt = "2026-09-20T10:00:00Z",
                            ),
                        ),
                    ),
                    loading = false,
                    message = null,
                    onRefresh = {}, onAddPortfolio = {}, onUpdatePolicy = {}, onStartRecommendation = {},
                )
            }
        }

        compose.onNodeWithTag("investment-portfolio-panel").assertIsDisplayed()
        compose.onNodeWithText("Объединённый портфель").assertIsDisplayed()
        compose.onNodeWithText("Финам").assertIsDisplayed()
        compose.onNodeWithTag("refresh-investment-recommendations").assertIsDisplayed()
    }
}
