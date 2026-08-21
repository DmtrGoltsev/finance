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

    @Test
    fun dashboardUsesPersonalScopeAndFiltersSharedEntitiesWhenMembershipExists() = runBlocking {
        withScriptedJsonServer(
            ScriptedJsonResponse(body = """{"data":{"actor":{"id":"user-1","memberships":[{"householdId":"household-1","status":"active"}]}}}"""),
            ScriptedJsonResponse(body = """{"items":[{"id":"acc-personal","name":"Card","accountType":"card","ownershipType":"personal","currency":"RUB","currentBalance":"100.00"},{"id":"acc-shared","name":"Shared","accountType":"bank","ownershipType":"shared","householdId":"household-1","currency":"RUB","currentBalance":"900.00"}]}"""),
            ScriptedJsonResponse(body = """{"items":[{"id":"cat-personal","name":"Food","type":"expense","scope":"personal"},{"id":"cat-shared","name":"Home","type":"expense","scope":"household","householdId":"household-1"}]}"""),
            ScriptedJsonResponse(body = """{"items":[{"id":"asset-personal","name":"Broker","scopeType":"personal","currency":"RUB","manualAmount":"0"},{"id":"asset-shared","name":"Shared broker","scopeType":"household","householdId":"household-1","currency":"RUB","manualAmount":"0"}]}"""),
            ScriptedJsonResponse(body = """{"items":[{"id":"tx-personal","transactionType":"expense","accountId":"acc-personal","categoryId":"cat-personal","amount":"10.00","currency":"RUB","transactionDate":"2026-07-01"},{"id":"tx-shared","transactionType":"expense","accountId":"acc-shared","categoryId":"cat-shared","amount":"20.00","currency":"RUB","transactionDate":"2026-07-01"}]}"""),
            ScriptedJsonResponse(body = """{"data":{"totalsByCurrency":[]}}"""),
            ScriptedJsonResponse(body = """{"data":{"assetCategoryGroups":[]}}"""),
            ScriptedJsonResponse(body = """{"data":{"items":[]}}"""),
        ) { baseUrl, requests ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.dashboard("2026-07-01", "2026-07-31")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val dashboard = (result as ApiResult.Success).value
            assertEquals(listOf("acc-personal"), dashboard.accounts.map { it.id })
            assertEquals(listOf("cat-personal"), dashboard.categories.map { it.id })
            assertEquals(listOf("asset-personal"), dashboard.assetCategories.map { it.id })
            assertEquals(listOf("tx-personal"), dashboard.transactions.map { it.id })
            val reportRequests = requests.filter { it.contains("/api/v1/reports/") }
            assertTrue(reportRequests.isNotEmpty())
            assertTrue(reportRequests.all { it.contains("reportMode=personal") })
            assertTrue(reportRequests.none { it.contains("combined_viewer_overview") || it.contains("householdId=") })
        }
    }

    @Test
    fun dashboardPaginatesBeforePersonalFilteringAndKeepsMoreThanTwoHundredTransactions() = runBlocking {
        val responses = mutableListOf(
            ScriptedJsonResponse(
                body = """{"data":{"actor":{"id":"user-1","memberships":[]}}}""",
            ),
        )
        val sharedAccounts = (0 until 100).map { index ->
            """{"id":"shared-account-$index","name":"Shared $index","accountType":"card","ownershipType":"shared","householdId":"household-1","currency":"RUB","currentBalance":"9999.00"}"""
        }
        responses += ScriptedJsonResponse(body = pageBody(sharedAccounts, "100", true))
        responses += ScriptedJsonResponse(
            body = pageBody(
                listOf("""{"id":"personal-account","name":"Personal","accountType":"card","ownershipType":"personal","currency":"RUB","currentBalance":"100.00"}"""),
                null,
                false,
            ),
        )
        val sharedCategories = (0 until 100).map { index ->
            """{"id":"shared-category-$index","name":"Shared category $index","type":"expense","scope":"household","householdId":"household-1"}"""
        }
        responses += ScriptedJsonResponse(body = pageBody(sharedCategories, "100", true))
        responses += ScriptedJsonResponse(
            body = pageBody(
                listOf("""{"id":"personal-category","name":"Personal category","type":"expense","scope":"personal"}"""),
                null,
                false,
            ),
        )
        val sharedAssets = (0 until 100).map { index ->
            """{"id":"shared-asset-$index","name":"Shared asset $index","scopeType":"household","householdId":"household-1","currency":"RUB","manualAmount":"9999.00","isInvestment":false,"assetType":"other"}"""
        }
        responses += ScriptedJsonResponse(body = pageBody(sharedAssets, "100", true))
        responses += ScriptedJsonResponse(
            body = pageBody(
                listOf("""{"id":"personal-asset","name":"Personal asset","scopeType":"personal","currency":"RUB","manualAmount":"0","isInvestment":false,"assetType":"other"}"""),
                null,
                false,
            ),
        )
        val sharedTransactions = (0 until 100).map { index ->
            """{"id":"shared-tx-$index","transactionType":"expense","accountId":"shared-account-0","categoryId":"shared-category-0","amount":"9999.00","currency":"RUB","occurredAt":"2026-07-31T23:59:59Z","description":"SHARED SECRET $index"}"""
        }
        val personalTransactions = (0 until 201).map { index ->
            val occurredAt = java.time.Instant.parse("2026-07-01T00:00:00Z").plusSeconds(index.toLong())
            """{"id":"personal-tx-$index","transactionType":"expense","accountId":"personal-account","categoryId":"personal-category","amount":"1.00","currency":"RUB","occurredAt":"$occurredAt","description":"Personal $index"}"""
        }
        val allTransactions = sharedTransactions + personalTransactions
        allTransactions.chunked(100).forEachIndexed { index, page ->
            val nextOffset = (index + 1) * 100
            val hasMore = nextOffset < allTransactions.size
            responses += ScriptedJsonResponse(
                body = pageBody(page, nextOffset.toString().takeIf { hasMore }, hasMore),
            )
        }
        responses += ScriptedJsonResponse(body = """{"data":{"totalsByCurrency":[]}}""")
        responses += ScriptedJsonResponse(body = """{"data":{"assetCategoryGroups":[]}}""")
        responses += ScriptedJsonResponse(body = """{"data":{"items":[],"page":{"limit":100,"nextCursor":null,"hasMore":false}}}""")

        withScriptedJsonServer(*responses.toTypedArray()) { baseUrl, requests ->
            val client = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())

            val result = client.dashboard("2026-07-01", "2026-07-31")

            assertTrue("Expected success, got $result", result is ApiResult.Success)
            val dashboard = (result as ApiResult.Success).value
            assertEquals(listOf("personal-account"), dashboard.accounts.map { it.id })
            assertEquals(listOf("personal-category"), dashboard.categories.map { it.id })
            assertEquals(listOf("personal-asset"), dashboard.assetCategories.map { it.id })
            assertEquals(201, dashboard.transactions.size)
            assertEquals("personal-tx-200", dashboard.transactions.first().id)
            assertTrue(dashboard.transactions.none { it.description?.contains("SHARED SECRET") == true })
            assertTrue(requests.any { it.contains("/api/v1/accounts?ownershipType=personal") && it.contains("cursor=100") })
            assertTrue(requests.any { it.contains("/api/v1/transactions?ownershipType=personal") && it.contains("cursor=300") })
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
        ScriptedJsonResponse(body = """{"data": {"items": []}}"""),
    )

    private fun pageBody(items: List<String>, nextCursor: String?, hasMore: Boolean): String {
        val cursor = nextCursor?.let { "\"$it\"" } ?: "null"
        return """{"items":[${items.joinToString(",")}],"page":{"limit":100,"nextCursor":$cursor,"hasMore":$hasMore}}"""
    }

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
