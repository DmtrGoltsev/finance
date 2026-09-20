package com.finance.mvp.investments

import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.InvestmentInstrumentType
import com.finance.mvp.api.InvestmentRiskBucket
import com.finance.mvp.api.PortfolioPosition
import java.math.BigDecimal
import java.util.Locale

class PortfolioOcrParser {
    fun parse(brokerage: Brokerage, pages: List<String>): List<PortfolioPosition> {
        val pageLines = pages.map { page -> page.lineSequence().map(String::trim).filter(String::isNotBlank).toList() }
        val candidates = mutableListOf<PortfolioPosition>()
        pageLines.forEach { lines ->
        lines.forEachIndexed { index, rawLine ->
            val line = rawLine.uppercase(Locale.ROOT)
            val isin = ISIN.find(line)?.value
            val ticker = tickerFrom(line)
            if (isin == null && ticker == null) return@forEachIndexed

            val windowStart = (index - 2).coerceAtLeast(0)
            val windowEnd = (index + 7).coerceAtMost(lines.lastIndex)
            val window = lines.subList(windowStart, windowEnd + 1)
            val name = inferName(lines, index, rawLine, ticker, isin)
            val instrumentType = inferType(window.joinToString(" "))
            val numbers = window.mapNotNull(::moneyNumber)
            val quantity = window.firstNotNullOfOrNull(::quantityNumber) ?: "0"
            val marketValue = numbers.lastOrNull() ?: "0"
            val marketPrice = numbers.firstOrNull { it != quantity }
            candidates += PortfolioPosition(
                instrumentName = name,
                ticker = ticker,
                isin = isin,
                instrumentType = instrumentType,
                riskBucket = when (instrumentType) {
                    InvestmentInstrumentType.Bond -> InvestmentRiskBucket.Conservative
                    InvestmentInstrumentType.Fund -> InvestmentRiskBucket.Moderate
                    InvestmentInstrumentType.Stock -> InvestmentRiskBucket.Aggressive
                },
                quantity = quantity,
                marketPrice = marketPrice,
                marketValue = marketValue,
            )
        }
        }
        return candidates
            .distinctBy { it.isin ?: it.ticker ?: it.instrumentName.lowercase(Locale.ROOT) }
            .take(MAX_POSITIONS)
            .ifEmpty { brokerFallback(pageLines.flatten(), brokerage) }
    }

    private fun brokerFallback(lines: List<String>, brokerage: Brokerage): List<PortfolioPosition> {
        val marker = when (brokerage) {
            Brokerage.Sinara -> "СИНАРА"
            Brokerage.SberInvestments -> "СБЕР"
            Brokerage.Finam -> "ФИНАМ"
        }
        if (lines.none { it.uppercase(Locale.ROOT).contains(marker) }) return emptyList()
        return emptyList()
    }

    private fun tickerFrom(line: String): String? {
        return TICKER.findAll(line)
            .map { it.value }
            .firstOrNull { it !in STOP_WORDS && !ISIN.matches(it) && it.any(Char::isLetter) }
    }

    private fun inferName(
        lines: List<String>,
        index: Int,
        rawLine: String,
        ticker: String?,
        isin: String?,
    ): String {
        val cleanCurrent = rawLine
            .replace(ticker.orEmpty(), "", ignoreCase = true)
            .replace(isin.orEmpty(), "", ignoreCase = true)
            .trim(' ', '-', '•')
        if (cleanCurrent.length >= 3) return cleanCurrent.take(300)
        return lines.asSequence()
            .drop((index - 2).coerceAtLeast(0))
            .take(3)
            .map(String::trim)
            .firstOrNull { candidate ->
                candidate.length >= 3 &&
                    !candidate.matches(NUMERIC_LINE) &&
                    tickerFrom(candidate.uppercase(Locale.ROOT)) == null
            }
            ?.take(300)
            ?: ticker
            ?: isin
            ?: "Инструмент"
    }

    private fun inferType(text: String): InvestmentInstrumentType {
        val normalized = text.lowercase(Locale.ROOT)
        return when {
            BOND_WORDS.any(normalized::contains) -> InvestmentInstrumentType.Bond
            FUND_WORDS.any(normalized::contains) -> InvestmentInstrumentType.Fund
            else -> InvestmentInstrumentType.Stock
        }
    }

    private fun quantityNumber(line: String): String? {
        val match = QUANTITY.find(line) ?: return null
        return normalizeDecimal(match.groupValues[1])
    }

    private fun moneyNumber(line: String): String? {
        if (!MONEY_MARKER.containsMatchIn(line)) return null
        val match = DECIMAL.find(line.replace("\u00A0", " ")) ?: return null
        return normalizeDecimal(match.value)
    }

    private fun normalizeDecimal(raw: String): String? {
        val compact = raw.replace(" ", "").replace(',', '.').filter { it.isDigit() || it == '.' || it == '-' }
        return runCatching { BigDecimal(compact).stripTrailingZeros().toPlainString() }.getOrNull()
    }

    private companion object {
        const val MAX_POSITIONS = 500
        val ISIN = Regex("\\b[A-Z]{2}[A-Z0-9]{9}[0-9]\\b")
        val TICKER = Regex("\\b[A-ZА-Я][A-Z0-9._-]{1,11}\\b")
        val QUANTITY = Regex("([0-9]+(?:[.,][0-9]+)?)\\s*(?:шт|лот|лотов|акц)", RegexOption.IGNORE_CASE)
        val MONEY_MARKER = Regex("(?:₽|руб|RUB|стоим|цена|портфел)", RegexOption.IGNORE_CASE)
        val DECIMAL = Regex("-?[0-9][0-9 \\u00A0]*(?:[.,][0-9]+)?")
        val NUMERIC_LINE = Regex("^[0-9 .,₽%+-]+$")
        val BOND_WORDS = listOf("облига", "офз", "купон", "погаш")
        val FUND_WORDS = listOf("фонд", "бпиф", "etf")
        val STOP_WORDS = setOf(
            "RUB", "RUR", "ИИС", "АКЦИИ", "ОБЛИГАЦИИ", "ФОНДЫ", "ПОРТФЕЛЬ", "ДОХОД", "ЦЕНА", "СУММА",
            "СИНАРА", "СБЕР", "ФИНАМ", "MOEX",
        )
    }
}
