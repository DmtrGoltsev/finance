package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalAssetCategoryDao {
    @Upsert
    suspend fun upsert(assetCategory: LocalAssetCategoryEntity)

    @Query("SELECT * FROM local_asset_categories WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalAssetCategoryEntity?

    @Query("SELECT * FROM local_asset_categories WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalAssetCategoryEntity?

    @Query(
        """
        SELECT * FROM local_asset_categories
        WHERE userId = :userId
        ORDER BY isInvestment DESC, name COLLATE NOCASE ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForUser(userId: String): List<LocalAssetCategoryEntity>

    @Query("DELETE FROM local_asset_categories WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
