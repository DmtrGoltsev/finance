package com.finance.mvp.local

import android.content.Context
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class FinanceDatabaseMigrationV4Test {
    @Test
    fun migration3To4PreservesExistingDataAndCreatesInvestmentCache() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val helper = FrameworkSQLiteOpenHelperFactory().create(
            SupportSQLiteOpenHelper.Configuration.builder(context)
                .name(null)
                .callback(object : SupportSQLiteOpenHelper.Callback(3) {
                    override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                        db.execSQL("CREATE TABLE legacy_marker (id INTEGER NOT NULL PRIMARY KEY, value TEXT NOT NULL)")
                        db.execSQL("INSERT INTO legacy_marker(id, value) VALUES (1, 'kept')")
                    }
                    override fun onUpgrade(db: androidx.sqlite.db.SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
                })
                .build(),
        )
        val db = helper.writableDatabase

        FinanceLocalDatabase.MIGRATION_3_4.migrate(db)

        db.query("SELECT value FROM legacy_marker WHERE id = 1").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals("kept", cursor.getString(0))
        }
        db.execSQL("INSERT INTO local_investment_snapshots VALUES ('u:s','u','s','sinara',1,'{}',2)")
        db.query("SELECT COUNT(*) FROM local_investment_snapshots").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals(1, cursor.getInt(0))
        }
        db.execSQL("INSERT INTO local_investment_recommendations VALUES ('u:j','u','j','queued','{}',NULL,3)")
        helper.close()
    }

    @Test
    fun migration4To5PreservesInvestmentCacheAndCreatesStructuredDraftStore() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val helper = FrameworkSQLiteOpenHelperFactory().create(
            SupportSQLiteOpenHelper.Configuration.builder(context)
                .name(null)
                .callback(object : SupportSQLiteOpenHelper.Callback(4) {
                    override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                        FinanceLocalDatabase.MIGRATION_3_4.migrate(db)
                        db.execSQL("INSERT INTO local_investment_snapshots VALUES ('u:s','u','s','finam',1,'{}',2)")
                    }
                    override fun onUpgrade(db: androidx.sqlite.db.SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
                })
                .build(),
        )
        val db = helper.writableDatabase

        FinanceLocalDatabase.MIGRATION_4_5.migrate(db)

        db.query("SELECT COUNT(*) FROM local_investment_snapshots").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals(1, cursor.getInt(0))
        }
        db.execSQL("INSERT INTO local_investment_drafts VALUES ('u:i','u','i','{}',3)")
        db.query("SELECT COUNT(*) FROM local_investment_drafts").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals(1, cursor.getInt(0))
        }
        helper.close()
    }

    @Test
    fun migration5To6PreservesRecommendationsAndAddsHistoryMetadata() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val helper = FrameworkSQLiteOpenHelperFactory().create(
            SupportSQLiteOpenHelper.Configuration.builder(context)
                .name(null)
                .callback(object : SupportSQLiteOpenHelper.Callback(5) {
                    override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                        FinanceLocalDatabase.MIGRATION_3_4.migrate(db)
                        FinanceLocalDatabase.MIGRATION_4_5.migrate(db)
                        db.execSQL("INSERT INTO local_investment_recommendations VALUES ('u:j','u','j','ready','{}',NULL,3)")
                    }
                    override fun onUpgrade(db: androidx.sqlite.db.SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
                })
                .build(),
        )
        val db = helper.writableDatabase

        FinanceLocalDatabase.MIGRATION_5_6.migrate(db)

        db.execSQL(
            "UPDATE local_investment_recommendations SET accountProfilesJson='[]', reportSummary='summary', reportPath='/report' WHERE jobId='j'",
        )
        db.query("SELECT reportSummary, reportPath FROM local_investment_recommendations WHERE jobId='j'").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals("summary", cursor.getString(0))
            assertEquals("/report", cursor.getString(1))
        }
        helper.close()
    }
}
