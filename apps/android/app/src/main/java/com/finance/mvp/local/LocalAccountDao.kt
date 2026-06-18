package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalAccountDao {
    @Upsert
    suspend fun upsert(account: LocalAccountEntity)

    @Query("SELECT * FROM local_accounts WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalAccountEntity?

    @Query("SELECT * FROM local_accounts WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalAccountEntity?

    @Query(
        """
        SELECT * FROM local_accounts
        WHERE userId = :userId
        ORDER BY name COLLATE NOCASE ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForUser(userId: String): List<LocalAccountEntity>

    @Query("DELETE FROM local_accounts WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
