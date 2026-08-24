package com.finance.mvp.api

import com.finance.mvp.session.InMemorySecureTokenStore
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientRegistrationTest {
    @Test
    fun registerPostsAndroidBearerPayloadAndStoresAccessToken() = runBlocking {
        withJsonRegistrationServer(
            statusCode = 201,
            body = """
                {
                  "accessToken": "registered-token",
                  "refreshToken": "registered-refresh-token",
                  "tokenType": "Bearer",
                  "expiresAt": "2026-05-26T12:00:00Z",
                  "actor": {
                    "userId": "user-registered",
                    "sessionId": "session-registered",
                    "memberships": [
                      {"householdId": "household-1", "status": "active"}
                    ]
                  }
                }
            """.trimIndent(),
        ) { baseUrl, capturedRequest ->
            val tokenStore = InMemorySecureTokenStore()
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)

            val result = client.register(
                email = "finance.qa@local.test",
                password = "typed-password",
                displayName = "Finance QA",
            )

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val registration = (result as ApiResult.Success).value
            assertTrue(
                "Expected authenticated result, got $registration",
                registration is RegistrationResult.Authenticated,
            )
            val session = (registration as RegistrationResult.Authenticated).session
            assertTrue("Expected session in authenticated result", session != null)
            session ?: return@withJsonRegistrationServer
            assertTrue(session.isAuthenticated)
            assertEquals("household-1", session.householdId)
            assertEquals("registered-token", tokenStore.readAccessToken())
            assertEquals("registered-refresh-token", tokenStore.readRefreshToken())
            assertEquals("user-registered", tokenStore.readSession()?.authenticatedUserId)

            val request = capturedRequest.get()
            val requestLine = request.lineSequence().first()
            assertTrue("Unexpected request line: $requestLine", requestLine.startsWith("POST "))
            assertTrue("Unexpected request line: $requestLine", requestLine.contains("/api/v1/users"))
            val json = JSONObject(request.substringAfter("\r\n\r\n"))
            assertEquals("finance.qa@local.test", json.getString("email"))
            assertEquals("typed-password", json.getString("password"))
            assertEquals("Finance QA", json.getString("displayName"))
            assertEquals("android_bearer", json.getString("transport"))
        }
    }

    @Test
    fun registerOmitsBlankDisplayName() = runBlocking {
        withJsonRegistrationServer(
            statusCode = 201,
            body = """
                {
                  "accessToken": "registered-token",
                  "refreshToken": "registered-refresh-token",
                  "tokenType": "Bearer",
                  "expiresAt": "2026-05-26T12:00:00Z",
                  "actor": {"userId": "user-registered", "memberships": []}
                }
            """.trimIndent(),
        ) { baseUrl, capturedRequest ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.register(
                email = "finance.qa@local.test",
                password = "typed-password",
                displayName = "  ",
            )

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val json = JSONObject(capturedRequest.get().substringAfter("\r\n\r\n"))
            assertFalse(json.has("displayName"))
        }
    }

    @Test
    fun registerAcceptedClearsStaleTokenAndDoesNotAuthenticate() = runBlocking {
        withJsonRegistrationServer(
            statusCode = 202,
            body = """
                {
                  "registrationAccepted": true,
                  "message": "Registration request accepted",
                  "requestId": "req-accepted"
                }
            """.trimIndent(),
        ) { baseUrl, capturedRequest ->
            val tokenStore = InMemorySecureTokenStore()
            tokenStore.saveAccessToken("old-restored-token")
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)

            val result = client.register(
                email = "existing.qa@local.test",
                password = "typed-password",
                displayName = null,
            )

            assertTrue("Expected accepted result, got $result", result is ApiResult.Success)
            val registration = (result as ApiResult.Success).value
            assertTrue("Expected accepted result, got $registration", registration is RegistrationResult.Accepted)
            assertEquals("Registration request accepted", (registration as RegistrationResult.Accepted).message)
            assertNull(tokenStore.readAccessToken())
            assertNull(tokenStore.readRefreshToken())

            val json = JSONObject(capturedRequest.get().substringAfter("\r\n\r\n"))
            assertEquals("existing.qa@local.test", json.getString("email"))
            assertEquals("android_bearer", json.getString("transport"))
        }
    }

    private suspend fun withJsonRegistrationServer(
        statusCode: Int,
        body: String,
        block: suspend (String, AtomicReference<String>) -> Unit,
    ) {
        val capturedRequest = AtomicReference("")
        val server = ServerSocket(0)
        val serverThread = Thread {
            runCatching {
                server.accept().use { socket ->
                    val input = socket.getInputStream()
                    val headerBytes = mutableListOf<Byte>()
                    var previous = 0
                    var current = input.read()
                    while (current != -1) {
                        headerBytes.add(current.toByte())
                        if (previous == '\r'.code && current == '\n'.code) {
                            val headerText = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                            if (headerText.endsWith("\r\n\r\n")) {
                                break
                            }
                        }
                        previous = current
                        current = input.read()
                    }
                    val headerText = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                    val contentLength = headerText
                        .lineSequence()
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
                    capturedRequest.set(headerText + bodyBytes.toString(Charsets.UTF_8))

                    val response = body.toByteArray(Charsets.UTF_8)
                    val headers = buildString {
                        append("HTTP/1.1 $statusCode Test\r\n")
                        append("Content-Type: application/json\r\n")
                        append("Content-Length: ${response.size}\r\n")
                        append("Connection: close\r\n")
                        append("\r\n")
                    }.toByteArray(Charsets.US_ASCII)
                    socket.getOutputStream().use { output ->
                        output.write(headers)
                        output.write(response)
                    }
                }
            }
        }.apply { start() }
        try {
            block("http://127.0.0.1:${server.localPort}", capturedRequest)
        } finally {
            server.close()
            serverThread.join(1_000)
        }
    }
}
