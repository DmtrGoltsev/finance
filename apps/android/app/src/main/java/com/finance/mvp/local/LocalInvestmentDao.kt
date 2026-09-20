package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalInvestmentDao {
    @Upsert
    suspend fun upsertSnapshot(snapshot: LocalInvestmentSnapshotEntity)

    @Upsert
    suspend fun upsertRecommendation(recommendation: LocalInvestmentRecommendationEntity)

    @Query("SELECT * FROM local_investment_snapshots WHERE userId = :userId ORDER BY observedAtEpochMillis DESC")
    suspend fun snapshots(userId: String): List<LocalInvestmentSnapshotEntity>

    @Query("SELECT * FROM local_investment_recommendations WHERE userId = :userId ORDER BY updatedAtEpochMillis DESC")
    suspend fun recommendations(userId: String): List<LocalInvestmentRecommendationEntity>

    @Query("SELECT * FROM local_investment_recommendations WHERE userId = :userId AND jobId = :jobId LIMIT 1")
    suspend fun recommendation(userId: String, jobId: String): LocalInvestmentRecommendationEntity?

    @Query("DELETE FROM local_investment_snapshots WHERE userId = :userId")
    suspend fun deleteSnapshots(userId: String)

    @Query("DELETE FROM local_investment_recommendations WHERE userId = :userId")
    suspend fun deleteRecommendations(userId: String)
}
