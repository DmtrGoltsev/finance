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
import java.util.concurrent.TimeUnit

class TransactionSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val userId = inputData.getString(KEY_USER_ID)?.takeIf { it.isNotBlank() }
            ?: return Result.failure()

        val apiClient = LiveFinanceApiClient(
            config = ApiConfig(BuildConfig.FINANCE_API_BASE_URL),
            tokenStore = AndroidSecureTokenStore(applicationContext),
        )
        val manager = SyncManager(
            database = FinanceLocalDatabase.getInstance(applicationContext),
            apiClient = FinanceSyncApiClientAdapter(apiClient),
            deviceIdStore = AndroidDeviceIdStore(applicationContext),
        )
        val summary = manager.syncOnce(userId)
        return when {
            summary.push.failed > 0 -> Result.failure()
            summary.pullSucceeded -> Result.success()
            else -> Result.retry()
        }
    }

    companion object {
        const val KEY_USER_ID = "user_id"
        private const val UNIQUE_WORK_NAME = "transaction-sync"

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
                UNIQUE_WORK_NAME,
                ExistingWorkPolicy.KEEP,
                request,
            )
        }
    }
}
