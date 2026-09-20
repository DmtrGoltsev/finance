package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_investment_recommendations",
    indices = [
        Index(value = ["userId", "jobId"], unique = true),
        Index(value = ["userId", "updatedAtEpochMillis"]),
    ],
)
data class LocalInvestmentRecommendationEntity(
    @PrimaryKey val cacheKey: String,
    val userId: String,
    val jobId: String,
    val status: String,
    val jobJson: String,
    val reportJson: String?,
    val updatedAtEpochMillis: Long,
)
