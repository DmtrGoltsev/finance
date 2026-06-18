package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalPlanningPlanDao {
    @Upsert
    suspend fun upsert(plan: LocalPlanningPlanEntity)

    @Query("SELECT * FROM local_planning_plans WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalPlanningPlanEntity?

    @Query("SELECT * FROM local_planning_plans WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalPlanningPlanEntity?

    @Query(
        """
        SELECT * FROM local_planning_plans
        WHERE userId = :userId
          AND scope = :scope
          AND month = :month
          AND ((:householdId IS NULL AND householdId IS NULL) OR householdId = :householdId)
          AND recordStatus != 'deleted'
        ORDER BY updatedAtEpochMillis DESC
        LIMIT 1
        """,
    )
    suspend fun findForScopeMonth(
        userId: String,
        scope: String,
        month: String,
        householdId: String?,
    ): LocalPlanningPlanEntity?

    @Query(
        """
        SELECT * FROM local_planning_plans
        WHERE userId = :userId
          AND scope = :scope
          AND ((:householdId IS NULL AND householdId IS NULL) OR householdId = :householdId)
          AND recordStatus != 'deleted'
        ORDER BY month DESC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun historyForScope(userId: String, scope: String, householdId: String?): List<LocalPlanningPlanEntity>

    @Query(
        """
        SELECT * FROM local_planning_plans
        WHERE userId = :userId
        ORDER BY month DESC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForUser(userId: String): List<LocalPlanningPlanEntity>

    @Query("DELETE FROM local_planning_plans WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
