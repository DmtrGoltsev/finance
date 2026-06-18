package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

@Dao
interface LocalPlanningAllocationDao {
    @Upsert
    suspend fun upsert(allocation: LocalPlanningAllocationEntity)

    @Query("SELECT * FROM local_planning_allocations WHERE userId = :userId AND localId = :localId LIMIT 1")
    suspend fun findByLocalId(userId: String, localId: String): LocalPlanningAllocationEntity?

    @Query("SELECT * FROM local_planning_allocations WHERE userId = :userId AND serverId = :serverId LIMIT 1")
    suspend fun findByServerId(userId: String, serverId: String): LocalPlanningAllocationEntity?

    @Query(
        """
        SELECT * FROM local_planning_allocations
        WHERE userId = :userId AND planLocalId = :planLocalId AND recordStatus != 'deleted'
        ORDER BY targetType ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForPlan(userId: String, planLocalId: String): List<LocalPlanningAllocationEntity>

    @Query(
        """
        SELECT * FROM local_planning_allocations
        WHERE userId = :userId AND planLocalId = :planLocalId
        ORDER BY targetType ASC, updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForPlanIncludingDeleted(userId: String, planLocalId: String): List<LocalPlanningAllocationEntity>

    @Query(
        """
        SELECT * FROM local_planning_allocations
        WHERE userId = :userId
        ORDER BY updatedAtEpochMillis DESC
        """,
    )
    suspend fun listForUser(userId: String): List<LocalPlanningAllocationEntity>

    @Query("DELETE FROM local_planning_allocations WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
