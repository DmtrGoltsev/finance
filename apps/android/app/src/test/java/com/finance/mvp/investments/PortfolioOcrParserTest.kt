package com.finance.mvp.investments

import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.InvestmentInstrumentType
import com.finance.mvp.api.InvestmentRiskBucket
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PortfolioOcrParserTest {
    private val parser = PortfolioOcrParser()

    @Test
    fun parsesRussianStockFromBrokerScreensAndDeduplicatesPages() {
        val page = """
            Сбербанк
            SBER
            10 шт
            Цена 310,50 RUB
            Стоимость 3 105,00 RUB
        """.trimIndent()

        val positions = parser.parse(Brokerage.SberInvestments, listOf(page, page))

        assertEquals(1, positions.size)
        assertEquals("SBER", positions.single().ticker)
        assertEquals("10", positions.single().quantity)
        assertEquals("3105", positions.single().marketValue)
        assertEquals(InvestmentRiskBucket.Aggressive, positions.single().riskBucket)
    }

    @Test
    fun classifiesOfzAsConservativeBondAndKeepsIsin() {
        val positions = parser.parse(
            Brokerage.Finam,
            listOf("ОФЗ 26238\nRU000A1038V6\n5 шт\nСтоимость 3 100 RUB\nКупон 7,10%"),
        )

        assertEquals(1, positions.size)
        assertEquals("RU000A1038V6", positions.single().isin)
        assertEquals(InvestmentInstrumentType.Bond, positions.single().instrumentType)
        assertEquals(InvestmentRiskBucket.Conservative, positions.single().riskBucket)
    }

    @Test
    fun unrecognizedScreenshotReturnsEmptyEditableDraftSeed() {
        assertTrue(parser.parse(Brokerage.Sinara, listOf("Баланс портфеля пока пуст")).isEmpty())
    }
}
