package com.finance.mvp.sync

import android.content.Context
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

interface DeviceIdStore {
    suspend fun deviceId(): String
}

class AndroidDeviceIdStore(
    context: Context,
) : DeviceIdStore {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_NAME,
        Context.MODE_PRIVATE,
    )

    override suspend fun deviceId(): String = withContext(Dispatchers.IO) {
        preferences.getString(KEY_DEVICE_ID, null)?.takeIf { it.isNotBlank() }
            ?: "android-${UUID.randomUUID()}".also { generated ->
                check(preferences.edit().putString(KEY_DEVICE_ID, generated).commit()) {
                    "Failed to persist sync device id."
                }
            }
    }

    companion object {
        const val PREFERENCES_NAME = "finance_sync_device"
        const val KEY_DEVICE_ID = "device_id"
    }
}

class InMemoryDeviceIdStore(
    private val value: String = "android-test-device",
) : DeviceIdStore {
    override suspend fun deviceId(): String = value
}
