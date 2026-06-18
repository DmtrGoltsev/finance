package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_categories",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "recordStatus"]),
        Index(value = ["userId", "categoryType"]),
        Index(value = ["userId", "name"]),
    ],
)
data class LocalCategoryEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val name: String,
    val categoryType: String,
    val scope: String,
    val householdId: String?,
    val iconKey: String,
    val color: String,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
