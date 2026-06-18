package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_planning_plans",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "scope", "month", "householdId"]),
        Index(value = ["userId", "recordStatus"]),
        Index(value = ["userId", "syncStatus"]),
    ],
)
data class LocalPlanningPlanEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val scope: String,
    val month: String,
    val currency: String,
    val householdId: String?,
    val totalPlannedIncome: String,
    val previousMonthSurplus: String,
    val allocatedTotal: String,
    val remainingAmount: String,
    val overallocatedAmount: String,
    val isUnderallocated: Boolean,
    val isOverallocated: Boolean,
    val status: String?,
    val progressStatus: String?,
    val progressPercent: String?,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
