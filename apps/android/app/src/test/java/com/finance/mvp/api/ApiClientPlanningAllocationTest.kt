package com.finance.mvp.api

import com.finance.mvp.session.InMemorySecureTokenStore
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientPlanningAllocationTest {
    @Test
    fun createPlanningAllocationPostsAssetTargetTypeAndParsesAssetIdFallback() = runBlocking {
        withJsonPlanningServer(
            statusCode = 201,
            body = """
                {
                  "data": {
                    "id": "alloc-1",
                    "planId": "plan-1",
                    "targetType": "asset",
                    "assetId": "asset-broker",
                    "targetSnapshot": "Brokerage",
                    "requiresAttention": false,
                    "comment": "Invest",
                    "allocationMode": "amount",
                    "allocationValue": "100.00",
                    "calculatedAmount": "100.00",
                    "version": 1
                  }
                }
            """.trimIndent(),
        ) { baseUrl, capturedRequest ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.createPlanningAllocation(
                planId = "plan-1",
                request = PlanningAllocationCreateRequest(
                    targetType = "asset",
                    targetId = "asset-broker",
                    comment = "Invest",
                    allocationMode = "amount",
                    allocationValue = "100.00",
                ),
            )

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val allocation = (result as ApiResult.Success).value
            assertEquals("asset", allocation.targetType)
            assertEquals("asset-broker", allocation.targetId)

            val request = capturedRequest.get()
            val requestLine = request.lineSequence().first()
            assertTrue("Unexpected request line: $requestLine", requestLine.startsWith("POST "))
            assertTrue("Unexpected request line: $requestLine", requestLine.contains("/api/v1/planning/plans/plan-1/allocations"))
            val json = JSONObject(request.substringAfter("\r\n\r\n"))
            assertEquals("asset", json.getString("targetType"))
            assertEquals("asset-broker", json.getString("targetId"))
        }
    }

    @Test
    fun updatePlanningAllocationPayloadAllowsAssetTargetType() {
        val json = PlanningAllocationUpdateRequest(
            targetType = "asset",
            targetId = "asset-metal",
            allocationMode = "percent",
            allocationValue = "15.00",
            version = 2,
        ).toJsonForApi()

        assertEquals("asset", json.getString("targetType"))
        assertEquals("asset-metal", json.getString("targetId"))
        assertEquals("percent", json.getString("allocationMode"))
        assertEquals("15.00", json.getString("allocationValue"))
        assertEquals(2, json.getInt("version"))
    }

    private suspend fun withJsonPlanningServer(
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
