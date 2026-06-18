package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "pending_mutations",
    indices = [
        Index(value = ["userId", "deviceId", "status", "createdAtEpochMillis"]),
        Index(value = ["userId", "entityType", "entityId"]),
    ],
)
data class PendingMutationEntity(
    @PrimaryKey val clientMutationId: String,
    val userId: String,
    val deviceId: String,
    val entityType: String,
    val entityId: String,
    val operation: String,
    val baseVersion: Int?,
    val payloadJson: String?,
    val status: String,
    val attempts: Int,
    val lastError: String?,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val lastAttemptAtEpochMillis: Long? = null,
)
