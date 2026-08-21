package com.finance.mvp.session

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

interface SecureTokenStore {
    suspend fun readSession(): StoredSessionTokens?
    suspend fun readAccessToken(): String?
    suspend fun readRefreshToken(): String?
    suspend fun saveAccessToken(token: String)
    suspend fun saveSessionTokens(
        accessToken: String,
        refreshToken: String,
        sessionIdentity: String? = null,
        authenticatedUserId: String? = null,
    )
    suspend fun rotateSessionTokens(
        expectedGeneration: Long,
        expectedIdentity: String?,
        accessToken: String,
        refreshToken: String,
    ): Boolean
    suspend fun bindAuthenticatedUser(
        expectedGeneration: Long,
        expectedIdentity: String?,
        sessionIdentity: String,
        authenticatedUserId: String,
    ): Boolean
    suspend fun clear()
}

data class StoredSessionTokens(
    val accessToken: String,
    val refreshToken: String?,
    val sessionIdentity: String?,
    val authenticatedUserId: String?,
    val generation: Long,
)

class AndroidSecureTokenStore(
    context: Context,
) : SecureTokenStore {
    private val appContext = context.applicationContext
    private val preferences: SharedPreferences by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        createEncryptedPreferences(appContext)
    }

    override suspend fun readSession(): StoredSessionTokens? = withContext(Dispatchers.IO) {
        synchronized(STORAGE_LOCK) { readSessionLocked() }
    }

    override suspend fun readAccessToken(): String? = readSession()?.accessToken

    override suspend fun readRefreshToken(): String? = readSession()?.refreshToken

    override suspend fun saveAccessToken(token: String) {
        require(token.isNotBlank()) { "Access token must not be blank." }
        withContext(Dispatchers.IO) {
            synchronized(STORAGE_LOCK) {
                check(
                    preferences.edit()
                        .putString(KEY_ACCESS_TOKEN, token)
                        .remove(KEY_REFRESH_TOKEN)
                        .remove(KEY_SESSION_IDENTITY)
                        .remove(KEY_AUTHENTICATED_USER_ID)
                        .putLong(KEY_SESSION_GENERATION, nextGenerationLocked())
                        .commit(),
                ) {
                    "Failed to persist access token in encrypted storage."
                }
            }
        }
    }

    override suspend fun saveSessionTokens(
        accessToken: String,
        refreshToken: String,
        sessionIdentity: String?,
        authenticatedUserId: String?,
    ) {
        require(accessToken.isNotBlank()) { "Access token must not be blank." }
        require(refreshToken.isNotBlank()) { "Refresh token must not be blank." }
        withContext(Dispatchers.IO) {
            synchronized(STORAGE_LOCK) {
                val editor = preferences.edit()
                    .putString(KEY_ACCESS_TOKEN, accessToken)
                    .putString(KEY_REFRESH_TOKEN, refreshToken)
                    .putLong(KEY_SESSION_GENERATION, nextGenerationLocked())
                sessionIdentity?.takeIf { it.isNotBlank() }
                    ?.let { editor.putString(KEY_SESSION_IDENTITY, it) }
                    ?: editor.remove(KEY_SESSION_IDENTITY)
                authenticatedUserId?.takeIf { it.isNotBlank() }
                    ?.let { editor.putString(KEY_AUTHENTICATED_USER_ID, it) }
                    ?: editor.remove(KEY_AUTHENTICATED_USER_ID)
                check(editor.commit()) {
                    "Failed to persist session tokens in encrypted storage."
                }
            }
        }
    }

    override suspend fun bindAuthenticatedUser(
        expectedGeneration: Long,
        expectedIdentity: String?,
        sessionIdentity: String,
        authenticatedUserId: String,
    ): Boolean {
        require(sessionIdentity.isNotBlank()) { "Session identity must not be blank." }
        require(authenticatedUserId.isNotBlank()) { "Authenticated user ID must not be blank." }
        return withContext(Dispatchers.IO) {
            synchronized(STORAGE_LOCK) {
                val current = readSessionLocked() ?: return@synchronized false
                if (
                    current.generation != expectedGeneration ||
                    current.sessionIdentity != expectedIdentity ||
                    current.authenticatedUserId != null ||
                    (current.sessionIdentity != null && current.sessionIdentity != sessionIdentity)
                ) {
                    return@synchronized false
                }
                check(
                    preferences.edit()
                        .putString(KEY_SESSION_IDENTITY, sessionIdentity)
                        .putString(KEY_AUTHENTICATED_USER_ID, authenticatedUserId)
                        .commit(),
                ) {
                    "Failed to bind authenticated user to secure session."
                }
                true
            }
        }
    }

    override suspend fun rotateSessionTokens(
        expectedGeneration: Long,
        expectedIdentity: String?,
        accessToken: String,
        refreshToken: String,
    ): Boolean {
        require(accessToken.isNotBlank()) { "Access token must not be blank." }
        require(refreshToken.isNotBlank()) { "Refresh token must not be blank." }
        return withContext(Dispatchers.IO) {
            synchronized(STORAGE_LOCK) {
                val current = readSessionLocked() ?: return@synchronized false
                if (
                    current.generation != expectedGeneration ||
                    current.sessionIdentity != expectedIdentity
                ) {
                    return@synchronized false
                }
                check(
                    preferences.edit()
                        .putString(KEY_ACCESS_TOKEN, accessToken)
                        .putString(KEY_REFRESH_TOKEN, refreshToken)
                        .commit(),
                ) {
                    "Failed to rotate session tokens in encrypted storage."
                }
                true
            }
        }
    }

    override suspend fun clear() {
        withContext(Dispatchers.IO) {
            synchronized(STORAGE_LOCK) {
                check(
                    preferences.edit()
                        .remove(KEY_ACCESS_TOKEN)
                        .remove(KEY_REFRESH_TOKEN)
                        .remove(KEY_SESSION_IDENTITY)
                        .remove(KEY_AUTHENTICATED_USER_ID)
                        .putLong(KEY_SESSION_GENERATION, nextGenerationLocked())
                        .commit(),
                ) {
                    "Failed to clear session tokens from encrypted storage."
                }
            }
        }
    }

    private fun readSessionLocked(): StoredSessionTokens? {
        val accessToken = preferences.getString(KEY_ACCESS_TOKEN, null)
            ?.takeIf { it.isNotBlank() }
            ?: return null
        return StoredSessionTokens(
            accessToken = accessToken,
            refreshToken = preferences.getString(KEY_REFRESH_TOKEN, null)?.takeIf { it.isNotBlank() },
            sessionIdentity = preferences.getString(KEY_SESSION_IDENTITY, null)?.takeIf { it.isNotBlank() },
            authenticatedUserId = preferences.getString(KEY_AUTHENTICATED_USER_ID, null)
                ?.takeIf { it.isNotBlank() },
            generation = preferences.getLong(KEY_SESSION_GENERATION, LEGACY_SESSION_GENERATION),
        )
    }

    private fun nextGenerationLocked(): Long =
        preferences.getLong(KEY_SESSION_GENERATION, LEGACY_SESSION_GENERATION) + 1L

    @Suppress("DEPRECATION")
    private fun createEncryptedPreferences(context: Context): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        return EncryptedSharedPreferences.create(
            context,
            PREFERENCES_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    companion object {
        const val PREFERENCES_NAME = "finance_secure_session"
        const val KEY_ACCESS_TOKEN = "access_token"
        const val KEY_REFRESH_TOKEN = "refresh_token"
        const val KEY_SESSION_IDENTITY = "session_identity"
        const val KEY_AUTHENTICATED_USER_ID = "authenticated_user_id"
        const val KEY_SESSION_GENERATION = "session_generation"
        const val LEGACY_SESSION_GENERATION = 0L
        private val STORAGE_LOCK = Any()

        fun encryptedPreferencesFile(context: Context): File =
            File(context.applicationInfo.dataDir, "shared_prefs/$PREFERENCES_NAME.xml")
    }
}

class InMemorySecureTokenStore : SecureTokenStore {
    private val lock = Any()
    private var session: StoredSessionTokens? = null
    private var generation: Long = AndroidSecureTokenStore.LEGACY_SESSION_GENERATION

    override suspend fun readSession(): StoredSessionTokens? = synchronized(lock) { session }

    override suspend fun readAccessToken(): String? = readSession()?.accessToken
    override suspend fun readRefreshToken(): String? = readSession()?.refreshToken

    override suspend fun saveAccessToken(token: String) {
        synchronized(lock) {
            generation += 1
            session = StoredSessionTokens(token, null, null, null, generation)
        }
    }

    override suspend fun saveSessionTokens(
        accessToken: String,
        refreshToken: String,
        sessionIdentity: String?,
        authenticatedUserId: String?,
    ) {
        synchronized(lock) {
            generation += 1
            session = StoredSessionTokens(
                accessToken,
                refreshToken,
                sessionIdentity,
                authenticatedUserId,
                generation,
            )
        }
    }

    override suspend fun rotateSessionTokens(
        expectedGeneration: Long,
        expectedIdentity: String?,
        accessToken: String,
        refreshToken: String,
    ): Boolean = synchronized(lock) {
        val current = session ?: return@synchronized false
        if (
            current.generation != expectedGeneration ||
            current.sessionIdentity != expectedIdentity
        ) {
            return@synchronized false
        }
        session = current.copy(accessToken = accessToken, refreshToken = refreshToken)
        true
    }

    override suspend fun bindAuthenticatedUser(
        expectedGeneration: Long,
        expectedIdentity: String?,
        sessionIdentity: String,
        authenticatedUserId: String,
    ): Boolean = synchronized(lock) {
        val current = session ?: return@synchronized false
        if (
            current.generation != expectedGeneration ||
            current.sessionIdentity != expectedIdentity ||
            current.authenticatedUserId != null ||
            (current.sessionIdentity != null && current.sessionIdentity != sessionIdentity)
        ) {
            return@synchronized false
        }
        session = current.copy(
            sessionIdentity = sessionIdentity,
            authenticatedUserId = authenticatedUserId,
        )
        true
    }

    override suspend fun clear() {
        synchronized(lock) {
            generation += 1
            session = null
        }
    }
}
