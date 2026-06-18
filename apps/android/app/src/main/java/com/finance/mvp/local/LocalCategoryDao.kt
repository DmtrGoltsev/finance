package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalCategoryDao {
    @Upsert
    suspend fun upsert(category: LocalCategoryEntity)

    @Query("SELECT * FROM local_categories WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalCategoryEntity?

    @Query("SELECT * FROM local_categories WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalCategoryEntity?

    @Query(
        """
        SELECT * FROM local_categories
        WHERE userId = :userId
        ORDER BY categoryType ASC, name COLLATE NOCASE ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForUser(userId: String): List<LocalCategoryEntity>

    @Query("DELETE FROM local_categories WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
