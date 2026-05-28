package com.finance.mvp.api

import com.finance.mvp.session.InMemorySecureTokenStore
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientCaptureDraftTest {
    @Test
    fun createCaptureDraftPostsOnlyStructuredFields() = runBlocking {
        withJsonCaptureServer(
            statusCode = 201,
            body = """
                {
                  "data": {
                    "id": "draft-1",
                    "status": "pending",
                    "amount": "12.34",
                    "currency": "USD",
                    "description": "Test Market",
                    "merchantName": "Test Market",
                    "capturedAt": "2026-05-23T10:00:00Z",
                    "occurredAt": "2026-05-23T10:00:00Z",
                    "captureSource": "screenshot",
                    "confidence": "0.9000",
                    "sourceAppPackage": "",
                    "sourceAppLabel": "Photo Picker",
                    "evidenceHash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "idempotencyKey": "capture-v1:test",
                    "accountId": "acc-card",
                    "categoryId": "cat-food",
                    "version": 1
                  }
                }
            """.trimIndent(),
        ) { baseUrl, capturedRequest ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.createCaptureDraft(
                CaptureDraftCreateRequest(
                    amount = "12.34",
                    currency = "USD",
                    description = "Test Market",
                    merchantName = "Test Market",
                    capturedAt = "2026-05-23T10:00:00Z",
                    occurredAt = "2026-05-23T10:00:00Z",
                    captureSource = "screenshot",
                    idempotencyKey = "capture-v1:test",
                    confidence = 0.9,
                    sourceAppPackage = null,
                    sourceAppLabel = "Photo Picker",
                    evidenceHash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                ),
            )

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val request = capturedRequest.get()
            val requestLine = request.lineSequence().first()
            assertTrue("Unexpected request line: $requestLine", requestLine.startsWith("POST "))
            assertTrue("Unexpected request line: $requestLine", requestLine.contains("/api/v1/capture-drafts"))
            val json = JSONObject(request.substringAfter("\r\n\r\n"))
            assertEquals("12.34", json.getString("amount"))
            assertEquals("screenshot", json.getString("captureSource"))
            assertEquals("0.9000", json.getString("confidence"))
            listOf(
                "rawBody",
                "rawText",
                "rawImage",
                "rawOcrText",
                "messageText",
            ).forEach { key ->
                assertFalse("Request must not include $key", json.has(key))
            }
            assertFalse(json.toString().contains("Paid 12.34 USD at Test Market"))
        }
    }

    @Test
    fun updateCaptureDraftPayloadIncludesAccountCategoryAndDecimalConfidence() {
        val json = CaptureDraftUpdateRequest(
            confidence = 0.87654,
            accountId = "acc-card",
            categoryId = "cat-food",
        ).toJsonForApi()

        assertEquals("0.8765", json.getString("confidence"))
        assertEquals("acc-card", json.getString("accountId"))
        assertEquals("cat-food", json.getString("categoryId"))
        listOf(
            "rawImage",
            "rawOcrText",
                "messageText",
            ).forEach { key ->
            assertFalse("Request must not include $key", json.has(key))
        }
    }

    @Test
    fun confirmCaptureDraftParsesCaptureDraftEnvelope() = runBlocking {
        withJsonCaptureServer(
            statusCode = 200,
            body = captureDraftEnvelope(status = "confirmed"),
        ) { baseUrl, capturedRequest ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.confirmCaptureDraft("draft-1")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val draft = (result as ApiResult.Success).value
            assertEquals("draft-1", draft.id)
            assertEquals("confirmed", draft.status)
            assertEquals("acc-card", draft.accountId)
            assertEquals("cat-food", draft.categoryId)
            val requestLine = capturedRequest.get().lineSequence().first()
            assertTrue("Unexpected request line: $requestLine", requestLine.startsWith("POST "))
            assertTrue("Unexpected request line: $requestLine", requestLine.contains("/api/v1/capture-drafts/draft-1/confirm"))
        }
    }

    private fun captureDraftEnvelope(status: String): String {
        return """
            {
              "data": {
                "id": "draft-1",
                "status": "$status",
                "amount": "12.34",
                "currency": "USD",
                "description": "Test Market",
                "merchantName": "Test Market",
                "capturedAt": "2026-05-23T10:00:00Z",
                "occurredAt": "2026-05-23T10:00:00Z",
                "captureSource": "screenshot",
                "confidence": "0.9000",
                "sourceAppPackage": "",
                "sourceAppLabel": "Photo Picker",
                "evidenceHash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "idempotencyKey": "capture-v1:test",
                "accountId": "acc-card",
                "categoryId": "cat-food",
                "version": 1
              }
            }
        """.trimIndent()
    }

    private suspend fun withJsonCaptureServer(
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
