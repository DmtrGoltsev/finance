package com.finance.mvp.notifications

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.finance.mvp.BuildConfig
import com.finance.mvp.R
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.session.AndroidSecureTokenStore
import com.google.android.gms.tasks.Tasks
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext

class FinancePushApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        if (!BuildConfig.FINANCE_PUSH_ENABLED) return
        if (FirebaseApp.getApps(this).isEmpty()) {
            FirebaseApp.initializeApp(this, FirebaseOptions.Builder()
                .setApplicationId(BuildConfig.FIREBASE_APPLICATION_ID)
                .setApiKey(BuildConfig.FIREBASE_API_KEY)
                .setProjectId(BuildConfig.FIREBASE_PROJECT_ID)
                .setGcmSenderId(BuildConfig.FIREBASE_SENDER_ID).build())
        }
        FirebaseMessaging.getInstance().isAutoInitEnabled = true
        PushRegistrationWorker.enqueue(this)
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "finance-push-refresh-daily", ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<PushRegistrationWorker>(24, TimeUnit.HOURS)
                .setConstraints(pushConstraints()).build(),
        )
    }
}

private fun pushConstraints() = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

internal fun deviceId(context: Context, user: String): String {
    val preferences = context.getSharedPreferences("push-device-ids", Context.MODE_PRIVATE)
    synchronized(PushRegistrationWorker::class.java) {
        return preferences.getString(user, null) ?: UUID.randomUUID().toString().also {
            check(preferences.edit().putString(user, it).commit())
        }
    }
}

class ApiInvestmentPushTokenRegistrar(private val context: Context) : InvestmentPushTokenRegistrar {
    override suspend fun registerToken(token: String): Result<Unit> {
        val store = AndroidSecureTokenStore(context)
        val before = store.readSession() ?: return Result.failure(IllegalStateException("No session"))
        val user = before.authenticatedUserId ?: return Result.failure(IllegalStateException("No owner"))
        val api = LiveFinanceApiClient(ApiConfig(BuildConfig.FINANCE_API_BASE_URL), store)
        // The client fences the request against logout/rotation while it is in flight.
        val sid = before.sessionIdentity ?: return Result.failure(IllegalStateException("No session id"))
        val response = api.registerPushDevice(deviceId(context, user), token, sid)
        return when (response) {
            is ApiResult.Success -> Result.success(Unit)
            is ApiResult.Failure -> Result.failure(IllegalStateException("Push registration failed"))
        }
    }
}

class PushRegistrationWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        if (!BuildConfig.FINANCE_PUSH_ENABLED) return@withContext Result.success()
        if (AndroidSecureTokenStore(applicationContext).readSession() == null) return@withContext Result.success()
        try {
            val prefs = applicationContext.getSharedPreferences("push-token-lifecycle", Context.MODE_PRIVATE)
            val rotation = prefs.getLong("rotation", 0)
            if (prefs.getLong("applied", 0) < rotation) {
                Tasks.await(FirebaseMessaging.getInstance().deleteToken(), 30, TimeUnit.SECONDS)
                check(prefs.edit().putLong("applied", rotation).commit())
            }
            val token = Tasks.await(FirebaseMessaging.getInstance().token, 30, TimeUnit.SECONDS)
            if (ApiInvestmentPushTokenRegistrar(applicationContext).registerToken(token).isSuccess) {
                Result.success()
            } else Result.retry()
        } catch (_: Exception) { Result.retry() }
    }

    companion object {
        fun enqueue(context: Context) {
            if (!BuildConfig.FINANCE_PUSH_ENABLED) return
            WorkManager.getInstance(context).enqueueUniqueWork("finance-push-register", ExistingWorkPolicy.REPLACE,
                OneTimeWorkRequestBuilder<PushRegistrationWorker>().setConstraints(pushConstraints()).build())
        }

        suspend fun revoke(context: Context) {
            if (!BuildConfig.FINANCE_PUSH_ENABLED) return
            val prefs = context.getSharedPreferences("push-token-lifecycle", Context.MODE_PRIVATE)
            synchronized(PushRegistrationWorker::class.java) {
                check(prefs.edit().putLong("rotation", prefs.getLong("rotation", 0) + 1).commit())
            }
            WorkManager.getInstance(context).cancelUniqueWork("finance-push-register")
            val store = AndroidSecureTokenStore(context)
            val session = store.readSession() ?: return
            val user = session.authenticatedUserId ?: return
            val sid = session.sessionIdentity ?: return
            LiveFinanceApiClient(ApiConfig(BuildConfig.FINANCE_API_BASE_URL), store)
                .revokePushDevice(deviceId(context, user), sid)
        }
    }
}

internal data class ReadyPush(val eventId: String, val jobId: String)

internal fun parseReadyPush(data: Map<String, String>, currentSession: String?): ReadyPush? {
    if (currentSession == null || data["sessionId"] != currentSession ||
        data["type"] != "investment_recommendation") return null
    return runCatching {
        ReadyPush(UUID.fromString(data.getValue("eventId")).toString(),
            UUID.fromString(data.getValue("jobId")).toString())
    }.getOrNull()
}

class FinanceMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) { PushRegistrationWorker.enqueue(this) }

    override fun onMessageReceived(message: RemoteMessage) {
        if (!BuildConfig.FINANCE_PUSH_ENABLED) return
        val session = runBlocking { AndroidSecureTokenStore(this@FinanceMessagingService).readSession() }
        val push = parseReadyPush(message.data, session?.sessionIdentity) ?: return
        val manager = NotificationManagerCompat.from(this)
        if (!manager.areNotificationsEnabled()) return
        val seen = getSharedPreferences("push-seen-events", MODE_PRIVATE)
        synchronized(FinanceMessagingService::class.java) {
            if (seen.contains(push.eventId)) return
            // Persist before notify; a crash can suppress a push, but cannot duplicate the alert.
            if (!seen.edit().putLong(push.eventId, System.currentTimeMillis()).commit()) return
            val old = System.currentTimeMillis() - TimeUnit.DAYS.toMillis(35)
            seen.edit().apply { seen.all.filterValues { it is Long && it < old }.keys.forEach { remove(it) } }.apply()
            manager.createNotificationChannel(NotificationChannel("investments", "Анализ портфеля",
                NotificationManager.IMPORTANCE_DEFAULT))
            val intent = investmentRecommendationsIntent(this, push.jobId)
            val pending = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = NotificationCompat.Builder(this, "investments")
                .setSmallIcon(R.mipmap.ic_launcher).setContentTitle("Finance")
                .setContentText("Анализ портфеля готов").setContentIntent(pending)
                .setAutoCancel(true).setOnlyAlertOnce(true).build()
            try { manager.notify(push.eventId, 0, notification) } catch (_: SecurityException) { }
        }
    }
}
