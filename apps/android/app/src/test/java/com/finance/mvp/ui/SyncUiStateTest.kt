package com.finance.mvp.ui

import com.finance.mvp.api.ApiFailureKind
import com.finance.mvp.api.ApiResult
import java.io.IOException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncUiStateTest {
    @Test
    fun idleStateDoesNotRenderAttention() {
        assertNull(syncAttention(SyncUiState()))
    }

    @Test
    fun savedOfflinePendingStateHasOfflineAttention() {
        val attention = syncAttention(SyncUiState(pendingCount = 2, savedOffline = true))

        assertEquals(SyncAttentionType.Offline, attention?.type)
        assertTrue(attention?.label.orEmpty().contains("2"))
    }

    @Test
    fun failedStateWinsOverPendingState() {
        val attention = syncAttention(SyncUiState(pendingCount = 1, failedCount = 1, savedOffline = true))

        assertEquals(SyncAttentionType.Failed, attention?.type)
        assertTrue(attention?.actionDescription.orEmpty().isNotBlank())
    }

    @Test
    fun syncingStateWinsOverFailedState() {
        val attention = syncAttention(SyncUiState(pendingCount = 1, failedCount = 1, isSyncing = true))

        assertEquals(SyncAttentionType.Syncing, attention?.type)
    }

    @Test
    fun networkFailureWithoutStatusIsRetriableForOfflineQueue() {
        val failure = ApiResult.Failure("offline", IOException("socket closed"))

        assertEquals(ApiFailureKind.NETWORK, failure.kind)
        assertTrue(failure.isRetriableForOfflineQueue())
    }

    @Test
    fun contractFailureWithoutStatusIsNotRetriableForOfflineQueue() {
        val failure = ApiResult.Failure(
            message = "API response did not match expected contract",
            cause = IllegalStateException("missing id"),
        )

        assertEquals(ApiFailureKind.CONTRACT, failure.kind)
        assertFalse(failure.isRetriableForOfflineQueue())
    }

    @Test
    fun unknownFailureWithoutStatusIsNotRetriableForOfflineQueue() {
        val failure = ApiResult.Failure(
            message = "unexpected failure",
            cause = RuntimeException("boom"),
            kind = ApiFailureKind.UNKNOWN,
        )

        assertFalse(failure.isRetriableForOfflineQueue())
    }

    @Test
    fun validationAndAuthenticationFailuresAreNotRetriableForOfflineQueue() {
        listOf(400, 401, 403, 409, 422).forEach { statusCode ->
            val failure = ApiResult.Failure("client error", statusCode = statusCode)

            assertEquals(ApiFailureKind.HTTP, failure.kind)
            assertFalse("Expected HTTP $statusCode to be non-retriable", failure.isRetriableForOfflineQueue())
        }
    }

    @Test
    fun timeoutRateLimitAndServerFailuresAreRetriableForOfflineQueue() {
        listOf(408, 429, 500, 502, 503, 504).forEach { statusCode ->
            val failure = ApiResult.Failure("temporary server error", statusCode = statusCode)

            assertEquals(ApiFailureKind.HTTP, failure.kind)
            assertTrue("Expected HTTP $statusCode to be retriable", failure.isRetriableForOfflineQueue())
        }
    }

    @Test
    fun syncIssueLabelsAreLocalized() {
        assertEquals("Операция", syncIssueEntityLabel("transactions"))
        assertEquals("Изменение", syncIssueOperationLabel("update"))
        assertEquals("Отклонено сервером", syncIssueStatusLabel("rejected"))
    }

    @Test
    fun syncIssueSafeErrorHidesPayloadLikeDetails() {
        val message = syncIssueSafeError("""{"amount":"1000.00","note":"private"}""")

        assertTrue(message.contains("Подробности скрыты"))
        assertFalse(message.contains("1000.00"))
        assertFalse(message.contains("private"))
    }

    @Test
    fun syncIssueSafeErrorKeepsConciseTechnicalReason() {
        assertEquals("temporary server error", syncIssueSafeError("temporary server error"))
        assertEquals("Причина не указана.", syncIssueSafeError("   "))
    }
}
