package com.finance.mvp.api

import com.finance.mvp.session.InMemorySecureTokenStore
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientInvestmentContractTest {
    @Test
    fun createImportPostsAccountProfileFields() = runBlocking {
        val profile = BrokerageAccountProfile(
            id = "11111111-1111-4111-8111-111111111111",
            brokerage = Brokerage.SberInvestments,
            userLabel = "Основной ИИС",
            accountType = TaxAccountType.IisIII,
        )
        withJsonServer(201, importEnvelope(profile)) { baseUrl, request ->
            val result = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore()).createPortfolioImport(
                idempotencyKey = "android-import-1",
                accountProfile = profile,
                screenshotCount = 2,
                observedAt = "2026-09-20T10:00:00Z",
            )

            assertTrue(result is ApiResult.Success)
            assertEquals(profile, (result as ApiResult.Success).value.accountProfile)
            val json = JSONObject(request.get().substringAfter("\r\n\r\n"))
            assertEquals(profile.id, json.getString("accountProfileId"))
            assertEquals("sber_investments", json.getString("brokerage"))
            assertEquals("Основной ИИС", json.getString("userLabel"))
            assertEquals("iis_iii", json.getString("accountType"))
        }
    }

    @Test
    fun listRecommendationHistoryParsesProfilesSummaryAndPagination() = runBlocking {
        withJsonServer(
            200,
            """{"items":[{"job":{"id":"job-1","snapshotIds":["snap-1"],"status":"ready","attemptCount":1,"marketDataAsOf":"2026-09-20T10:00:00Z","cashFirstAdjustments":[],"createdAt":"2026-09-20T10:00:00Z","updatedAt":"2026-09-20T10:01:00Z","completedAt":"2026-09-20T10:01:00Z"},"accountProfiles":[{"id":"11111111-1111-4111-8111-111111111111","brokerage":"sber_investments","userLabel":"Основной","accountType":"brokerage"}],"reportSummary":"Сводка","reportPath":"/api/v1/investments/recommendation-jobs/job-1/report"}],"page":{"limit":20,"nextCursor":"next-1","hasMore":true}}""",
        ) { baseUrl, request ->
            val result = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())
                .listRecommendationJobs(limit = 20, cursor = "cursor-1")

            assertTrue(result is ApiResult.Success)
            val page = (result as ApiResult.Success).value
            assertEquals("Основной", page.items.single().accountProfiles.single().userLabel)
            assertEquals("Сводка", page.items.single().reportSummary)
            assertEquals("next-1", page.nextCursor)
            assertTrue(page.hasMore)
            val requestLine = request.get().lineSequence().first()
            assertTrue(requestLine.contains("limit=20"))
            assertTrue(requestLine.contains("cursor=cursor-1"))
        }
    }

    @Test
    fun confirmImportPostsMatchingAccountProfileId() = runBlocking {
        val profileId = "11111111-1111-4111-8111-111111111111"
        withJsonServer(
            201,
            """{"data":{"id":"snap-1","importId":"22222222-2222-4222-8222-222222222222","accountProfile":{"id":"$profileId","brokerage":"sber_investments","userLabel":"Основной","accountType":"brokerage"},"observedAt":"2026-09-20T10:00:00Z","currency":"RUB","freeCash":"100","monthlyContribution":"1000","totalValue":"5100","positions":[],"createdAt":"2026-09-20T10:01:00Z"}}""",
        ) { baseUrl, request ->
            val result = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore()).confirmPortfolioImport(
                importId = "22222222-2222-4222-8222-222222222222",
                accountProfileId = profileId,
                freeCash = "100",
                monthlyContribution = "1000",
                positions = emptyList(),
            )

            assertTrue(result is ApiResult.Success)
            assertEquals("Основной", (result as ApiResult.Success).value.accountProfile?.userLabel)
            val json = JSONObject(request.get().substringAfter("\r\n\r\n"))
            assertEquals(profileId, json.getString("accountProfileId"))
        }
    }

    @Test
    fun discardImportUsesIdempotentDeleteEndpoint() = runBlocking {
        withJsonServer(204, "") { baseUrl, request ->
            val result = LiveFinanceApiClient(ApiConfig(baseUrl), InMemorySecureTokenStore())
                .discardPortfolioImport("22222222-2222-4222-8222-222222222222")

            assertTrue(result is ApiResult.Success)
            val requestLine = request.get().lineSequence().first()
            assertTrue(requestLine.startsWith("DELETE "))
            assertTrue(requestLine.contains("/api/v1/investments/portfolio-imports/22222222-2222-4222-8222-222222222222"))
        }
    }

    private fun importEnvelope(profile: BrokerageAccountProfile): String =
        """{"data":{"id":"22222222-2222-4222-8222-222222222222","accountProfile":${profile.toJson()},"screenshotCount":2,"observedAt":"2026-09-20T10:00:00Z","status":"pending","confirmedAt":null,"createdAt":"2026-09-20T10:00:01Z"}}"""

    private suspend fun withJsonServer(
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
                            val headers = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                            if (headers.endsWith("\r\n\r\n")) break
                        }
                        previous = current
                        current = input.read()
                    }
                    val headers = headerBytes.toByteArray().toString(Charsets.ISO_8859_1)
                    val length = headers.lineSequence()
                        .firstOrNull { it.startsWith("Content-Length:", ignoreCase = true) }
                        ?.substringAfter(":")?.trim()?.toIntOrNull() ?: 0
                    val bytes = ByteArray(length)
                    var read = 0
                    while (read < length) {
                        val count = input.read(bytes, read, length - read)
                        if (count == -1) break
                        read += count
                    }
                    capturedRequest.set(headers + bytes.toString(Charsets.UTF_8))
                    val response = body.toByteArray(Charsets.UTF_8)
                    socket.getOutputStream().use { output ->
                        output.write("HTTP/1.1 $statusCode Test\r\nContent-Type: application/json\r\nContent-Length: ${response.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.US_ASCII))
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
