package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface SyncStateDao {
    @Upsert
    suspend fun upsert(state: SyncStateEntity)

    @Query("SELECT * FROM sync_state WHERE userId = :userId AND deviceId = :deviceId LIMIT 1")
    suspend fun find(userId: String, deviceId: String): SyncStateEntity?

    @Query("DELETE FROM sync_state WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
