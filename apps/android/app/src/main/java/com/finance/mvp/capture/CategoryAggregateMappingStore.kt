package com.finance.mvp.capture

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.MessageDigest
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

interface CategoryAggregateMappingStore {
    suspend fun readCategoryId(userContext: String, externalLabel: String): String?
    suspend fun saveCategoryId(userContext: String, externalLabel: String, categoryId: String)
}

class AndroidCategoryAggregateMappingStore(
    context: Context,
) : CategoryAggregateMappingStore {
    private val appContext = context.applicationContext
    private val preferences: SharedPreferences by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        createEncryptedPreferences(appContext)
    }

    override suspend fun readCategoryId(userContext: String, externalLabel: String): String? = withContext(Dispatchers.IO) {
        preferences.getString(mappingKey(userContext, externalLabel), null)
            ?.takeIf { it.isNotBlank() }
    }

    override suspend fun saveCategoryId(userContext: String, externalLabel: String, categoryId: String) {
        require(categoryId.isNotBlank()) { "Category id must not be blank." }
        withContext(Dispatchers.IO) {
            check(preferences.edit().putString(mappingKey(userContext, externalLabel), categoryId).commit()) {
                "Failed to persist category aggregate mapping."
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

    private companion object {
        const val PREFERENCES_NAME = "finance_secure_category_aggregate_mappings"
    }
}

object CategoryAggregateMappingKeys {
    fun normalizedExternalLabel(label: String): String {
        return label
            .lowercase(Locale("ru", "RU"))
            .replace('ё', 'е')
            .replace(Regex("""[^\p{L}\p{Nd}]+"""), " ")
            .replace(Regex("""\s+"""), " ")
            .trim()
            .take(120)
    }

    fun mappingKey(userContext: String, externalLabel: String): String {
        val normalizedContext = userContext
            .lowercase(Locale.US)
            .replace(Regex("""[^a-z0-9:_-]+"""), "-")
            .trim('-')
            .ifBlank { "anonymous" }
        val normalizedLabel = normalizedExternalLabel(externalLabel)
        return "category-aggregate:${sha256Hex("$normalizedContext|$normalizedLabel")}"
    }

    private fun sha256Hex(value: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }
}

private fun mappingKey(userContext: String, externalLabel: String): String {
    return CategoryAggregateMappingKeys.mappingKey(userContext, externalLabel)
}
