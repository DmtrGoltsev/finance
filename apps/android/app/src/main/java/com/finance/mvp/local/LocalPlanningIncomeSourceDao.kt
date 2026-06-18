package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalPlanningIncomeSourceDao {
    @Upsert
    suspend fun upsert(source: LocalPlanningIncomeSourceEntity)

    @Query("SELECT * FROM local_planning_income_sources WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalPlanningIncomeSourceEntity?

    @Query("SELECT * FROM local_planning_income_sources WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalPlanningIncomeSourceEntity?

    @Query(
        """
        SELECT * FROM local_planning_income_sources
        WHERE userId = :userId AND planLocalId = :planLocalId AND recordStatus != 'deleted'
        ORDER BY dayOfMonth ASC, source COLLATE NOCASE ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForPlan(userId: String, planLocalId: String): List<LocalPlanningIncomeSourceEntity>

    @Query(
        """
        SELECT * FROM local_planning_income_sources
        WHERE userId = :userId AND planLocalId = :planLocalId
        ORDER BY dayOfMonth ASC, source COLLATE NOCASE ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForPlanIncludingDeleted(userId: String, planLocalId: String): List<LocalPlanningIncomeSourceEntity>

    @Query(
        """
        SELECT * FROM local_planning_income_sources
        WHERE userId = :userId
        ORDER BY updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForUser(userId: String): List<LocalPlanningIncomeSourceEntity>

    @Query("DELETE FROM local_planning_income_sources WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
