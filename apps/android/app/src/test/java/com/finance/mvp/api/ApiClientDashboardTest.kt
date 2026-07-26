package com.finance.mvp.api

import com.finance.mvp.session.InMemorySecureTokenStore
import java.net.ServerSocket
import java.util.Collections
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientDashboardTest {
    @Test
    fun dashboardUsesSummaryInvestmentsInsteadOfAccountBalanceInvestments() = runBlocking {
        withScriptedJsonServer(
            *dashboardResponses(
                summaryBody = """
                    {
                      "data": {
                        "totalsByCurrency": [
                          {
                            "currency": "RUB",
                            "incomeTotal": "0.00",
                            "expenseTotal": "0.00",
                            "netTotal": "0.00",
                            "investmentsTotal": "250.00"
                          }
                        ]
                      }
                    }
                """.trimIndent(),
                accountBalancesBody = accountBalancesWithInvestments("12345.67"),
            ),
        ) { baseUrl, requests ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.dashboard("2026-07-01", "2026-07-31")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val dashboard = (result as ApiResult.Success).value
            assertEquals("250.00", dashboard.investmentsByCurrency.single().amount)
            assertEquals("RUB", dashboard.investmentsTotal?.currency)
            assertEquals("250.00", dashboard.investmentsTotal?.amount)
            assertTrue(requests.any { it.contains("/api/v1/reports/account-balances") })
        }
    }

    @Test
    fun dashboardDoesNotFallbackToAccountBalanceInvestmentsWhenSummaryInvestmentsAreMissing() = runBlocking {
        withScriptedJsonServer(
            *dashboardResponses(
                summaryBody = """{"data": {"totalsByCurrency": []}}""",
                accountBalancesBody = accountBalancesWithInvestments("12345.67"),
            ),
        ) { baseUrl, _ ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.dashboard("2026-07-01", "2026-07-31")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val dashboard = (result as ApiResult.Success).value
            assertTrue(dashboard.investmentsByCurrency.isEmpty())
            assertNull(dashboard.investmentsTotal)
        }
    }

    @Test
    fun dashboardDoesNotFallbackToAccountBalanceInvestmentsWhenSummaryInvestmentsAreZero() = runBlocking {
        withScriptedJsonServer(
            *dashboardResponses(
                summaryBody = """
                    {
                      "data": {
                        "totalsByCurrency": [
                          {
                            "currency": "RUB",
                            "incomeTotal": "0.00",
                            "expenseTotal": "0.00",
                            "netTotal": "0.00",
                            "investmentsTotal": "0.00"
                          }
                        ]
                      }
                    }
                """.trimIndent(),
                accountBalancesBody = accountBalancesWithInvestments("12345.67"),
            ),
        ) { baseUrl, _ ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.dashboard("2026-07-01", "2026-07-31")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val dashboard = (result as ApiResult.Success).value
            assertEquals("0.00", dashboard.investmentsByCurrency.single().amount)
            assertEquals("RUB", dashboard.investmentsTotal?.currency)
            assertEquals("0.00", dashboard.investmentsTotal?.amount)
        }
    }

    private data class ScriptedJsonResponse(
        val statusCode: Int = 200,
        val body: String,
    )

    private fun dashboardResponses(
        summaryBody: String,
        accountBalancesBody: String,
    ): Array<ScriptedJsonResponse> = arrayOf(
        ScriptedJsonResponse(
            body = """
                {
                  "data": {
                    "actor": {
                      "id": "user-1",
                      "displayName": "User",
                      "memberships": []
                    }
                  }
                }
            """.trimIndent(),
        ),
        ScriptedJsonResponse(
            body = """
                {
                  "items": [
                    {
                      "id": "acc-card",
                      "name": "Card",
                      "accountType": "card",
                      "ownershipType": "personal",
                      "currency": "RUB",
                      "currentBalance": "100.00"
                    }
                  ]
                }
            """.trimIndent(),
        ),
        ScriptedJsonResponse(body = """{"items": []}"""),
        ScriptedJsonResponse(body = """{"items": []}"""),
        ScriptedJsonResponse(body = """{"items": []}"""),
        ScriptedJsonResponse(body = summaryBody),
        ScriptedJsonResponse(body = accountBalancesBody),
    )

    private fun accountBalancesWithInvestments(amount: String): String = """
        {
          "data": {
            "assetCategoryGroups": [],
            "investmentsTotal": {
              "currency": "RUB",
              "amount": "$amount"
            },
            "investmentsByCurrency": [
              {
                "currency": "RUB",
                "amount": "$amount"
              }
            ]
          }
        }
    """.trimIndent()

    private suspend fun withScriptedJsonServer(
        vararg responses: ScriptedJsonResponse,
        block: suspend (String, List<String>) -> Unit,
    ) {
        val capturedRequests = Collections.synchronizedList(mutableListOf<String>())
        val server = ServerSocket(0)
        val serverThread = Thread {
            runCatching {
                responses.forEach { responseSpec ->
                    server.accept().use { socket ->
                        val request = socket.getInputStream().readHttpRequest()
                        capturedRequests.add(request)
                        val response = responseSpec.body.toByteArray(Charsets.UTF_8)
                        val headers = buildString {
                            append("HTTP/1.1 ${responseSpec.statusCode} Test\r\n")
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
            }
        }.apply { start() }
        try {
            block("http://127.0.0.1:${server.localPort}", capturedRequests)
        } finally {
            server.close()
            serverThread.join(1_000)
        }
    }

    private fun java.io.InputStream.readHttpRequest(): String {
        val headerBytes = mutableListOf<Byte>()
        var previous = 0
        var current = read()
        while (current != -1) {
            headerBytes.add(current.toByte())
            if (previous == '\r'.code && current == '\n'.code) {
                val headerText = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                if (headerText.endsWith("\r\n\r\n")) {
                    break
                }
            }
            previous = current
            current = read()
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
        var bytesRead = 0
        while (bytesRead < contentLength) {
            val count = read(bodyBytes, bytesRead, contentLength - bytesRead)
            if (count == -1) break
            bytesRead += count
        }
        return headerText + bodyBytes.toString(Charsets.UTF_8)
    }
}
