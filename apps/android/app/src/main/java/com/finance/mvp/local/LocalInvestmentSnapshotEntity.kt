package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_investment_snapshots",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "brokerage", "observedAtEpochMillis"]),
    ],
)
data class LocalInvestmentSnapshotEntity(
    @PrimaryKey val cacheKey: String,
    val userId: String,
    val serverId: String,
    val brokerage: String,
    val observedAtEpochMillis: Long,
    val payloadJson: String,
    val cachedAtEpochMillis: Long,
)
