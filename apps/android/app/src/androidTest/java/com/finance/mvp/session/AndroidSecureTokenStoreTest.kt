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
    fun persistsSessionAcrossStoreInstancesWithoutPlaintextXml() = runBlocking {
        val accessToken = "access-token-${UUID.randomUUID()}"
        val refreshToken = "refresh-token-${UUID.randomUUID()}"
        val sessionIdentity = "session-${UUID.randomUUID()}"
        val authenticatedUserId = "user-${UUID.randomUUID()}"

        AndroidSecureTokenStore(context).saveSessionTokens(
            accessToken,
            refreshToken,
            sessionIdentity,
            authenticatedUserId,
        )

        val restoredStore = AndroidSecureTokenStore(context)
        val restoredSession = restoredStore.readSession()
        assertEquals(accessToken, restoredSession?.accessToken)
        assertEquals(refreshToken, restoredSession?.refreshToken)
        assertEquals(sessionIdentity, restoredSession?.sessionIdentity)
        assertEquals(authenticatedUserId, restoredSession?.authenticatedUserId)
        assertTrue((restoredSession?.generation ?: 0L) > 0L)

        val encryptedFile = AndroidSecureTokenStore.encryptedPreferencesFile(context)
        assertTrue(encryptedFile.exists())
        val encryptedText = encryptedFile.readText()
        assertFalse(encryptedText.contains(accessToken))
        assertFalse(encryptedText.contains(refreshToken))
        assertFalse(encryptedText.contains(sessionIdentity))
        assertFalse(encryptedText.contains(authenticatedUserId))
    }

    @Test
    fun clearRemovesStoredToken() = runBlocking {
        val store = AndroidSecureTokenStore(context)
        store.saveSessionTokens(
            accessToken = "access-token-${UUID.randomUUID()}",
            refreshToken = "refresh-token-${UUID.randomUUID()}",
        )

        store.clear()

        val restoredStore = AndroidSecureTokenStore(context)
        assertNull(restoredStore.readAccessToken())
        assertNull(restoredStore.readRefreshToken())
    }

    @Test
    fun refreshPreservesGenerationAndLogoutInvalidatesItAcrossStoreInstances() = runBlocking {
        val store = AndroidSecureTokenStore(context)
        store.saveSessionTokens("access-a", "refresh-a", "session-a", "user-a")
        val original = requireNotNull(store.readSession())

        assertTrue(
            AndroidSecureTokenStore(context).rotateSessionTokens(
                expectedGeneration = original.generation,
                expectedIdentity = original.sessionIdentity,
                accessToken = "access-a-rotated",
                refreshToken = "refresh-a-rotated",
            ),
        )
        val rotated = requireNotNull(AndroidSecureTokenStore(context).readSession())
        assertEquals(original.generation, rotated.generation)
        assertEquals(original.sessionIdentity, rotated.sessionIdentity)

        AndroidSecureTokenStore(context).clear()
        AndroidSecureTokenStore(context).saveSessionTokens(
            "access-b",
            "refresh-b",
            "session-b",
            "user-b",
        )
        val replacement = requireNotNull(AndroidSecureTokenStore(context).readSession())
        assertTrue(replacement.generation > original.generation)
        assertEquals("session-b", replacement.sessionIdentity)
    }
}
