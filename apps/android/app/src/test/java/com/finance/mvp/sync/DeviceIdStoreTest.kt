package com.finance.mvp.sync

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class DeviceIdStoreTest {
    @Test
    fun androidDeviceIdStoreReturnsStableGeneratedId() = runTest {
        val context = ApplicationProvider.getApplicationContext<Context>()
        context.getSharedPreferences(AndroidDeviceIdStore.PREFERENCES_NAME, Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()

        val firstStore = AndroidDeviceIdStore(context)
        val first = firstStore.deviceId()
        val second = AndroidDeviceIdStore(context).deviceId()

        assertTrue(first.startsWith("android-"))
        assertEquals(first, second)
    }
}
