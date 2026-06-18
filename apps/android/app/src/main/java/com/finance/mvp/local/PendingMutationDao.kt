package com.finance.mvp.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PendingMutationDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertIgnoringConflict(mutation: PendingMutationEntity): Long

    @Query("SELECT * FROM pending_mutations WHERE clientMutationId = :clientMutationId LIMIT 1")
    suspend fun findByClientMutationId(clientMutationId: String): PendingMutationEntity?

    @Query(
        """
        SELECT * FROM pending_mutations
        WHERE userId = :userId AND status IN (:statuses)
        ORDER BY createdAtEpochMillis ASC, clientMutationId ASC
        LIMIT :limit
        """,
    )
    suspend fun pendingForUser(
        userId: String,
        statuses: List<String> = listOf("queued", "retry"),
        limit: Int = 100,
    ): List<PendingMutationEntity>

    @Query(
        """
        SELECT * FROM pending_mutations
        WHERE userId = :userId AND status IN (:statuses)
        ORDER BY updatedAtEpochMillis DESC, createdAtEpochMillis DESC, clientMutationId DESC
        LIMIT :limit
        """,
    )
    suspend fun syncIssuesForUser(
        userId: String,
        statuses: List<String> = listOf("failed", "rejected"),
        limit: Int = 100,
    ): List<PendingMutationEntity>

    @Query(
        """
        SELECT COUNT(*) FROM pending_mutations
        WHERE userId = :userId AND status IN (:statuses)
        """,
    )
    suspend fun countForUser(
        userId: String,
        statuses: List<String>,
    ): Int

    @Query(
        """
        SELECT COUNT(*) FROM pending_mutations
        WHERE userId = :userId AND status IN (:statuses) AND entityType IN (:entityTypes)
        """,
    )
    suspend fun countForUserAndEntityTypes(
        userId: String,
        statuses: List<String>,
        entityTypes: List<String>,
    ): Int

    @Query(
        """
        UPDATE pending_mutations
        SET status = :status,
            attempts = :attempts,
            lastError = :lastError,
            updatedAtEpochMillis = :updatedAtEpochMillis,
            lastAttemptAtEpochMillis = :lastAttemptAtEpochMillis
        WHERE clientMutationId = :clientMutationId
        """,
    )
    suspend fun updateStatus(
        clientMutationId: String,
        status: String,
        attempts: Int,
        lastError: String?,
        updatedAtEpochMillis: Long,
        lastAttemptAtEpochMillis: Long?,
    )

    @Query(
        """
        UPDATE pending_mutations
        SET status = :nextStatus,
            updatedAtEpochMillis = :updatedAtEpochMillis
        WHERE userId = :userId AND status IN (:statuses)
        """,
    )
    suspend fun updateStatusesForUser(
        userId: String,
        statuses: List<String>,
        nextStatus: String,
        updatedAtEpochMillis: Long,
    ): Int

    @Query("DELETE FROM pending_mutations WHERE clientMutationId IN (:clientMutationIds)")
    suspend fun deleteByClientMutationIds(clientMutationIds: List<String>)

    @Query("DELETE FROM pending_mutations WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
