package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_accounts",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "recordStatus"]),
        Index(value = ["userId", "name"]),
    ],
)
data class LocalAccountEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val name: String,
    val accountType: String,
    val ownershipType: String,
    val currency: String,
    val currentBalance: String,
    val householdId: String?,
    val assetCategoryId: String?,
    val isPaymentAccount: Boolean,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
