package com.finance.mvp.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "local_transactions",
    indices = [
        Index(value = ["userId", "serverId"], unique = true),
        Index(value = ["userId", "syncStatus"]),
        Index(value = ["userId", "transactionDate"]),
    ],
)
data class LocalTransactionEntity(
    @PrimaryKey val localId: String,
    val userId: String,
    val serverId: String?,
    val transactionType: String,
    val amount: String,
    val currency: String,
    val accountId: String,
    val categoryId: String?,
    val counterpartyAccountId: String?,
    val transactionDate: String,
    val occurredAt: String?,
    val note: String?,
    val version: Int?,
    val syncStatus: String,
    val recordStatus: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val deletedAtEpochMillis: Long? = null,
)
