package com.finance.mvp.sync

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.Configuration
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.testing.WorkManagerTestInitHelper
import com.finance.mvp.session.InMemorySecureTokenStore
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class TransactionSyncWorkerTest {
    @Test
    fun delayedWorkerForUserASkipsBeforeAnyApiOrDatabaseSideEffectAfterLoginB() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-b", "refresh-b", "session-b", "user-b")
        var apiCalls = 0
        var databaseWrites = 0

        val result = runTransactionSyncIfAuthenticated("user-a", tokenStore) {
            apiCalls += 1
            databaseWrites += 1
            "unexpected"
        }

        assertTrue(result is AuthenticatedSyncRun.Skipped)
        assertEquals(0, apiCalls)
        assertEquals(0, databaseWrites)
    }

    @Test
    fun legacySessionWithoutUserIdFailsClosedForBackgroundSync() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveAccessToken("legacy-access")
        var executions = 0

        val result = runTransactionSyncIfAuthenticated("user-a", tokenStore) {
            executions += 1
        }

        assertTrue(result is AuthenticatedSyncRun.Skipped)
        assertEquals(0, executions)
    }

    @Test
    fun currentAuthenticatedUserSyncExecutesNormally() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-a", "refresh-a", "session-a", "user-a")
        var executions = 0

        val result = runTransactionSyncIfAuthenticated("user-a", tokenStore) {
            executions += 1
            "completed"
        }

        assertTrue(result is AuthenticatedSyncRun.Executed)
        assertEquals("completed", (result as AuthenticatedSyncRun.Executed).value)
        assertEquals(1, executions)
    }

    @Test
    fun cancelStopsPerUserUniqueWork() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        WorkManagerTestInitHelper.initializeTestWorkManager(
            context,
            Configuration.Builder().build(),
        )
        val workManager = WorkManager.getInstance(context)

        TransactionSyncWorker.enqueue(context, "user-a")
        val workName = TransactionSyncWorker.uniqueWorkName("user-a")
        val enqueued = workManager.getWorkInfosForUniqueWork(workName).get(5, TimeUnit.SECONDS)
        assertEquals(1, enqueued.size)

        TransactionSyncWorker.cancel(context, "user-a")
        val cancelled = workManager.getWorkInfosForUniqueWork(workName).get(5, TimeUnit.SECONDS)

        assertEquals(WorkInfo.State.CANCELLED, cancelled.single().state)
    }
}
