package com.finance.mvp.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.BrokerageAccountProfile
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.api.TaxAccountType
import com.finance.mvp.investments.InvestmentOverview
import com.finance.mvp.local.CachedInvestmentRecommendation
import com.finance.mvp.ui.investments.InvestmentPortfolioContent
import com.finance.mvp.ui.theme.FinanceTheme
import org.junit.Rule
import org.junit.Test

class InvestmentPortfolioUiTest {
    @get:Rule val compose = createComposeRule()

    @Test fun showsTwoSberAccountsAndCombinedPortfolio() {
        val main = BrokerageAccountProfile(
            "11111111-1111-4111-8111-111111111111", Brokerage.SberInvestments, "Основной", TaxAccountType.Brokerage,
        )
        val iis = BrokerageAccountProfile(
            "22222222-2222-4222-8222-222222222222", Brokerage.SberInvestments, "ИИС жены", TaxAccountType.IisIII,
        )
        compose.setContent {
            FinanceTheme {
                InvestmentPortfolioContent(
                    overview = InvestmentOverview(
                        snapshots = listOf(
                            PortfolioSnapshot(
                                id = "snap-main", importId = "import-main", brokerage = Brokerage.SberInvestments,
                                observedAt = "2026-09-20T10:00:00Z", currency = "RUB",
                                freeCash = "100", monthlyContribution = "1000", totalValue = "5000",
                                positions = emptyList(), createdAt = "2026-09-20T10:00:00Z",
                                accountProfile = main,
                            ),
                            PortfolioSnapshot(
                                id = "snap-iis", importId = "import-iis", brokerage = Brokerage.SberInvestments,
                                observedAt = "2026-09-20T11:00:00Z", currency = "RUB",
                                freeCash = "200", monthlyContribution = "2000", totalValue = "7000",
                                positions = emptyList(), createdAt = "2026-09-20T11:00:00Z",
                                accountProfile = iis,
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
        compose.onNodeWithText("12000.00 RUB").assertIsDisplayed()
        compose.onNodeWithText("2 счёта • 0 позиций").assertIsDisplayed()
        compose.onNodeWithText("Основной").assertExists()
        compose.onNodeWithText("ИИС жены").assertExists()
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

    @Test fun showsRestoredHistorySummaryAndAccountProfiles() {
        val main = BrokerageAccountProfile(
            "33333333-3333-4333-8333-333333333333", Brokerage.SberInvestments, "Основной", TaxAccountType.Brokerage,
        )
        val iis = BrokerageAccountProfile(
            "44444444-4444-4444-8444-444444444444", Brokerage.SberInvestments, "ИИС жены", TaxAccountType.IisIII,
        )
        compose.setContent {
            FinanceTheme {
                InvestmentPortfolioContent(
                    overview = InvestmentOverview(
                        recommendations = listOf(
                            CachedInvestmentRecommendation(
                                job = RecommendationJob(
                                    id = "history-job", snapshotIds = listOf("one", "two"), status = RecommendationStatus.Ready,
                                    attemptCount = 1, marketDataAsOf = "2026-09-20T10:00:00Z", cashFirstAdjustments = emptyList(),
                                    createdAt = "2026-09-20T10:00:00Z", updatedAt = "2026-09-20T10:01:00Z",
                                    completedAt = "2026-09-20T10:01:00Z",
                                ),
                                report = null,
                                accountProfiles = listOf(main, iis),
                                reportSummary = "Портфель соответствует профилю риска",
                                reportPath = "/api/v1/investments/recommendation-jobs/history-job/report",
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

        compose.onNodeWithText("СберИнвестиции: Основной • СберИнвестиции: ИИС жены").assertIsDisplayed()
        compose.onNodeWithText("Краткий итог").assertIsDisplayed()
        compose.onNodeWithText("Портфель соответствует профилю риска").assertIsDisplayed()
    }
}
