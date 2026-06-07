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
    fun createPlanningAllocationPostsInvestmentAssetCategoryTargetTypeAndParsesAssetCategoryFallback() = runBlocking {
        withJsonPlanningServer(
            statusCode = 201,
            body = """
                {
                  "data": {
                    "id": "alloc-1",
                    "planId": "plan-1",
                    "targetType": "investment_asset_category",
                    "assetCategoryId": "asset-cat-broker",
                    "targetSnapshot": "Brokerage",
                    "requiresAttention": false,
                    "comment": "Invest",
                    "allocationMode": "amount",
                    "allocationValue": "100.00",
                    "calculatedAmount": "100.00",
                    "recurrenceType": "regular",
                    "isSavingsGoal": false,
                    "actualAmount": "0.00",
                    "varianceAmount": "-100.00",
                    "status": "no_actuals",
                    "version": 1
                  }
                }
            """.trimIndent(),
        ) { baseUrl, capturedRequest ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.createPlanningAllocation(
                planId = "plan-1",
                request = PlanningAllocationCreateRequest(
                    targetType = "investment_asset_category",
                    targetId = "asset-cat-broker",
                    comment = "Invest",
                    allocationMode = "amount",
                    allocationValue = "100.00",
                    recurrenceType = "regular",
                ),
            )

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val allocation = (result as ApiResult.Success).value
            assertEquals("investment_asset_category", allocation.targetType)
            assertEquals("asset-cat-broker", allocation.targetId)

            val request = capturedRequest.get()
            val requestLine = request.lineSequence().first()
            assertTrue("Unexpected request line: $requestLine", requestLine.startsWith("POST "))
            assertTrue("Unexpected request line: $requestLine", requestLine.contains("/api/v1/planning/plans/plan-1/allocations"))
            val json = JSONObject(request.substringAfter("\r\n\r\n"))
            assertEquals("investment_asset_category", json.getString("targetType"))
            assertEquals("asset-cat-broker", json.getString("targetId"))
            assertEquals("regular", json.getString("recurrenceType"))
            assertEquals(false, json.getBoolean("isSavingsGoal"))
        }
    }

    @Test
    fun getPlanningPlanParsesPreviousMonthSurplusAndAllocationVariance() = runBlocking {
        withJsonPlanningServer(
            statusCode = 200,
            body = """
                {
                  "data": {
                    "id": "plan-1",
                    "scope": "personal",
                    "month": "2026-06",
                    "currency": "RUB",
                    "summary": {
                      "totalPlannedIncome": "1000.0000",
                      "totalConfirmedIncome": "1000.0000",
                      "totalAllocatedAmount": "850.0000",
                      "unallocatedAmount": "150.0000",
                      "previousMonthSurplus": "75.0000",
                      "underallocated": true,
                      "overallocated": false
                    },
                    "incomeSources": [],
                    "allocations": [
                      {
                        "id": "alloc-1",
                        "planId": "plan-1",
                        "targetType": "expense_category",
                        "targetId": "cat-food",
                        "targetSnapshot": {"name": "Food"},
                        "requiresAttention": false,
                        "allocationMode": "amount",
                        "allocationValue": "250.0000",
                        "calculatedAmount": "250.0000",
                        "recurrenceType": "regular",
                        "isSavingsGoal": false,
                        "actualAmount": "270.0000",
                        "varianceAmount": "20.0000",
                        "status": "needs_attention",
                        "version": 3
                      }
                    ],
                    "version": 4
                  }
                }
            """.trimIndent(),
        ) { baseUrl, _ ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.getPlanningPlan("plan-1")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val plan = (result as ApiResult.Success).value
            assertEquals("75.0000", plan.previousMonthSurplus)
            val allocation = plan.allocations.single()
            assertEquals("20.0000", allocation.varianceAmount)
        }
    }

    @Test
    fun updatePlanningAllocationPayloadAllowsInvestmentAssetCategoryRecurrenceAndGoalFields() {
        val json = PlanningAllocationUpdateRequest(
            targetType = "investment_asset_category",
            targetId = "asset-cat-metal",
            allocationMode = "percent",
            allocationValue = "15.00",
            recurrenceType = "one_off",
            isSavingsGoal = true,
            goalTargetAmount = "5000.00",
            goalDueMonth = "2026-12",
            version = 2,
        ).toJsonForApi()

        assertEquals("investment_asset_category", json.getString("targetType"))
        assertEquals("asset-cat-metal", json.getString("targetId"))
        assertEquals("percent", json.getString("allocationMode"))
        assertEquals("15.00", json.getString("allocationValue"))
        assertEquals("one_off", json.getString("recurrenceType"))
        assertEquals(true, json.getBoolean("isSavingsGoal"))
        assertEquals("5000.00", json.getString("goalTargetAmount"))
        assertEquals("2026-12", json.getString("goalDueMonth"))
        assertEquals(2, json.getInt("version"))
    }

    @Test
    fun updatePlanningAllocationPayloadClearsGoalFieldsWhenSavingsGoalDisabled() {
        val json = PlanningAllocationUpdateRequest(
            isSavingsGoal = false,
            version = 3,
        ).toJsonForApi()

        assertEquals(false, json.getBoolean("isSavingsGoal"))
        assertTrue(json.has("goalTargetAmount"))
        assertTrue(json.isNull("goalTargetAmount"))
        assertTrue(json.has("goalDueMonth"))
        assertTrue(json.isNull("goalDueMonth"))
        assertEquals(3, json.getInt("version"))
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
