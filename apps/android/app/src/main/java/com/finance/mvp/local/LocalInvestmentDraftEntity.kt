package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_investment_drafts",
    indices = [Index(value = ["userId", "importId"], unique = true)],
)
data class LocalInvestmentDraftEntity(
    @PrimaryKey val cacheKey: String,
    val userId: String,
    val importId: String,
    val payloadJson: String,
    val updatedAtEpochMillis: Long,
)
