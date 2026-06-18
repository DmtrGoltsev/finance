package com.finance.mvp.local

import androidx.room.Entity

@Entity(
    tableName = "sync_state",
    primaryKeys = ["userId", "deviceId"],
)
data class SyncStateEntity(
    val userId: String,
    val deviceId: String,
    val serverCursor: Long,
    val lastSuccessfulSyncAt: String?,
    val updatedAtEpochMillis: Long,
)
