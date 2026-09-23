package com.finance.mvp.local

import com.finance.mvp.api.BrokerageAccountProfile
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.parsePortfolioSnapshot
import com.finance.mvp.api.parseBrokerageAccountProfile
import com.finance.mvp.api.parseRecommendationJob
import com.finance.mvp.api.parseRecommendationReport
import com.finance.mvp.api.toCacheJson
import com.finance.mvp.api.toJson as toApiJson
import com.finance.mvp.investments.PortfolioDraftState
import com.finance.mvp.investments.portfolioDraftFromJson
import com.finance.mvp.investments.toJson
import java.time.Instant
import org.json.JSONArray
import org.json.JSONObject

data class CachedInvestmentRecommendation(
    val job: RecommendationJob,
    val report: RecommendationReport?,
    val accountProfiles: List<BrokerageAccountProfile> = emptyList(),
    val reportSummary: String? = null,
    val reportPath: String? = null,
)

class InvestmentStore(
    private val database: FinanceLocalDatabase,
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
) {
    suspend fun draft(userId: String): PortfolioDraftState? =
        database.localInvestmentDao().latestDraft(userId)?.let { entity ->
            runCatching { portfolioDraftFromJson(entity.payloadJson) }.getOrNull()
        }

    suspend fun cacheDraft(userId: String, draft: PortfolioDraftState) {
        database.localInvestmentDao().upsertDraft(
            LocalInvestmentDraftEntity(
                cacheKey = "$userId:${draft.importId}",
                userId = userId,
                importId = draft.importId,
                payloadJson = draft.toJson(),
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }

    suspend fun deleteDraft(userId: String, importId: String) {
        database.localInvestmentDao().deleteDraft(userId, importId)
    }
    suspend fun snapshots(userId: String): List<PortfolioSnapshot> =
        database.localInvestmentDao().snapshots(userId).mapNotNull { entity ->
            runCatching { parsePortfolioSnapshot(JSONObject(entity.payloadJson)) }.getOrNull()
        }

    suspend fun recommendations(userId: String): List<CachedInvestmentRecommendation> =
        database.localInvestmentDao().recommendations(userId).mapNotNull { entity ->
            runCatching {
                CachedInvestmentRecommendation(
                    job = parseRecommendationJob(JSONObject(entity.jobJson)),
                    report = entity.reportJson?.let { parseRecommendationReport(JSONObject(it)) },
                    accountProfiles = entity.accountProfilesJson?.let { payload ->
                        val array = JSONArray(payload)
                        (0 until array.length()).mapNotNull(array::optJSONObject).map(::parseBrokerageAccountProfile)
                    }.orEmpty(),
                    reportSummary = entity.reportSummary,
                    reportPath = entity.reportPath,
                )
            }.getOrNull()
        }.sortedByDescending { it.job.createdAt }

    suspend fun cacheSnapshots(userId: String, snapshots: List<PortfolioSnapshot>) {
        snapshots.forEach { snapshot ->
            database.localInvestmentDao().upsertSnapshot(
                LocalInvestmentSnapshotEntity(
                    cacheKey = "$userId:${snapshot.id}",
                    userId = userId,
                    serverId = snapshot.id,
                    brokerage = snapshot.brokerage.apiValue,
                    observedAtEpochMillis = runCatching { Instant.parse(snapshot.observedAt).toEpochMilli() }.getOrDefault(0L),
                    payloadJson = snapshot.toCacheJson(),
                    cachedAtEpochMillis = nowEpochMillis(),
                ),
            )
        }
    }

    suspend fun cacheRecommendation(
        userId: String,
        job: RecommendationJob,
        report: RecommendationReport? = null,
        accountProfiles: List<BrokerageAccountProfile> = emptyList(),
        reportSummary: String? = null,
        reportPath: String? = null,
    ) {
        val existing = database.localInvestmentDao().recommendation(userId, job.id)
        database.localInvestmentDao().upsertRecommendation(
            LocalInvestmentRecommendationEntity(
                cacheKey = "$userId:${job.id}",
                userId = userId,
                jobId = job.id,
                status = if (report?.isStale == true) "stale" else job.status.apiValue,
                jobJson = job.toCacheJson(),
                reportJson = report?.toCacheJson() ?: existing?.reportJson,
                accountProfilesJson = if (accountProfiles.isNotEmpty()) {
                    JSONArray().apply { accountProfiles.forEach { put(it.toApiJson()) } }.toString()
                } else {
                    existing?.accountProfilesJson
                },
                reportSummary = reportSummary ?: report?.summary ?: existing?.reportSummary,
                reportPath = reportPath ?: existing?.reportPath,
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }
}
