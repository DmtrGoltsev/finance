package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_planning_income_sources",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "planLocalId", "recordStatus"]),
        Index(value = ["userId", "planServerId"]),
        Index(value = ["userId", "syncStatus"]),
    ],
)
data class LocalPlanningIncomeSourceEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val planLocalId: String,
    val planServerId: String?,
    val amount: String,
    val source: String,
    val description: String?,
    val dayOfMonth: Int?,
    val confirmed: Boolean,
    val effectiveDate: String?,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
