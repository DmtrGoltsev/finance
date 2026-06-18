package com.finance.mvp.notifications

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import com.finance.mvp.MainActivity
import com.finance.mvp.R
import com.finance.mvp.ui.PlanningNotificationCandidate
import com.finance.mvp.ui.PlanningNotificationCandidateAction
import java.time.LocalTime
import java.time.YearMonth
import java.time.ZonedDateTime
import kotlin.math.min

data class PlanningIncomeReminder(
    val incomeSourceId: String,
    val planId: String,
    val scope: String,
    val month: String,
    val source: String,
    val amount: String,
    val currency: String,
    val dayOfMonth: Int,
)

object PlanningReminderNotifications {
    const val ACTION_PLANNING_REMINDER = "com.finance.mvp.notifications.PLANNING_REMINDER"

    private const val CHANNEL_ID = "planning_income_reminders"
    private const val CHANNEL_NAME = "Planning income reminders"
    private const val PREFS_NAME = "planning_income_reminders_v1"
    private const val ACTIVE_IDS_KEY = "active_income_source_ids"
    private const val REQUEST_OFFSET = 41000
    private val reminderTime = LocalTime.of(9, 0)
    private const val WINDOW_MILLIS = 60L * 60L * 1000L

    private const val EXTRA_INCOME_SOURCE_ID = "incomeSourceId"
    private const val EXTRA_PLAN_ID = "planningPlanId"
    private const val EXTRA_SCOPE = "planningScope"
    private const val EXTRA_MONTH = "planningMonth"
    private const val EXTRA_SOURCE = "planningSource"
    private const val EXTRA_AMOUNT = "planningAmount"
    private const val EXTRA_CURRENCY = "planningCurrency"
    private const val EXTRA_DAY_OF_MONTH = "planningDayOfMonth"

    fun applyCandidate(context: Context, candidate: PlanningNotificationCandidate) {
        when (candidate.action) {
            PlanningNotificationCandidateAction.ScheduleIncomeSource -> {
                val reminder = candidate.toReminderOrNull()
                if (reminder == null) {
                    candidate.incomeSourceId?.let { cancel(context, it) }
                } else {
                    schedule(context, reminder)
                }
            }
            PlanningNotificationCandidateAction.CancelIncomeSource -> {
                candidate.incomeSourceId?.let { cancel(context, it) }
            }
            PlanningNotificationCandidateAction.PlanStatusChanged -> Unit
        }
    }

    fun schedule(context: Context, reminder: PlanningIncomeReminder) {
        createChannel(context)
        saveReminder(context, reminder)
        scheduleAlarm(context, reminder, nextOccurrence(reminder, ZonedDateTime.now()))
    }

    fun cancel(context: Context, incomeSourceId: String) {
        val alarmManager = context.getSystemService(AlarmManager::class.java)
        reminderPendingIntent(context, incomeSourceId, PendingIntent.FLAG_NO_CREATE)?.let(alarmManager::cancel)
        context.getSystemService(NotificationManager::class.java).cancel(notificationId(incomeSourceId))
        removeReminder(context, incomeSourceId)
    }

    fun showReminder(context: Context, reminder: PlanningIncomeReminder) {
        createChannel(context)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val notification = Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_cash_24)
            .setContentTitle("Проверьте плановый доход")
            .setContentText("${reminder.source}: ${reminder.amount} ${reminder.currency}")
            .setStyle(
                Notification.BigTextStyle().bigText(
                    "${reminder.source}: ${reminder.amount} ${reminder.currency}. Откройте планирование, чтобы подтвердить или поправить доход.",
                ),
            )
            .setContentIntent(openPlanningPendingIntent(context, reminder))
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_REMINDER)
            .build()

        context.getSystemService(NotificationManager::class.java)
            .notify(notificationId(reminder.incomeSourceId), notification)
    }

    fun rescheduleNextMonth(context: Context, reminder: PlanningIncomeReminder) {
        saveReminder(context, reminder)
        scheduleAlarm(context, reminder, nextOccurrence(reminder, ZonedDateTime.now()))
    }

    fun rescheduleActiveReminders(context: Context) {
        loadActiveReminders(context).forEach { schedule(context, it) }
    }

    fun reminderFromIntent(intent: Intent): PlanningIncomeReminder? {
        val day = intent.getIntExtra(EXTRA_DAY_OF_MONTH, 0)
        if (day !in 1..31) return null
        return PlanningIncomeReminder(
            incomeSourceId = intent.getStringExtra(EXTRA_INCOME_SOURCE_ID).orEmpty(),
            planId = intent.getStringExtra(EXTRA_PLAN_ID).orEmpty(),
            scope = intent.getStringExtra(EXTRA_SCOPE).orEmpty(),
            month = intent.getStringExtra(EXTRA_MONTH).orEmpty(),
            source = intent.getStringExtra(EXTRA_SOURCE).orEmpty(),
            amount = intent.getStringExtra(EXTRA_AMOUNT).orEmpty(),
            currency = intent.getStringExtra(EXTRA_CURRENCY).orEmpty(),
            dayOfMonth = day,
        ).takeIf { it.incomeSourceId.isNotBlank() && it.planId.isNotBlank() }
    }

    private fun scheduleAlarm(context: Context, reminder: PlanningIncomeReminder, triggerAt: ZonedDateTime) {
        val alarmManager = context.getSystemService(AlarmManager::class.java)
        alarmManager.setWindow(
            AlarmManager.RTC_WAKEUP,
            triggerAt.toInstant().toEpochMilli(),
            WINDOW_MILLIS,
            reminderPendingIntent(context, reminder),
        )
    }

    private fun nextOccurrence(reminder: PlanningIncomeReminder, now: ZonedDateTime): ZonedDateTime {
        var targetMonth = parseYearMonth(reminder.month) ?: YearMonth.from(now)
        var occurrence = occurrenceInMonth(targetMonth, reminder.dayOfMonth, now)
        while (!occurrence.isAfter(now)) {
            targetMonth = targetMonth.plusMonths(1)
            occurrence = occurrenceInMonth(targetMonth, reminder.dayOfMonth, now)
        }
        return occurrence
    }

    private fun occurrenceInMonth(month: YearMonth, requestedDay: Int, now: ZonedDateTime): ZonedDateTime {
        val actualDay = min(requestedDay, month.lengthOfMonth())
        return month.atDay(actualDay).atTime(reminderTime).atZone(now.zone)
    }

    private fun parseYearMonth(month: String): YearMonth? = runCatching { YearMonth.parse(month) }.getOrNull()

    private fun reminderPendingIntent(
        context: Context,
        incomeSourceId: String,
        lookupFlag: Int,
    ): PendingIntent? {
        val intent = Intent(context, PlanningReminderReceiver::class.java).setAction(ACTION_PLANNING_REMINDER)
        return PendingIntent.getBroadcast(
            context,
            requestCode(incomeSourceId),
            intent,
            lookupFlag or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun reminderPendingIntent(context: Context, reminder: PlanningIncomeReminder): PendingIntent {
        val intent = Intent(context, PlanningReminderReceiver::class.java)
            .setAction(ACTION_PLANNING_REMINDER)
            .putReminderExtras(reminder)
        return PendingIntent.getBroadcast(
            context,
            requestCode(reminder.incomeSourceId),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun openPlanningPendingIntent(context: Context, reminder: PlanningIncomeReminder): PendingIntent {
        val intent = Intent(context, MainActivity::class.java)
            .putExtra("openSection", "analytics")
            .putExtra("openPlanning", true)
            .putExtra("incomeSourceId", reminder.incomeSourceId)
            .putExtra("planningPlanId", reminder.planId)
            .putExtra("planningMonth", reminder.month)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        return PendingIntent.getActivity(
            context,
            requestCode(reminder.incomeSourceId) + REQUEST_OFFSET,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun Intent.putReminderExtras(reminder: PlanningIncomeReminder): Intent = putExtra(
        EXTRA_INCOME_SOURCE_ID,
        reminder.incomeSourceId,
    )
        .putExtra(EXTRA_PLAN_ID, reminder.planId)
        .putExtra(EXTRA_SCOPE, reminder.scope)
        .putExtra(EXTRA_MONTH, reminder.month)
        .putExtra(EXTRA_SOURCE, reminder.source)
        .putExtra(EXTRA_AMOUNT, reminder.amount)
        .putExtra(EXTRA_CURRENCY, reminder.currency)
        .putExtra(EXTRA_DAY_OF_MONTH, reminder.dayOfMonth)

    private fun createChannel(context: Context) {
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Reminders to confirm or edit planned income sources"
        }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun notificationId(incomeSourceId: String): Int = incomeSourceId.hashCode() and 0x3fffffff

    private fun requestCode(incomeSourceId: String): Int = notificationId(incomeSourceId)

    private fun PlanningNotificationCandidate.toReminderOrNull(): PlanningIncomeReminder? {
        val sourceId = incomeSourceId?.takeIf { it.isNotBlank() } ?: return null
        val reminderDay = dayOfMonth?.takeIf { it in 1..31 } ?: return null
        return PlanningIncomeReminder(
            incomeSourceId = sourceId,
            planId = planId,
            scope = scope,
            month = month,
            source = incomeSourceName.orEmpty().ifBlank { "Плановый доход" },
            amount = incomeSourceAmount.orEmpty(),
            currency = currency.orEmpty(),
            dayOfMonth = reminderDay,
        )
    }

    private fun saveReminder(context: Context, reminder: PlanningIncomeReminder) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val activeIds = prefs.getStringSet(ACTIVE_IDS_KEY, emptySet()).orEmpty().toMutableSet()
        activeIds += reminder.incomeSourceId
        prefs.edit()
            .putStringSet(ACTIVE_IDS_KEY, activeIds)
            .putString(key(reminder.incomeSourceId, EXTRA_PLAN_ID), reminder.planId)
            .putString(key(reminder.incomeSourceId, EXTRA_SCOPE), reminder.scope)
            .putString(key(reminder.incomeSourceId, EXTRA_MONTH), reminder.month)
            .putString(key(reminder.incomeSourceId, EXTRA_SOURCE), reminder.source)
            .putString(key(reminder.incomeSourceId, EXTRA_AMOUNT), reminder.amount)
            .putString(key(reminder.incomeSourceId, EXTRA_CURRENCY), reminder.currency)
            .putInt(key(reminder.incomeSourceId, EXTRA_DAY_OF_MONTH), reminder.dayOfMonth)
            .apply()
    }

    private fun removeReminder(context: Context, incomeSourceId: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val activeIds = prefs.getStringSet(ACTIVE_IDS_KEY, emptySet()).orEmpty().toMutableSet()
        activeIds -= incomeSourceId
        prefs.edit()
            .putStringSet(ACTIVE_IDS_KEY, activeIds)
            .remove(key(incomeSourceId, EXTRA_PLAN_ID))
            .remove(key(incomeSourceId, EXTRA_SCOPE))
            .remove(key(incomeSourceId, EXTRA_MONTH))
            .remove(key(incomeSourceId, EXTRA_SOURCE))
            .remove(key(incomeSourceId, EXTRA_AMOUNT))
            .remove(key(incomeSourceId, EXTRA_CURRENCY))
            .remove(key(incomeSourceId, EXTRA_DAY_OF_MONTH))
            .apply()
    }

    private fun loadActiveReminders(context: Context): List<PlanningIncomeReminder> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getStringSet(ACTIVE_IDS_KEY, emptySet()).orEmpty().mapNotNull { id ->
            val day = prefs.getInt(key(id, EXTRA_DAY_OF_MONTH), 0)
            if (day !in 1..31) return@mapNotNull null
            PlanningIncomeReminder(
                incomeSourceId = id,
                planId = prefs.getString(key(id, EXTRA_PLAN_ID), null) ?: return@mapNotNull null,
                scope = prefs.getString(key(id, EXTRA_SCOPE), null).orEmpty(),
                month = prefs.getString(key(id, EXTRA_MONTH), null).orEmpty(),
                source = prefs.getString(key(id, EXTRA_SOURCE), null).orEmpty(),
                amount = prefs.getString(key(id, EXTRA_AMOUNT), null).orEmpty(),
                currency = prefs.getString(key(id, EXTRA_CURRENCY), null).orEmpty(),
                dayOfMonth = day,
            )
        }
    }

    private fun key(incomeSourceId: String, field: String): String = "$incomeSourceId.$field"
}
