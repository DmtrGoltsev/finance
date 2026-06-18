package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_asset_categories",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "recordStatus"]),
        Index(value = ["userId", "isInvestment"]),
        Index(value = ["userId", "name"]),
    ],
)
data class LocalAssetCategoryEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val name: String,
    val scopeType: String,
    val householdId: String?,
    val ownerUserId: String?,
    val currency: String,
    val manualAmount: String,
    val isInvestment: Boolean,
    val assetType: String,
    val iconKey: String,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
