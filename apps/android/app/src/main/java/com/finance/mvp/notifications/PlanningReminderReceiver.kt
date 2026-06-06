package com.finance.mvp.notifications

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class PlanningReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            PlanningReminderNotifications.ACTION_PLANNING_REMINDER -> {
                val reminder = PlanningReminderNotifications.reminderFromIntent(intent) ?: return
                PlanningReminderNotifications.showReminder(context, reminder)
                PlanningReminderNotifications.rescheduleNextMonth(context, reminder)
            }
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            -> PlanningReminderNotifications.rescheduleActiveReminders(context)
        }
    }
}
