package com.finance.mvp.session

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

interface SecureTokenStore {
    suspend fun readAccessToken(): String?
    suspend fun saveAccessToken(token: String)
    suspend fun clear()
}

class AndroidSecureTokenStore(
    context: Context,
) : SecureTokenStore {
    private val appContext = context.applicationContext
    private val preferences: SharedPreferences by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        createEncryptedPreferences(appContext)
    }

    override suspend fun readAccessToken(): String? = withContext(Dispatchers.IO) {
        preferences.getString(KEY_ACCESS_TOKEN, null)
    }

    override suspend fun saveAccessToken(token: String) {
        require(token.isNotBlank()) { "Access token must not be blank." }
        withContext(Dispatchers.IO) {
            check(preferences.edit().putString(KEY_ACCESS_TOKEN, token).commit()) {
                "Failed to persist access token in encrypted storage."
            }
        }
    }

    override suspend fun clear() {
        withContext(Dispatchers.IO) {
            check(preferences.edit().remove(KEY_ACCESS_TOKEN).commit()) {
                "Failed to clear access token from encrypted storage."
            }
        }
    }

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

        fun encryptedPreferencesFile(context: Context): File =
            File(context.applicationInfo.dataDir, "shared_prefs/$PREFERENCES_NAME.xml")
    }
}

class InMemorySecureTokenStore : SecureTokenStore {
    private var accessToken: String? = null

    override suspend fun readAccessToken(): String? = accessToken

    override suspend fun saveAccessToken(token: String) {
        accessToken = token
    }

    override suspend fun clear() {
        accessToken = null
    }
}
