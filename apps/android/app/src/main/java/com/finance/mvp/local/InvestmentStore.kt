package com.finance.mvp.local

import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationJob
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.parsePortfolioSnapshot
import com.finance.mvp.api.parseRecommendationJob
import com.finance.mvp.api.parseRecommendationReport
import com.finance.mvp.api.toCacheJson
import java.time.Instant
import org.json.JSONObject

data class CachedInvestmentRecommendation(
    val job: RecommendationJob,
    val report: RecommendationReport?,
)

class InvestmentStore(
    private val database: FinanceLocalDatabase,
    private val nowEpochMillis: () -> Long = { System.currentTimeMillis() },
) {
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
                )
            }.getOrNull()
        }

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
                updatedAtEpochMillis = nowEpochMillis(),
            ),
        )
    }
}
