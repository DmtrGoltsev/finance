package com.finance.mvp.session

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AndroidSecureTokenStoreTest {
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences(AndroidSecureTokenStore.PREFERENCES_NAME, Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()
    }

    @Test
    fun persistsTokenAcrossStoreInstancesWithoutPlaintextXml() = runBlocking {
        val token = "test-token-${UUID.randomUUID()}"

        AndroidSecureTokenStore(context).saveAccessToken(token)

        assertEquals(token, AndroidSecureTokenStore(context).readAccessToken())

        val encryptedFile = AndroidSecureTokenStore.encryptedPreferencesFile(context)
        assertTrue(encryptedFile.exists())
        assertFalse(encryptedFile.readText().contains(token))
    }

    @Test
    fun clearRemovesStoredToken() = runBlocking {
        val store = AndroidSecureTokenStore(context)
        store.saveAccessToken("test-token-${UUID.randomUUID()}")

        store.clear()

        assertNull(AndroidSecureTokenStore(context).readAccessToken())
    }
}
