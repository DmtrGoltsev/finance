package com.finance.mvp.capture

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class CaptureOptInStore(context: Context) {
    private val appContext = context.applicationContext
    private val preferences: SharedPreferences by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        EncryptedSharedPreferences.create(
            appContext,
            PREFERENCES_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun isSmsCaptureEnabled(): Boolean = preferences.getBoolean(KEY_SMS_CAPTURE, false)

    fun setSmsCaptureEnabled(enabled: Boolean) {
        check(preferences.edit().putBoolean(KEY_SMS_CAPTURE, enabled).commit()) {
            "Failed to persist SMS capture opt-in."
        }
    }

    fun isNotificationCaptureEnabled(): Boolean = preferences.getBoolean(KEY_NOTIFICATION_CAPTURE, false)

    fun setNotificationCaptureEnabled(enabled: Boolean) {
        check(preferences.edit().putBoolean(KEY_NOTIFICATION_CAPTURE, enabled).commit()) {
            "Failed to persist notification capture opt-in."
        }
    }

    companion object {
        private const val PREFERENCES_NAME = "finance_capture_opt_in"
        private const val KEY_SMS_CAPTURE = "sms_capture_enabled"
        private const val KEY_NOTIFICATION_CAPTURE = "notification_capture_enabled"
    }
}
