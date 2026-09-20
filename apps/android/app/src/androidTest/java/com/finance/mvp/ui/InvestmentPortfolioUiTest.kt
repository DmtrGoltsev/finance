package com.finance.mvp.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.investments.InvestmentOverview
import com.finance.mvp.local.CachedInvestmentRecommendation
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
                    onRefresh = {}, onAddPortfolio = {}, hasDraft = true, onResumeDraft = {},
                    onUpdatePolicy = {}, onStartRecommendation = {},
                )
            }
        }

        compose.onNodeWithTag("investment-portfolio-panel").assertIsDisplayed()
        compose.onNodeWithText("Объединённый портфель").assertIsDisplayed()
        compose.onNodeWithText("Финам").assertIsDisplayed()
        compose.onNodeWithText("1 брокеров • 0 позиций").assertIsDisplayed()
        compose.onNodeWithTag("resume-investment-draft").assertIsDisplayed()
        compose.onNodeWithTag("refresh-investment-recommendations").assertIsDisplayed()
    }

    @Test fun showsReportAssumptionsWhenRecommendationIsExpanded() {
        compose.setContent {
            FinanceTheme {
                InvestmentPortfolioContent(
                    overview = InvestmentOverview(
                        recommendations = listOf(
                            CachedInvestmentRecommendation(
                                job = RecommendationJob(
                                    id = "job", snapshotIds = listOf("snapshot"), status = RecommendationStatus.Ready,
                                    attemptCount = 1, marketDataAsOf = "2026-09-20T10:00:00Z", cashFirstAdjustments = emptyList(),
                                    createdAt = "2026-09-20T10:00:00Z", updatedAt = "2026-09-20T10:01:00Z",
                                    completedAt = "2026-09-20T10:01:00Z",
                                ),
                                report = RecommendationReport(
                                    id = "report", jobId = "job", summary = "Результат",
                                    assumptions = mapOf("Горизонт" to "5 лет"),
                                    generatedAt = "2026-09-20T10:01:00Z", validUntil = "2026-09-21T10:01:00Z",
                                    isStale = false, disclaimer = "Не ИИР", actions = emptyList(), sources = emptyList(),
                                ),
                            ),
                        ),
                    ),
                    loading = false,
                    message = null,
                    onRefresh = {}, onAddPortfolio = {}, hasDraft = false, onResumeDraft = {},
                    onUpdatePolicy = {}, onStartRecommendation = {},
                )
            }
        }

        compose.onNodeWithText("Скрыть отчёт").assertIsDisplayed()
        compose.onNodeWithText("Допущения").assertIsDisplayed()
        compose.onNodeWithText("Горизонт: 5 лет").assertIsDisplayed()
    }
}
