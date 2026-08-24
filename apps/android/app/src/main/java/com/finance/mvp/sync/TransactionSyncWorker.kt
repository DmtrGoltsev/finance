package com.finance.mvp.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.finance.mvp.BuildConfig
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.local.FinanceLocalDatabase
import com.finance.mvp.session.AndroidSecureTokenStore
import com.finance.mvp.session.SecureTokenStore
import java.util.concurrent.TimeUnit

class TransactionSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val userId = inputData.getString(KEY_USER_ID)?.takeIf { it.isNotBlank() }
            ?: return Result.failure()

        val tokenStore = AndroidSecureTokenStore(applicationContext)
        return when (
            val run = runTransactionSyncIfAuthenticated(userId, tokenStore) {
                val apiClient = LiveFinanceApiClient(
                    config = ApiConfig(BuildConfig.FINANCE_API_BASE_URL),
                    tokenStore = tokenStore,
                )
                val manager = SyncManager(
                    database = FinanceLocalDatabase.getInstance(applicationContext),
                    apiClient = FinanceSyncApiClientAdapter(apiClient),
                    deviceIdStore = AndroidDeviceIdStore(applicationContext),
                )
                manager.syncOnce(userId)
            }
        ) {
            AuthenticatedSyncRun.Skipped -> Result.success()
            is AuthenticatedSyncRun.Executed -> when {
                run.value.sessionChanged -> Result.success()
                run.value.push.failed > 0 -> Result.failure()
                run.value.pullSucceeded -> Result.success()
                else -> Result.retry()
            }
        }
    }

    companion object {
        const val KEY_USER_ID = "user_id"
        private const val UNIQUE_WORK_PREFIX = "transaction-sync:"
        internal const val LEGACY_UNIQUE_WORK_NAME = "transaction-sync"

        internal fun uniqueWorkName(userId: String): String = "$UNIQUE_WORK_PREFIX$userId"

        fun enqueue(context: Context, userId: String) {
            val request = OneTimeWorkRequestBuilder<TransactionSyncWorker>()
                .setInputData(workDataOf(KEY_USER_ID to userId))
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context.applicationContext).enqueueUniqueWork(
                uniqueWorkName(userId),
                ExistingWorkPolicy.KEEP,
                request,
            )
        }

        fun cancel(context: Context, userId: String) {
            WorkManager.getInstance(context.applicationContext).apply {
                cancelUniqueWork(uniqueWorkName(userId))
                cancelUniqueWork(LEGACY_UNIQUE_WORK_NAME)
            }
        }
    }
}

internal sealed interface AuthenticatedSyncRun<out T> {
    data object Skipped : AuthenticatedSyncRun<Nothing>
    data class Executed<T>(val value: T) : AuthenticatedSyncRun<T>
}

internal suspend fun <T> runTransactionSyncIfAuthenticated(
    workerUserId: String,
    tokenStore: SecureTokenStore,
    block: suspend () -> T,
): AuthenticatedSyncRun<T> {
    val session = tokenStore.readSession()
    if (
        session == null ||
        session.authenticatedUserId != workerUserId ||
        session.sessionIdentity.isNullOrBlank()
    ) {
        return AuthenticatedSyncRun.Skipped
    }
    return AuthenticatedSyncRun.Executed(block())
}
