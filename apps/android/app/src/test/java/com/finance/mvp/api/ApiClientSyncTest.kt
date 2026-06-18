package com.finance.mvp.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class ApiClientSyncTest {
    @Test
    fun syncPushRequestSerializesBackendContractFields() {
        val json = SyncPushRequest(
            deviceId = "android-test-device",
            mutations = listOf(
                SyncMutationRequest(
                    clientMutationId = "mutation-1",
                    entityType = "transactions",
                    entityId = "11111111-1111-4111-8111-111111111111",
                    operation = "create",
                    payload = JSONObject()
                        .put("transactionType", "expense")
                        .put("accountId", "acc-1")
                        .put("amount", "12.3400")
                        .put("currency", "RUB")
                        .put("transactionDate", "2026-06-14")
                        .put("sourceType", "manual"),
                ),
            ),
        ).toJsonForApi()

        assertEquals("android-test-device", json.getString("deviceId"))
        assertEquals(ANDROID_SYNC_SCHEMA_VERSION, json.getInt("clientSchemaVersion"))
        val mutation = json.getJSONArray("mutations").getJSONObject(0)
        assertEquals("mutation-1", mutation.getString("clientMutationId"))
        assertEquals("transactions", mutation.getString("entityType"))
        assertEquals("create", mutation.getString("operation"))
        assertFalse(mutation.has("baseVersion"))
        assertEquals("manual", mutation.getJSONObject("payload").getString("sourceType"))
    }

    @Test
    fun syncPullRequestSerializesCursorLimitAndEntityTypes() {
        val json = SyncPullRequest(
            deviceId = "android-test-device",
            cursor = 42,
            limit = 25,
            entityTypes = listOf("transactions"),
        ).toJsonForApi()

        assertEquals(42, json.getLong("cursor"))
        assertEquals(25, json.getInt("limit"))
        assertEquals("transactions", json.getJSONArray("entityTypes").getString(0))
    }
}
