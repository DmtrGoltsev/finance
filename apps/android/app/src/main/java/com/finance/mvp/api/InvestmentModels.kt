package com.finance.mvp.api

import org.json.JSONArray
import org.json.JSONObject

enum class Brokerage(val apiValue: String, val title: String) {
    Sinara("sinara", "Синара"),
    SberInvestments("sber_investments", "СберИнвестиции"),
    Finam("finam", "Финам"),
    ;

    companion object {
        fun fromApi(value: String): Brokerage = entries.firstOrNull { it.apiValue == value } ?: Sinara
    }
}

data class BrokerageAccountProfile(
    val id: String,
    val brokerage: Brokerage,
    val userLabel: String,
    val accountType: TaxAccountType,
)

enum class InvestmentInstrumentType(val apiValue: String, val title: String) {
    Stock("stock", "Акция"),
    Bond("bond", "Облигация"),
    Fund("fund", "Фонд"),
    ;

    companion object {
        fun fromApi(value: String): InvestmentInstrumentType = entries.firstOrNull { it.apiValue == value } ?: Stock
    }
}

enum class InvestmentRiskBucket(val apiValue: String, val title: String) {
    Conservative("conservative", "Консервативный"),
    Moderate("moderate", "Умеренный"),
    Aggressive("aggressive", "Агрессивный"),
    ;

    companion object {
        fun fromApi(value: String): InvestmentRiskBucket = entries.firstOrNull { it.apiValue == value } ?: Moderate
    }
}

enum class TaxAccountType(val apiValue: String, val title: String) {
    Brokerage("brokerage", "Брокерский счёт"),
    IisA("iis_a", "ИИС-А"),
    IisB("iis_b", "ИИС-Б"),
    IisIII("iis_iii", "ИИС-III"),
    ;

    companion object {
        fun fromApi(value: String): TaxAccountType = entries.firstOrNull { it.apiValue == value } ?: Brokerage
    }
}

data class InvestmentPolicy(
    val conservativePercent: String = "40",
    val moderatePercent: String = "30",
    val aggressivePercent: String = "30",
    val tolerancePercent: String = "5",
    val id: String? = null,
    val version: Int? = null,
)

data class PortfolioImport(
    val id: String,
    val brokerage: Brokerage,
    val screenshotCount: Int,
    val observedAt: String,
    val status: String,
    val createdAt: String,
    val accountProfile: BrokerageAccountProfile? = null,
)

data class PortfolioPosition(
    val id: String? = null,
    val instrumentName: String,
    val ticker: String? = null,
    val isin: String? = null,
    val instrumentType: InvestmentInstrumentType,
    val riskBucket: InvestmentRiskBucket,
    val quantity: String,
    val marketPrice: String? = null,
    val marketValue: String,
    val averagePrice: String? = null,
    val nominal: String? = null,
    val accruedInterest: String? = null,
    val couponRate: String? = null,
    val maturityDate: String? = null,
    val taxAccountType: TaxAccountType = TaxAccountType.Brokerage,
    val holdingStartedAt: String? = null,
    val estimatedFeeRate: String? = null,
)

data class PortfolioSnapshot(
    val id: String,
    val importId: String,
    val brokerage: Brokerage,
    val observedAt: String,
    val currency: String,
    val freeCash: String,
    val monthlyContribution: String,
    val totalValue: String,
    val positions: List<PortfolioPosition>,
    val createdAt: String,
    val accountProfile: BrokerageAccountProfile? = null,
)

enum class RecommendationStatus(val apiValue: String, val title: String) {
    Queued("queued", "В очереди"),
    Collecting("collecting", "Собираем данные"),
    Analyzing("analyzing", "Анализируем"),
    Ready("ready", "Готово"),
    Failed("failed", "Ошибка"),
    Stale("stale", "Требуется обновление"),
    ;

    companion object {
        fun fromApi(value: String): RecommendationStatus = entries.firstOrNull { it.apiValue == value } ?: Failed
    }
}

data class BucketAdjustment(
    val riskBucket: InvestmentRiskBucket,
    val addAmount: String,
    val reduceAmount: String,
    val currentPercent: String,
    val projectedPercent: String,
    val targetPercent: String,
    val withinTolerance: Boolean,
)

data class RecommendationJob(
    val id: String,
    val snapshotIds: List<String>,
    val status: RecommendationStatus,
    val attemptCount: Int,
    val marketDataAsOf: String?,
    val cashFirstAdjustments: List<BucketAdjustment>,
    val createdAt: String,
    val updatedAt: String,
    val completedAt: String?,
    val lastErrorCode: String? = null,
)

internal val RecommendationJob.needsDeliveryRetry: Boolean
    get() = status == RecommendationStatus.Failed && lastErrorCode == "delivery_failed"

data class RecommendationAction(
    val instrumentName: String,
    val ticker: String?,
    val isin: String?,
    val riskBucket: InvestmentRiskBucket,
    val action: String,
    val currentPercent: String,
    val targetPercent: String,
    val amount: String,
    val priority: Int,
    val rationale: String,
    val risks: String,
)

data class RecommendationSource(
    val title: String,
    val url: String,
    val publisher: String,
    val publishedAt: String?,
    val fetchedAt: String,
    val trustTier: String,
)

data class RecommendationReport(
    val id: String,
    val jobId: String,
    val summary: String,
    val assumptions: Map<String, String>,
    val generatedAt: String,
    val validUntil: String,
    val isStale: Boolean,
    val disclaimer: String,
    val actions: List<RecommendationAction>,
    val sources: List<RecommendationSource>,
)

data class RecommendationHistoryItem(
    val job: RecommendationJob,
    val accountProfiles: List<BrokerageAccountProfile>,
    val reportSummary: String?,
    val reportPath: String?,
)

data class RecommendationHistoryPage(
    val items: List<RecommendationHistoryItem>,
    val limit: Int,
    val nextCursor: String?,
    val hasMore: Boolean,
)

internal fun InvestmentPolicy.toPutJson(): JSONObject = JSONObject()
    .put("conservativePercent", conservativePercent)
    .put("moderatePercent", moderatePercent)
    .put("aggressivePercent", aggressivePercent)
    .put("tolerancePercent", tolerancePercent)

internal fun PortfolioPosition.toInputJson(): JSONObject = JSONObject().apply {
    put("instrumentName", instrumentName.trim())
    putNullable("ticker", ticker?.trim()?.uppercase())
    putNullable("isin", isin?.trim()?.uppercase())
    put("instrumentType", instrumentType.apiValue)
    put("riskBucket", riskBucket.apiValue)
    put("quantity", quantity)
    putNullable("marketPrice", marketPrice)
    put("marketValue", marketValue)
    putNullable("averagePrice", averagePrice)
    putNullable("nominal", nominal)
    putNullable("accruedInterest", accruedInterest)
    putNullable("couponRate", couponRate)
    putNullable("maturityDate", maturityDate)
    put("taxAccountType", taxAccountType.apiValue)
    putNullable("holdingStartedAt", holdingStartedAt)
    putNullable("estimatedFeeRate", estimatedFeeRate)
}

internal fun PortfolioSnapshot.toCacheJson(): String = JSONObject()
    .put("id", id)
    .put("importId", importId)
    .put("brokerage", brokerage.apiValue)
    .put("observedAt", observedAt)
    .put("currency", currency)
    .put("freeCash", freeCash)
    .put("monthlyContribution", monthlyContribution)
    .put("totalValue", totalValue)
    .put("positions", JSONArray().apply { positions.forEach { put(it.toInputJson().put("id", it.id)) } })
    .put("createdAt", createdAt)
    .putNullable("accountProfile", accountProfile?.toJson())
    .toString()

internal fun RecommendationJob.toCacheJson(): String = JSONObject()
    .put("id", id)
    .put("snapshotIds", JSONArray(snapshotIds))
    .put("status", status.apiValue)
    .put("attemptCount", attemptCount)
    .putNullable("marketDataAsOf", marketDataAsOf)
    .put("cashFirstAdjustments", JSONArray().apply { cashFirstAdjustments.forEach { put(it.toJson()) } })
    .put("createdAt", createdAt)
    .put("updatedAt", updatedAt)
    .putNullable("completedAt", completedAt)
    .putNullable("lastErrorCode", lastErrorCode)
    .toString()

internal fun RecommendationReport.toCacheJson(): String = JSONObject()
    .put("id", id)
    .put("jobId", jobId)
    .put("summary", summary)
    .put("assumptions", JSONObject(assumptions))
    .put("generatedAt", generatedAt)
    .put("validUntil", validUntil)
    .put("isStale", isStale)
    .put("disclaimer", disclaimer)
    .put("actions", JSONArray().apply { actions.forEach { put(it.toJson()) } })
    .put("sources", JSONArray().apply { sources.forEach { put(it.toJson()) } })
    .toString()

internal fun parseInvestmentPolicy(json: JSONObject): InvestmentPolicy = json.dataObjectForInvestment().let {
    InvestmentPolicy(
        conservativePercent = it.optString("conservativePercent", "40"),
        moderatePercent = it.optString("moderatePercent", "30"),
        aggressivePercent = it.optString("aggressivePercent", "30"),
        tolerancePercent = it.optString("tolerancePercent", "5"),
        id = it.optNullableInvestmentString("id"),
        version = if (it.has("version") && !it.isNull("version")) it.optInt("version") else null,
    )
}

internal fun parsePortfolioImport(json: JSONObject): PortfolioImport = json.dataObjectForInvestment().let {
    val profile = it.optJSONObject("accountProfile")?.let(::parseBrokerageAccountProfile)
    PortfolioImport(
        id = it.getString("id"),
        brokerage = profile?.brokerage ?: Brokerage.fromApi(it.optString("brokerage", Brokerage.Sinara.apiValue)),
        screenshotCount = it.getInt("screenshotCount"),
        observedAt = it.getString("observedAt"),
        status = it.getString("status"),
        createdAt = it.getString("createdAt"),
        accountProfile = profile,
    )
}

internal fun parsePortfolioSnapshot(json: JSONObject): PortfolioSnapshot = json.dataObjectForInvestment().let { data ->
    val profile = data.optJSONObject("accountProfile")?.let(::parseBrokerageAccountProfile)
    PortfolioSnapshot(
        id = data.getString("id"),
        importId = data.getString("importId"),
        brokerage = profile?.brokerage ?: Brokerage.fromApi(data.optString("brokerage", Brokerage.Sinara.apiValue)),
        observedAt = data.getString("observedAt"),
        currency = data.optString("currency", "RUB"),
        freeCash = data.optString("freeCash", "0"),
        monthlyContribution = data.optString("monthlyContribution", "0"),
        totalValue = data.optString("totalValue", "0"),
        positions = data.optJSONArray("positions").objects().map(::parsePortfolioPositionForCache),
        createdAt = data.getString("createdAt"),
        accountProfile = profile,
    )
}

internal fun parseRecommendationHistoryPage(json: JSONObject): RecommendationHistoryPage {
    val items = json.optJSONArray("items") ?: json.optJSONObject("data")?.optJSONArray("items") ?: JSONArray()
    val page = json.optJSONObject("page") ?: json.optJSONObject("data")?.optJSONObject("page") ?: JSONObject()
    return RecommendationHistoryPage(
        items = items.objects().map { item ->
            RecommendationHistoryItem(
                job = parseRecommendationJob(item.getJSONObject("job")),
                accountProfiles = item.optJSONArray("accountProfiles").objects().map(::parseBrokerageAccountProfile),
                reportSummary = item.optNullableInvestmentString("reportSummary"),
                reportPath = item.optNullableInvestmentString("reportPath"),
            )
        },
        limit = page.optInt("limit", 20),
        nextCursor = page.optNullableInvestmentString("nextCursor"),
        hasMore = page.optBoolean("hasMore"),
    )
}

internal fun parseBrokerageAccountProfile(json: JSONObject): BrokerageAccountProfile = BrokerageAccountProfile(
    id = json.getString("id"),
    brokerage = Brokerage.fromApi(json.getString("brokerage")),
    userLabel = json.getString("userLabel"),
    accountType = TaxAccountType.fromApi(json.getString("accountType")),
)

internal fun parseRecommendationJob(json: JSONObject): RecommendationJob = json.dataObjectForInvestment().let { data ->
    RecommendationJob(
        id = data.getString("id"),
        snapshotIds = data.optJSONArray("snapshotIds").strings(),
        status = RecommendationStatus.fromApi(data.getString("status")),
        attemptCount = data.optInt("attemptCount"),
        marketDataAsOf = data.optNullableInvestmentString("marketDataAsOf"),
        cashFirstAdjustments = data.optJSONArray("cashFirstAdjustments").objects().map { item ->
            BucketAdjustment(
                riskBucket = InvestmentRiskBucket.fromApi(item.getString("riskBucket")),
                addAmount = item.optString("addAmount", "0"),
                reduceAmount = item.optString("reduceAmount", "0"),
                currentPercent = item.optString("currentPercent", "0"),
                projectedPercent = item.optString("projectedPercent", "0"),
                targetPercent = item.optString("targetPercent", "0"),
                withinTolerance = item.optBoolean("withinTolerance"),
            )
        },
        createdAt = data.getString("createdAt"),
        updatedAt = data.getString("updatedAt"),
        completedAt = data.optNullableInvestmentString("completedAt"),
        lastErrorCode = data.optNullableInvestmentString("lastErrorCode"),
    )
}

internal fun parseRecommendationReport(json: JSONObject): RecommendationReport = json.dataObjectForInvestment().let { data ->
    RecommendationReport(
        id = data.getString("id"),
        jobId = data.getString("jobId"),
        summary = data.getString("summary"),
        assumptions = data.optJSONObject("assumptions").toStringMap(),
        generatedAt = data.getString("generatedAt"),
        validUntil = data.getString("validUntil"),
        isStale = data.optBoolean("isStale"),
        disclaimer = data.optString("disclaimer"),
        actions = data.optJSONArray("actions").objects().map { item ->
            RecommendationAction(
                instrumentName = item.getString("instrumentName"),
                ticker = item.optNullableInvestmentString("ticker"),
                isin = item.optNullableInvestmentString("isin"),
                riskBucket = InvestmentRiskBucket.fromApi(item.getString("riskBucket")),
                action = item.getString("action"),
                currentPercent = item.optString("currentPercent", "0"),
                targetPercent = item.optString("targetPercent", "0"),
                amount = item.optString("amount", "0"),
                priority = item.optInt("priority"),
                rationale = item.getString("rationale"),
                risks = item.getString("risks"),
            )
        },
        sources = data.optJSONArray("sources").objects().map { item ->
            RecommendationSource(
                title = item.getString("title"),
                url = item.getString("url"),
                publisher = item.getString("publisher"),
                publishedAt = item.optNullableInvestmentString("publishedAt"),
                fetchedAt = item.getString("fetchedAt"),
                trustTier = item.getString("trustTier"),
            )
        },
    )
}

internal fun parsePortfolioPositionForCache(json: JSONObject): PortfolioPosition = PortfolioPosition(
    id = json.optNullableInvestmentString("id"),
    instrumentName = json.getString("instrumentName"),
    ticker = json.optNullableInvestmentString("ticker"),
    isin = json.optNullableInvestmentString("isin"),
    instrumentType = InvestmentInstrumentType.fromApi(json.getString("instrumentType")),
    riskBucket = InvestmentRiskBucket.fromApi(json.getString("riskBucket")),
    quantity = json.optString("quantity", "0"),
    marketPrice = json.optNullableInvestmentString("marketPrice"),
    marketValue = json.optString("marketValue", "0"),
    averagePrice = json.optNullableInvestmentString("averagePrice"),
    nominal = json.optNullableInvestmentString("nominal"),
    accruedInterest = json.optNullableInvestmentString("accruedInterest"),
    couponRate = json.optNullableInvestmentString("couponRate"),
    maturityDate = json.optNullableInvestmentString("maturityDate"),
    taxAccountType = TaxAccountType.fromApi(json.optString("taxAccountType", "brokerage")),
    holdingStartedAt = json.optNullableInvestmentString("holdingStartedAt"),
    estimatedFeeRate = json.optNullableInvestmentString("estimatedFeeRate"),
)

private fun BucketAdjustment.toJson() = JSONObject()
    .put("riskBucket", riskBucket.apiValue)
    .put("addAmount", addAmount)
    .put("reduceAmount", reduceAmount)
    .put("currentPercent", currentPercent)
    .put("projectedPercent", projectedPercent)
    .put("targetPercent", targetPercent)
    .put("withinTolerance", withinTolerance)

private fun RecommendationAction.toJson() = JSONObject()
    .put("instrumentName", instrumentName).putNullable("ticker", ticker).putNullable("isin", isin)
    .put("riskBucket", riskBucket.apiValue).put("action", action)
    .put("currentPercent", currentPercent).put("targetPercent", targetPercent).put("amount", amount)
    .put("priority", priority).put("rationale", rationale).put("risks", risks)

private fun RecommendationSource.toJson() = JSONObject()
    .put("title", title).put("url", url).put("publisher", publisher)
    .putNullable("publishedAt", publishedAt).put("fetchedAt", fetchedAt).put("trustTier", trustTier)

internal fun BrokerageAccountProfile.toJson() = JSONObject()
    .put("id", id)
    .put("brokerage", brokerage.apiValue)
    .put("userLabel", userLabel)
    .put("accountType", accountType.apiValue)

private fun JSONObject.putNullable(name: String, value: Any?): JSONObject = put(name, value ?: JSONObject.NULL)
private fun JSONObject.dataObjectForInvestment(): JSONObject = optJSONObject("data") ?: this
private fun JSONObject.optNullableInvestmentString(name: String): String? =
    if (!has(name) || isNull(name)) null else optString(name).takeIf { it.isNotBlank() && it != "null" }
private fun JSONArray?.objects(): List<JSONObject> = if (this == null) emptyList() else (0 until length()).mapNotNull(::optJSONObject)
private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).mapNotNull { optString(it).takeIf(String::isNotBlank) }
private fun JSONObject?.toStringMap(): Map<String, String> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { key -> opt(key)?.toString().orEmpty() }
}
