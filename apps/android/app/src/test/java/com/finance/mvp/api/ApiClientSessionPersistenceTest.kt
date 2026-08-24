package com.finance.mvp.api

import com.finance.mvp.session.InMemorySecureTokenStore
import java.io.InputStream
import java.io.OutputStream
import java.net.ServerSocket
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientSessionPersistenceTest {
    @Test
    fun recreatedClientRefreshesExpiredAccessTokenAndRestoresSession() = runBlocking {
        val responses = listOf(
            HttpResponse(
                statusCode = 201,
                body = bearerSessionJson("access-old", "refresh-old"),
            ),
            HttpResponse(statusCode = 401, body = """{"error":{"message":"expired"}}"""),
            HttpResponse(
                statusCode = 200,
                body = bearerSessionJson("access-new", "refresh-new"),
            ),
            HttpResponse(
                statusCode = 200,
                body = """{"actor":{"userId":"user-1","memberships":[]}}""",
            ),
        )

        withQueuedServer(responses) { baseUrl, requests ->
            val tokenStore = InMemorySecureTokenStore()
            val loginClient = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)
            assertTrue(loginClient.login("qa@example.test", "password") is ApiResult.Success)
            val loginGeneration = requireNotNull(tokenStore.readSession()).generation

            // A new client instance models process recreation while secure storage survives.
            val restoredClient = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)
            val restored = restoredClient.sessionStatus()

            assertTrue("Expected restored session, got $restored", restored is ApiResult.Success)
            assertEquals("user-1", (restored as ApiResult.Success).value.userId)
            assertEquals("access-new", tokenStore.readAccessToken())
            assertEquals("refresh-new", tokenStore.readRefreshToken())
            assertEquals(loginGeneration, tokenStore.readSession()?.generation)

            assertEquals(4, requests.size)
            assertTrue(requests[0].requestLine.contains("POST /api/v1/sessions "))
            assertEquals("Bearer access-old", requests[1].authorization)
            assertTrue(requests[2].requestLine.contains("POST /api/v1/sessions/refresh "))
            assertEquals("refresh-old", JSONObject(requests[2].body).getString("refreshToken"))
            assertEquals("Bearer access-new", requests[3].authorization)
        }
    }

    @Test
    fun logoutClearsLocalSessionEvenWhenServerIsUnavailable() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-token", "refresh-token")
        val loggedInGeneration = requireNotNull(tokenStore.readSession()).generation
        val closedPort = ServerSocket(0).use { it.localPort }
        val client = LiveFinanceApiClient(ApiConfig("http://127.0.0.1:$closedPort"), tokenStore)

        val result = client.logout()

        assertTrue(result is ApiResult.Failure)
        assertNull(tokenStore.readAccessToken())
        assertNull(tokenStore.readRefreshToken())
        tokenStore.saveSessionTokens("access-next", "refresh-next", "session-next")
        assertTrue(requireNotNull(tokenStore.readSession()).generation > loggedInGeneration)
    }

    @Test
    fun rejectedRefreshClearsPersistedSession() = runBlocking {
        val responses = listOf(
            HttpResponse(statusCode = 401, body = """{"error":{"message":"expired"}}"""),
            HttpResponse(statusCode = 401, body = """{"error":{"message":"invalid refresh"}}"""),
        )

        withQueuedServer(responses) { baseUrl, _ ->
            val tokenStore = InMemorySecureTokenStore()
            tokenStore.saveSessionTokens("access-old", "refresh-invalid")

            val result = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore).sessionStatus()

            assertTrue(result is ApiResult.Failure)
            assertNull(tokenStore.readAccessToken())
            assertNull(tokenStore.readRefreshToken())
        }
    }

    @Test
    fun transientRefreshFailureKeepsPersistedSessionForLaterRetry() = runBlocking {
        val responses = listOf(
            HttpResponse(statusCode = 401, body = """{"error":{"message":"expired"}}"""),
        )

        withQueuedServer(responses) { baseUrl, _ ->
            val tokenStore = InMemorySecureTokenStore()
            tokenStore.saveSessionTokens("access-old", "refresh-kept")

            val result = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore).sessionStatus()

            assertTrue(result is ApiResult.Failure)
            assertEquals("access-old", tokenStore.readAccessToken())
            assertEquals("refresh-kept", tokenStore.readRefreshToken())
        }
    }

    @Test
    fun twoClientsShareOneRefreshRotationWithoutClearingNewSession() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-old", "refresh-old", "user-1", "user-1")

        withConcurrentRefreshServer { baseUrl, refreshCalls ->
            val uiClient = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)
            val workerClient = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)

            val results = coroutineScope {
                listOf(
                    async(Dispatchers.IO) { uiClient.sessionStatus() },
                    async(Dispatchers.IO) { workerClient.sessionStatus() },
                ).awaitAll()
            }

            assertTrue(results.all { it is ApiResult.Success })
            assertEquals(1, refreshCalls.get())
            assertEquals("access-new", tokenStore.readAccessToken())
            assertEquals("refresh-new", tokenStore.readRefreshToken())
        }
    }

    @Test
    fun staleWorkerForUserADoesNotRetryRequestUnderNewUserBSession() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-a", "refresh-a", "session-a", "user-a")
        val userAGeneration = requireNotNull(tokenStore.readSession()).generation

        withUserSwitchServer { control ->
            val workerClient = LiveFinanceApiClient(ApiConfig(control.baseUrl), tokenStore)
            val loginClient = LiveFinanceApiClient(ApiConfig(control.baseUrl), tokenStore)
            val staleWorkerResult = async(Dispatchers.IO) { workerClient.sessionStatus() }

            assertTrue(control.staleRequestArrived.await(5, TimeUnit.SECONDS))
            val loginResult = loginClient.login("user-b@example.test", "password-b")
            assertTrue("Expected user B login success, got $loginResult", loginResult is ApiResult.Success)
            control.releaseStaleResponse.countDown()

            assertTrue(staleWorkerResult.await() is ApiResult.Failure)
            val current = tokenStore.readSession()
            assertEquals("access-b", current?.accessToken)
            assertEquals("refresh-b", current?.refreshToken)
            assertEquals("session-b", current?.sessionIdentity)
            assertTrue((current?.generation ?: 0L) > userAGeneration)
            assertEquals(0, control.refreshCalls.get())
            assertEquals(0, control.requestsAuthorizedAsUserB.get())
        }
    }

    @Test
    fun screenshotOcrRefreshesOnceAndRetriesUploadOnce() = runBlocking {
        val responses = listOf(
            HttpResponse(statusCode = 401, body = """{"error":{"message":"expired"}}"""),
            HttpResponse(statusCode = 200, body = bearerSessionJson("access-new", "refresh-new")),
            HttpResponse(statusCode = 200, body = """{"data":{"items":[]}}"""),
        )

        withQueuedServer(responses) { baseUrl, requests ->
            val tokenStore = InMemorySecureTokenStore()
            tokenStore.saveSessionTokens("access-old", "refresh-old", "user-1", "user-1")

            val result = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore).screenshotOcr(
                imageBytes = byteArrayOf(1, 2, 3, 4),
                contentType = "image/jpeg",
                capturedAt = "2026-08-22T10:00:00Z",
                householdId = null,
            )

            assertTrue("Expected OCR success, got $result", result is ApiResult.Success)
            assertEquals(3, requests.size)
            assertEquals(2, requests.count { it.requestLine.contains("/screenshot-ocr") })
            assertTrue(requests[1].requestLine.contains("/api/v1/sessions/refresh"))
            assertEquals("Bearer access-old", requests[0].authorization)
            assertEquals("Bearer access-new", requests[2].authorization)
        }
    }

    @Test
    fun legacyForegroundSessionBindsUserIdentityWithoutRequiringNewLogin() = runBlocking {
        val responses = listOf(
            HttpResponse(
                statusCode = 200,
                body = """{"actor":{"userId":"legacy-user","sessionId":"legacy-session","memberships":[]}}""",
            ),
        )

        withQueuedServer(responses) { baseUrl, _ ->
            val tokenStore = InMemorySecureTokenStore()
            tokenStore.saveAccessToken("legacy-access")
            val generation = requireNotNull(tokenStore.readSession()).generation

            val result = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore).sessionStatus()

            assertTrue(result is ApiResult.Success)
            val bound = requireNotNull(tokenStore.readSession())
            assertEquals(generation, bound.generation)
            assertEquals("legacy-user", bound.authenticatedUserId)
            assertEquals("legacy-session", bound.sessionIdentity)
            assertNull(bound.refreshToken)
        }
    }

    @Test
    fun lateLogoutForUserADoesNotClearConcurrentLoginForUserB() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-a", "refresh-a", "session-a", "user-a")

        withLateLogoutServer { control ->
            val logoutClient = LiveFinanceApiClient(ApiConfig(control.baseUrl), tokenStore)
            val loginClient = LiveFinanceApiClient(ApiConfig(control.baseUrl), tokenStore)
            val logoutResult = async(Dispatchers.IO) { logoutClient.logout() }

            assertTrue(control.logoutRequestArrived.await(5, TimeUnit.SECONDS))
            assertTrue(loginClient.login("user-b@example.test", "password-b") is ApiResult.Success)
            control.releaseLogoutResponse.countDown()

            val result = logoutResult.await()
            assertTrue(result is ApiResult.Failure)
            assertEquals(ApiFailureKind.SESSION_CHANGED, (result as ApiResult.Failure).kind)
            val current = requireNotNull(tokenStore.readSession())
            assertEquals("access-b", current.accessToken)
            assertEquals("refresh-b", current.refreshToken)
            assertEquals("session-b", current.sessionIdentity)
            assertEquals("user-b", current.authenticatedUserId)
        }
    }

    @Test
    fun sessionLeaseAllowsSameUserRefreshRotationAcrossSyncRetry() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-old", "refresh-old", "session-a", "user-a")
        val generation = requireNotNull(tokenStore.readSession()).generation
        val responses = listOf(
            HttpResponse(statusCode = 401, body = """{"error":{"message":"expired"}}"""),
            HttpResponse(
                statusCode = 200,
                body = bearerSessionJson("access-new", "refresh-new", "user-a", "session-a"),
            ),
            HttpResponse(
                statusCode = 200,
                body = """{"changes":[],"nextCursor":3,"hasMore":false,"serverTime":"2026-08-22T00:00:00Z"}""",
            ),
        )

        withQueuedServer(responses) { baseUrl, requests ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)
            val lease = (client.captureAuthenticatedSessionLease("user-a") as ApiResult.Success).value

            val result = client.syncPullWithLease(
                SyncPullRequest(deviceId = "device-a", cursor = 0, limit = 100, entityTypes = emptyList()),
                lease,
            )

            assertTrue(result is ApiResult.Success)
            assertEquals(3, (result as ApiResult.Success).value.nextCursor)
            assertEquals(3, requests.size)
            assertEquals("Bearer access-old", requests[0].authorization)
            assertTrue(requests[1].requestLine.contains("/api/v1/sessions/refresh"))
            assertEquals("Bearer access-new", requests[2].authorization)
            assertEquals(generation, tokenStore.readSession()?.generation)
            assertEquals("user-a", tokenStore.readSession()?.authenticatedUserId)
        }
    }

    @Test
    fun sessionLeaseRejectsSecondSyncRequestAfterUserSwitchWithoutNetworkCall() = runBlocking {
        val tokenStore = InMemorySecureTokenStore()
        tokenStore.saveSessionTokens("access-a", "refresh-a", "session-a", "user-a")
        val responses = listOf(
            HttpResponse(
                statusCode = 200,
                body = """{"deviceId":"device-a","serverTime":"2026-08-22T00:00:00Z","results":[]}""",
            ),
        )

        withQueuedServer(responses) { baseUrl, requests ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)
            val lease = (client.captureAuthenticatedSessionLease("user-a") as ApiResult.Success).value
            val push = client.syncPushWithLease(
                SyncPushRequest(deviceId = "device-a", mutations = emptyList()),
                lease,
            )
            assertTrue(push is ApiResult.Success)

            tokenStore.saveSessionTokens("access-b", "refresh-b", "session-b", "user-b")
            val pull = client.syncPullWithLease(
                SyncPullRequest(deviceId = "device-a", cursor = 0, limit = 100, entityTypes = emptyList()),
                lease,
            )

            assertTrue(pull is ApiResult.Failure)
            assertEquals(ApiFailureKind.SESSION_CHANGED, (pull as ApiResult.Failure).kind)
            assertEquals(1, requests.size)
            assertTrue(requests.single().requestLine.contains("/api/v1/sync/push"))
        }
    }

    private suspend fun withQueuedServer(
        responses: List<HttpResponse>,
        block: suspend (String, List<CapturedRequest>) -> Unit,
    ) {
        val requests = CopyOnWriteArrayList<CapturedRequest>()
        val server = ServerSocket(0)
        val serverThread = Thread {
            responses.forEach { response ->
                runCatching {
                    server.accept().use { socket ->
                        val input = socket.getInputStream()
                        val headerBytes = mutableListOf<Byte>()
                        var previous = 0
                        var current = input.read()
                        while (current != -1) {
                            headerBytes.add(current.toByte())
                            if (previous == '\r'.code && current == '\n'.code) {
                                val text = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                                if (text.endsWith("\r\n\r\n")) break
                            }
                            previous = current
                            current = input.read()
                        }
                        val headers = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                        val contentLength = headers.lineSequence()
                            .firstOrNull { it.startsWith("Content-Length:", ignoreCase = true) }
                            ?.substringAfter(":")
                            ?.trim()
                            ?.toIntOrNull()
                            ?: 0
                        val bodyBytes = ByteArray(contentLength)
                        var read = 0
                        while (read < contentLength) {
                            val count = input.read(bodyBytes, read, contentLength - read)
                            if (count == -1) break
                            read += count
                        }
                        requests += CapturedRequest(
                            requestLine = headers.lineSequence().first(),
                            authorization = headers.lineSequence()
                                .firstOrNull { it.startsWith("Authorization:", ignoreCase = true) }
                                ?.substringAfter(":")
                                ?.trim(),
                            body = bodyBytes.toString(Charsets.UTF_8),
                        )

                        val responseBytes = response.body.toByteArray(Charsets.UTF_8)
                        val reason = if (response.statusCode in 200..299) "OK" else "Error"
                        val responseHeaders = buildString {
                            append("HTTP/1.1 ${response.statusCode} $reason\r\n")
                            append("Content-Type: application/json\r\n")
                            append("Content-Length: ${responseBytes.size}\r\n")
                            append("Connection: close\r\n\r\n")
                        }.toByteArray(Charsets.US_ASCII)
                        socket.getOutputStream().use { output ->
                            output.write(responseHeaders)
                            output.write(responseBytes)
                        }
                    }
                }
            }
        }.apply { start() }
        try {
            block("http://127.0.0.1:${server.localPort}", requests)
        } finally {
            server.close()
            serverThread.join(1_000)
        }
    }

    private fun bearerSessionJson(
        accessToken: String,
        refreshToken: String,
        userId: String = "user-1",
        sessionId: String? = null,
    ): String = """
        {
          "accessToken": "$accessToken",
          "refreshToken": "$refreshToken",
          "tokenType": "Bearer",
          "expiresAt": "2026-08-23T00:00:00Z",
          "actor": {
            "userId": "$userId",
            ${sessionId?.let { "\"sessionId\": \"$it\"," }.orEmpty()}
            "memberships": []
          }
        }
    """.trimIndent()

    private suspend fun withConcurrentRefreshServer(
        block: suspend (String, AtomicInteger) -> Unit,
    ) {
        val oldAccessRequests = CountDownLatch(2)
        val refreshCalls = AtomicInteger()
        val executor = Executors.newFixedThreadPool(4)
        val server = ServerSocket(0)
        val acceptThread = Thread {
            while (!server.isClosed) {
                val socket = runCatching { server.accept() }.getOrNull() ?: break
                executor.submit {
                    socket.use {
                        val request = readCapturedRequest(it.getInputStream())
                        when {
                            request.requestLine.contains("/api/v1/sessions/current") &&
                                request.authorization == "Bearer access-old" -> {
                                oldAccessRequests.countDown()
                                if (!oldAccessRequests.await(5, TimeUnit.SECONDS)) {
                                    it.getOutputStream().respond(
                                        500,
                                        """{"error":{"message":"barrier timeout"}}""",
                                    )
                                } else {
                                    it.getOutputStream().respond(
                                        401,
                                        """{"error":{"message":"expired"}}""",
                                    )
                                }
                            }
                            request.requestLine.contains("/api/v1/sessions/current") &&
                                request.authorization == "Bearer access-new" -> {
                                it.getOutputStream().respond(
                                    200,
                                    """{"actor":{"userId":"user-1","memberships":[]}}""",
                                )
                            }
                            request.requestLine.contains("/api/v1/sessions/refresh") -> {
                                if (refreshCalls.incrementAndGet() == 1) {
                                    it.getOutputStream().respond(
                                        200,
                                        bearerSessionJson("access-new", "refresh-new"),
                                    )
                                } else {
                                    it.getOutputStream().respond(
                                        401,
                                        """{"error":{"message":"stale refresh"}}""",
                                    )
                                }
                            }
                            else -> it.getOutputStream().respond(
                                401,
                                """{"error":{"message":"unexpected token"}}""",
                            )
                        }
                    }
                }
            }
        }.apply {
            isDaemon = true
            start()
        }
        try {
            block("http://127.0.0.1:${server.localPort}", refreshCalls)
        } finally {
            server.close()
            acceptThread.join(1_000)
            executor.shutdownNow()
        }
    }

    private suspend fun withUserSwitchServer(block: suspend (UserSwitchControl) -> Unit) {
        val staleRequestArrived = CountDownLatch(1)
        val releaseStaleResponse = CountDownLatch(1)
        val refreshCalls = AtomicInteger()
        val requestsAuthorizedAsUserB = AtomicInteger()
        val executor = Executors.newFixedThreadPool(4)
        val server = ServerSocket(0)
        val acceptThread = Thread {
            while (!server.isClosed) {
                val socket = runCatching { server.accept() }.getOrNull() ?: break
                executor.submit {
                    socket.use {
                        val request = readCapturedRequest(it.getInputStream())
                        when {
                            request.requestLine.contains("POST /api/v1/sessions ") -> {
                                it.getOutputStream().respond(
                                    201,
                                    bearerSessionJson(
                                        accessToken = "access-b",
                                        refreshToken = "refresh-b",
                                        userId = "user-b",
                                        sessionId = "session-b",
                                    ),
                                )
                            }
                            request.requestLine.contains("/api/v1/sessions/current") &&
                                request.authorization == "Bearer access-a" -> {
                                staleRequestArrived.countDown()
                                if (releaseStaleResponse.await(5, TimeUnit.SECONDS)) {
                                    it.getOutputStream().respond(
                                        401,
                                        """{"error":{"message":"expired A"}}""",
                                    )
                                } else {
                                    it.getOutputStream().respond(500, "{}")
                                }
                            }
                            request.authorization == "Bearer access-b" -> {
                                requestsAuthorizedAsUserB.incrementAndGet()
                                it.getOutputStream().respond(
                                    200,
                                    """{"actor":{"userId":"user-b","sessionId":"session-b","memberships":[]}}""",
                                )
                            }
                            request.requestLine.contains("/api/v1/sessions/refresh") -> {
                                refreshCalls.incrementAndGet()
                                it.getOutputStream().respond(
                                    401,
                                    """{"error":{"message":"stale A refresh"}}""",
                                )
                            }
                            else -> it.getOutputStream().respond(400, "{}")
                        }
                    }
                }
            }
        }.apply {
            isDaemon = true
            start()
        }
        try {
            block(
                UserSwitchControl(
                    baseUrl = "http://127.0.0.1:${server.localPort}",
                    staleRequestArrived = staleRequestArrived,
                    releaseStaleResponse = releaseStaleResponse,
                    refreshCalls = refreshCalls,
                    requestsAuthorizedAsUserB = requestsAuthorizedAsUserB,
                ),
            )
        } finally {
            releaseStaleResponse.countDown()
            server.close()
            acceptThread.join(1_000)
            executor.shutdownNow()
        }
    }

    private suspend fun withLateLogoutServer(block: suspend (LateLogoutControl) -> Unit) {
        val logoutRequestArrived = CountDownLatch(1)
        val releaseLogoutResponse = CountDownLatch(1)
        val executor = Executors.newFixedThreadPool(3)
        val server = ServerSocket(0)
        val acceptThread = Thread {
            while (!server.isClosed) {
                val socket = runCatching { server.accept() }.getOrNull() ?: break
                executor.submit {
                    socket.use {
                        val request = readCapturedRequest(it.getInputStream())
                        when {
                            request.requestLine.contains("DELETE /api/v1/sessions/current ") &&
                                request.authorization == "Bearer access-a" -> {
                                logoutRequestArrived.countDown()
                                if (releaseLogoutResponse.await(5, TimeUnit.SECONDS)) {
                                    it.getOutputStream().respond(204, "")
                                } else {
                                    it.getOutputStream().respond(500, "{}")
                                }
                            }
                            request.requestLine.contains("POST /api/v1/sessions ") -> {
                                it.getOutputStream().respond(
                                    201,
                                    bearerSessionJson(
                                        accessToken = "access-b",
                                        refreshToken = "refresh-b",
                                        userId = "user-b",
                                        sessionId = "session-b",
                                    ),
                                )
                            }
                            else -> it.getOutputStream().respond(400, "{}")
                        }
                    }
                }
            }
        }.apply {
            isDaemon = true
            start()
        }
        try {
            block(
                LateLogoutControl(
                    baseUrl = "http://127.0.0.1:${server.localPort}",
                    logoutRequestArrived = logoutRequestArrived,
                    releaseLogoutResponse = releaseLogoutResponse,
                ),
            )
        } finally {
            releaseLogoutResponse.countDown()
            server.close()
            acceptThread.join(1_000)
            executor.shutdownNow()
        }
    }

    private fun readCapturedRequest(input: InputStream): CapturedRequest {
        val headerBytes = mutableListOf<Byte>()
        var previous = 0
        var current = input.read()
        while (current != -1) {
            headerBytes.add(current.toByte())
            if (previous == '\r'.code && current == '\n'.code) {
                val text = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                if (text.endsWith("\r\n\r\n")) break
            }
            previous = current
            current = input.read()
        }
        val headers = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
        val contentLength = headers.lineSequence()
            .firstOrNull { it.startsWith("Content-Length:", ignoreCase = true) }
            ?.substringAfter(":")
            ?.trim()
            ?.toIntOrNull()
            ?: 0
        val bodyBytes = ByteArray(contentLength)
        var read = 0
        while (read < contentLength) {
            val count = input.read(bodyBytes, read, contentLength - read)
            if (count == -1) break
            read += count
        }
        return CapturedRequest(
            requestLine = headers.lineSequence().first(),
            authorization = headers.lineSequence()
                .firstOrNull { it.startsWith("Authorization:", ignoreCase = true) }
                ?.substringAfter(":")
                ?.trim(),
            body = bodyBytes.toString(Charsets.UTF_8),
        )
    }

    private fun OutputStream.respond(statusCode: Int, body: String) {
        val bytes = body.toByteArray(Charsets.UTF_8)
        val reason = if (statusCode in 200..299) "OK" else "Error"
        val headers = buildString {
            append("HTTP/1.1 $statusCode $reason\r\n")
            append("Content-Type: application/json\r\n")
            append("Content-Length: ${bytes.size}\r\n")
            append("Connection: close\r\n\r\n")
        }.toByteArray(Charsets.US_ASCII)
        use { output ->
            output.write(headers)
            output.write(bytes)
        }
    }

    private data class HttpResponse(val statusCode: Int, val body: String)

    private data class CapturedRequest(
        val requestLine: String,
        val authorization: String?,
        val body: String,
    )

    private data class UserSwitchControl(
        val baseUrl: String,
        val staleRequestArrived: CountDownLatch,
        val releaseStaleResponse: CountDownLatch,
        val refreshCalls: AtomicInteger,
        val requestsAuthorizedAsUserB: AtomicInteger,
    )

    private data class LateLogoutControl(
        val baseUrl: String,
        val logoutRequestArrived: CountDownLatch,
        val releaseLogoutResponse: CountDownLatch,
    )
}
