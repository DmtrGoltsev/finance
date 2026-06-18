package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_planning_allocations",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "planLocalId", "recordStatus"]),
        Index(value = ["userId", "planServerId"]),
        Index(value = ["userId", "syncStatus"]),
        Index(value = ["userId", "targetType", "targetId"]),
    ],
)
data class LocalPlanningAllocationEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val planLocalId: String,
    val planServerId: String?,
    val targetType: String,
    val targetId: String?,
    val targetSnapshot: String?,
    val requiresAttention: Boolean,
    val attentionReason: String?,
    val comment: String?,
    val allocationMode: String,
    val allocationValue: String,
    val calculatedAmount: String,
    val recurrenceType: String?,
    val isSavingsGoal: Boolean,
    val goalTargetAmount: String?,
    val goalDueMonth: String?,
    val goalMonthlyAmount: String?,
    val actualAmount: String?,
    val varianceAmount: String?,
    val progressPercent: String?,
    val progressStatus: String?,
    val status: String?,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
