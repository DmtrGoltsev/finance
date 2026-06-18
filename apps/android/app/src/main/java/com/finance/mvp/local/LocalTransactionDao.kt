package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalTransactionDao {
    @Upsert
    suspend fun upsert(transaction: LocalTransactionEntity)

    @Query("SELECT * FROM local_transactions WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalTransactionEntity?

    @Query("SELECT * FROM local_transactions WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalTransactionEntity?

    @Query(
        """
        SELECT * FROM local_transactions
        WHERE userId = :userId
        ORDER BY transactionDate DESC, updatedAtEpochMillis DESC
        LIMIT :limit
        """,
    )
    suspend fun latestForUser(userId: String, limit: Int = 100): List<LocalTransactionEntity>

    @Query("DELETE FROM local_transactions WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
