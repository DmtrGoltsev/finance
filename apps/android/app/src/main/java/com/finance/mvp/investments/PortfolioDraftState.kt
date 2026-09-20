package com.finance.mvp.investments

import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.PortfolioPosition
import com.finance.mvp.api.parsePortfolioPositionForCache
import com.finance.mvp.api.toInputJson
import org.json.JSONArray
import org.json.JSONObject

data class PortfolioDraftState(
    val importId: String,
    val brokerage: Brokerage,
    val screenshotCount: Int,
    val positions: List<PortfolioPosition>,
    val freeCash: String = "0",
    val monthlyContribution: String = "0",
    val createdAtEpochMillis: Long,
)

internal fun PortfolioDraftState.toJson(): String = JSONObject()
    .put("importId", importId)
    .put("brokerage", brokerage.apiValue)
    .put("screenshotCount", screenshotCount)
    .put("positions", JSONArray().apply { positions.forEach { put(it.toInputJson()) } })
    .put("freeCash", freeCash)
    .put("monthlyContribution", monthlyContribution)
    .put("createdAtEpochMillis", createdAtEpochMillis)
    .toString()

internal fun portfolioDraftFromJson(payload: String): PortfolioDraftState = JSONObject(payload).let { json ->
    PortfolioDraftState(
        importId = json.getString("importId"),
        brokerage = Brokerage.fromApi(json.getString("brokerage")),
        screenshotCount = json.getInt("screenshotCount"),
        positions = json.optJSONArray("positions")?.let { array ->
            (0 until array.length()).mapNotNull(array::optJSONObject).map(::parsePortfolioPositionForCache)
        }.orEmpty(),
        freeCash = json.optString("freeCash", "0"),
        monthlyContribution = json.optString("monthlyContribution", "0"),
        createdAtEpochMillis = json.getLong("createdAtEpochMillis"),
    )
}
