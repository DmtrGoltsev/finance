package com.finance.mvp.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        LocalTransactionEntity::class,
        LocalAccountEntity::class,
        LocalCategoryEntity::class,
        LocalAssetCategoryEntity::class,
        LocalPlanningPlanEntity::class,
        LocalPlanningIncomeSourceEntity::class,
        LocalPlanningAllocationEntity::class,
        PendingMutationEntity::class,
        SyncStateEntity::class,
        LocalInvestmentSnapshotEntity::class,
        LocalInvestmentRecommendationEntity::class,
        LocalInvestmentDraftEntity::class,
    ],
    version = 6,
    exportSchema = false,
)
abstract class FinanceLocalDatabase : RoomDatabase() {
    abstract fun localTransactionDao(): LocalTransactionDao
    abstract fun localAccountDao(): LocalAccountDao
    abstract fun localCategoryDao(): LocalCategoryDao
    abstract fun localAssetCategoryDao(): LocalAssetCategoryDao
    abstract fun localPlanningPlanDao(): LocalPlanningPlanDao
    abstract fun localPlanningIncomeSourceDao(): LocalPlanningIncomeSourceDao
    abstract fun localPlanningAllocationDao(): LocalPlanningAllocationDao
    abstract fun pendingMutationDao(): PendingMutationDao
    abstract fun syncStateDao(): SyncStateDao
    abstract fun localInvestmentDao(): LocalInvestmentDao

    companion object {
        private const val DATABASE_NAME = "finance_local.db"

        @Volatile
        private var instance: FinanceLocalDatabase? = null

        fun getInstance(context: Context): FinanceLocalDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    FinanceLocalDatabase::class.java,
                    DATABASE_NAME,
                ).addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6).build().also { instance = it }
            }
        }

        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_accounts (
                        localId TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT,
                        name TEXT NOT NULL,
                        accountType TEXT NOT NULL,
                        ownershipType TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        currentBalance TEXT NOT NULL,
                        householdId TEXT,
                        assetCategoryId TEXT,
                        isPaymentAccount INTEGER NOT NULL,
                        version INTEGER,
                        syncStatus TEXT NOT NULL,
                        recordStatus TEXT NOT NULL,
                        createdAtEpochMillis INTEGER NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL,
                        deletedAtEpochMillis INTEGER
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_accounts_userId_serverId ON local_accounts(userId, serverId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_accounts_userId_recordStatus ON local_accounts(userId, recordStatus)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_accounts_userId_name ON local_accounts(userId, name)")

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_categories (
                        localId TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT,
                        name TEXT NOT NULL,
                        categoryType TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        householdId TEXT,
                        iconKey TEXT NOT NULL,
                        color TEXT NOT NULL,
                        version INTEGER,
                        syncStatus TEXT NOT NULL,
                        recordStatus TEXT NOT NULL,
                        createdAtEpochMillis INTEGER NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL,
                        deletedAtEpochMillis INTEGER
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_categories_userId_serverId ON local_categories(userId, serverId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_categories_userId_recordStatus ON local_categories(userId, recordStatus)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_categories_userId_categoryType ON local_categories(userId, categoryType)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_categories_userId_name ON local_categories(userId, name)")

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_asset_categories (
                        localId TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT,
                        name TEXT NOT NULL,
                        scopeType TEXT NOT NULL,
                        householdId TEXT,
                        ownerUserId TEXT,
                        currency TEXT NOT NULL,
                        manualAmount TEXT NOT NULL,
                        isInvestment INTEGER NOT NULL,
                        assetType TEXT NOT NULL,
                        iconKey TEXT NOT NULL,
                        version INTEGER,
                        syncStatus TEXT NOT NULL,
                        recordStatus TEXT NOT NULL,
                        createdAtEpochMillis INTEGER NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL,
                        deletedAtEpochMillis INTEGER
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE UNIQUE INDEX IF NOT EXISTS index_local_asset_categories_userId_serverId ON local_asset_categories(userId, serverId)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_local_asset_categories_userId_recordStatus ON local_asset_categories(userId, recordStatus)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_local_asset_categories_userId_isInvestment ON local_asset_categories(userId, isInvestment)",
                )
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_asset_categories_userId_name ON local_asset_categories(userId, name)")
            }
        }

        private val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_planning_plans (
                        localId TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT,
                        scope TEXT NOT NULL,
                        month TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        householdId TEXT,
                        totalPlannedIncome TEXT NOT NULL,
                        previousMonthSurplus TEXT NOT NULL,
                        allocatedTotal TEXT NOT NULL,
                        remainingAmount TEXT NOT NULL,
                        overallocatedAmount TEXT NOT NULL,
                        isUnderallocated INTEGER NOT NULL,
                        isOverallocated INTEGER NOT NULL,
                        status TEXT,
                        progressStatus TEXT,
                        progressPercent TEXT,
                        version INTEGER,
                        syncStatus TEXT NOT NULL,
                        recordStatus TEXT NOT NULL,
                        createdAtEpochMillis INTEGER NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL,
                        deletedAtEpochMillis INTEGER
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_planning_plans_userId_serverId ON local_planning_plans(userId, serverId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_plans_userId_scope_month_householdId ON local_planning_plans(userId, scope, month, householdId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_plans_userId_recordStatus ON local_planning_plans(userId, recordStatus)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_plans_userId_syncStatus ON local_planning_plans(userId, syncStatus)")

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_planning_income_sources (
                        localId TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT,
                        planLocalId TEXT NOT NULL,
                        planServerId TEXT,
                        amount TEXT NOT NULL,
                        source TEXT NOT NULL,
                        description TEXT,
                        dayOfMonth INTEGER,
                        confirmed INTEGER NOT NULL,
                        effectiveDate TEXT,
                        version INTEGER,
                        syncStatus TEXT NOT NULL,
                        recordStatus TEXT NOT NULL,
                        createdAtEpochMillis INTEGER NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL,
                        deletedAtEpochMillis INTEGER
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_planning_income_sources_userId_serverId ON local_planning_income_sources(userId, serverId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_income_sources_userId_planLocalId_recordStatus ON local_planning_income_sources(userId, planLocalId, recordStatus)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_income_sources_userId_planServerId ON local_planning_income_sources(userId, planServerId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_income_sources_userId_syncStatus ON local_planning_income_sources(userId, syncStatus)")

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_planning_allocations (
                        localId TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT,
                        planLocalId TEXT NOT NULL,
                        planServerId TEXT,
                        targetType TEXT NOT NULL,
                        targetId TEXT,
                        targetSnapshot TEXT,
                        requiresAttention INTEGER NOT NULL,
                        attentionReason TEXT,
                        comment TEXT,
                        allocationMode TEXT NOT NULL,
                        allocationValue TEXT NOT NULL,
                        calculatedAmount TEXT NOT NULL,
                        recurrenceType TEXT,
                        isSavingsGoal INTEGER NOT NULL,
                        goalTargetAmount TEXT,
                        goalDueMonth TEXT,
                        goalMonthlyAmount TEXT,
                        actualAmount TEXT,
                        varianceAmount TEXT,
                        progressPercent TEXT,
                        progressStatus TEXT,
                        status TEXT,
                        version INTEGER,
                        syncStatus TEXT NOT NULL,
                        recordStatus TEXT NOT NULL,
                        createdAtEpochMillis INTEGER NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL,
                        deletedAtEpochMillis INTEGER
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_planning_allocations_userId_serverId ON local_planning_allocations(userId, serverId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_allocations_userId_planLocalId_recordStatus ON local_planning_allocations(userId, planLocalId, recordStatus)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_allocations_userId_planServerId ON local_planning_allocations(userId, planServerId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_allocations_userId_syncStatus ON local_planning_allocations(userId, syncStatus)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_planning_allocations_userId_targetType_targetId ON local_planning_allocations(userId, targetType, targetId)")
            }
        }

        internal val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_investment_snapshots (
                        cacheKey TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        serverId TEXT NOT NULL,
                        brokerage TEXT NOT NULL,
                        observedAtEpochMillis INTEGER NOT NULL,
                        payloadJson TEXT NOT NULL,
                        cachedAtEpochMillis INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_investment_snapshots_userId_serverId ON local_investment_snapshots(userId, serverId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_investment_snapshots_userId_brokerage_observedAtEpochMillis ON local_investment_snapshots(userId, brokerage, observedAtEpochMillis)")
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_investment_recommendations (
                        cacheKey TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        jobId TEXT NOT NULL,
                        status TEXT NOT NULL,
                        jobJson TEXT NOT NULL,
                        reportJson TEXT,
                        updatedAtEpochMillis INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_investment_recommendations_userId_jobId ON local_investment_recommendations(userId, jobId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_local_investment_recommendations_userId_updatedAtEpochMillis ON local_investment_recommendations(userId, updatedAtEpochMillis)")
            }
        }

        internal val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS local_investment_drafts (
                        cacheKey TEXT NOT NULL PRIMARY KEY,
                        userId TEXT NOT NULL,
                        importId TEXT NOT NULL,
                        payloadJson TEXT NOT NULL,
                        updatedAtEpochMillis INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_local_investment_drafts_userId_importId ON local_investment_drafts(userId, importId)")
            }
        }

        internal val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE local_investment_recommendations ADD COLUMN accountProfilesJson TEXT")
                db.execSQL("ALTER TABLE local_investment_recommendations ADD COLUMN reportSummary TEXT")
                db.execSQL("ALTER TABLE local_investment_recommendations ADD COLUMN reportPath TEXT")
            }
        }
    }
}
