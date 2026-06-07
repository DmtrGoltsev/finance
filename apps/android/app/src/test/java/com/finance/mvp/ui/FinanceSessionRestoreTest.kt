package com.finance.mvp.ui

import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import com.finance.mvp.session.InMemorySecureTokenStore
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class FinanceSessionRestoreTest {
    @Test
    fun coldStartRestoreLoadsDashboardForAuthenticatedSession() = runBlocking {
        val session = SessionStatus(true, "User", "household")
        val dashboard = dashboardFixture(session)
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(session),
            dashboardResult = ApiResult.Success(dashboard),
        )

        val state = restoredFinanceUiState(apiClient)

        assertEquals(session, state.session)
        assertSame(dashboard, state.dashboard)
        assertTrue(state.message.isNotBlank())
        assertEquals(1, apiClient.sessionStatusCalls)
        assertEquals(1, apiClient.dashboardCalls)
    }

    @Test
    fun coldStartRestoreDoesNotKeepFinancialDataWhenDashboardReturns401Status() = runBlocking {
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(SessionStatus(true, "User", "household")),
            dashboardResult = ApiResult.Failure("server supplied body", statusCode = 401),
        )

        val state = restoredFinanceUiState(apiClient)

        assertNull(state.session)
        assertNull(state.dashboard)
        assertTrue(state.message.isNotBlank())
        assertEquals(1, apiClient.dashboardCalls)
    }

    @Test
    fun coldStartRestoreDoesNotKeepFinancialDataWhenDashboardReturns403Status() = runBlocking {
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(SessionStatus(true, "User", "household")),
            dashboardResult = ApiResult.Failure("server supplied body", statusCode = 403),
        )

        val state = restoredFinanceUiState(apiClient)

        assertNull(state.session)
        assertNull(state.dashboard)
        assertTrue(state.message.isNotBlank())
        assertEquals(1, apiClient.dashboardCalls)
    }

    @Test
    fun coldStartRestoreKeepsSessionWhenDashboardBodySaysForbiddenWithoutStatus() = runBlocking {
        val session = SessionStatus(true, "User", "household")
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(session),
            dashboardResult = ApiResult.Failure("forbidden by account policy"),
        )

        val state = restoredFinanceUiState(apiClient)

        assertEquals(session, state.session)
        assertNull(state.dashboard)
        assertTrue(state.message.isNotBlank())
        assertEquals(1, apiClient.dashboardCalls)
    }

    @Test
    fun coldStartRestoreDoesNotKeepFinancialDataWhenDashboardMessageHasLegacyHttp401() = runBlocking {
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(SessionStatus(true, "User", "household")),
            dashboardResult = ApiResult.Failure("HTTP 401 Unauthorized"),
        )

        val state = restoredFinanceUiState(apiClient)

        assertNull(state.session)
        assertNull(state.dashboard)
        assertTrue(state.message.isNotBlank())
        assertEquals(1, apiClient.dashboardCalls)
    }

    @Test
    fun coldStartRestoreDoesNotKeepFinancialDataWhenDashboardMessageHasLegacyHttp403() = runBlocking {
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(SessionStatus(true, "User", "household")),
            dashboardResult = ApiResult.Failure("HTTP 403 Forbidden"),
        )

        val state = restoredFinanceUiState(apiClient)

        assertNull(state.session)
        assertNull(state.dashboard)
        assertTrue(state.message.isNotBlank())
        assertEquals(1, apiClient.dashboardCalls)
    }

    @Test
    fun coldStartRestoreSkipsDashboardWhenSessionIsNotAuthenticated() = runBlocking {
        val apiClient = FakeFinanceApiClient(
            sessionResult = ApiResult.Success(SessionStatus(false, null, null)),
            dashboardResult = ApiResult.Failure("dashboard should not be called"),
        )

        val state = restoredFinanceUiState(apiClient)

        assertNull(state.dashboard)
        assertEquals(0, apiClient.dashboardCalls)
    }

    @Test
    fun liveClientClearsPersistedTokenWhenSessionRequestReturns403WithServerBody() = runBlocking {
        withJsonResponseServer(
            statusCode = 403,
            body = """{"error":{"message":"subscription required"}}""",
        ) { baseUrl, seenAuthorization ->
            val tokenStore = InMemorySecureTokenStore()
            tokenStore.saveAccessToken("stale-token")
            val apiClient = LiveFinanceApiClient(ApiConfig(baseUrl), tokenStore)

            val result = apiClient.dashboard()

            assertTrue(result is ApiResult.Failure)
            assertEquals(403, (result as ApiResult.Failure).statusCode)
            assertEquals("Bearer stale-token", seenAuthorization.get())
            assertNull(tokenStore.readAccessToken())
        }
    }

    private fun dashboardFixture(session: SessionStatus): FinanceDashboard {
        return FinanceDashboard(
            session = session,
            accounts = listOf(
                AccountSummary("Card", "card", "personal", "USD", "10.00", id = "acc-card"),
            ),
            categories = listOf(
                CategorySummary("Food", "expense", "personal", id = "cat-food"),
            ),
            transactions = emptyList(),
            totals = listOf(MoneyTotal("USD", "0.00", "0.00", "0.00")),
            reportTransferCount = 0,
        )
    }

    private suspend fun withJsonResponseServer(
        statusCode: Int,
        body: String,
        block: suspend (String, AtomicReference<String?>) -> Unit,
    ) {
        val seenAuthorization = AtomicReference<String?>()
        val server = ServerSocket(0)
        val serverThread = Thread {
            runCatching {
                server.accept().use { socket ->
                    val reader = socket.getInputStream().bufferedReader(Charsets.UTF_8)
                    var line = reader.readLine()
                    while (line != null && line.isNotBlank()) {
                        if (line.startsWith("Authorization:", ignoreCase = true)) {
                            seenAuthorization.set(line.substringAfter(":").trim())
                        }
                        line = reader.readLine()
                    }

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
            block("http://127.0.0.1:${server.localPort}", seenAuthorization)
        } finally {
            server.close()
            serverThread.join(1_000)
        }
    }
}

private class FakeFinanceApiClient(
    private val sessionResult: ApiResult<SessionStatus>,
    private val dashboardResult: ApiResult<FinanceDashboard>,
) : FinanceApiClient {
    override val config: ApiConfig = ApiConfig("http://localhost:8000")
    var sessionStatusCalls: Int = 0
        private set
    var dashboardCalls: Int = 0
        private set

    override suspend fun login(email: String, password: String): ApiResult<SessionStatus> {
        return ApiResult.Failure("unused")
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> {
        sessionStatusCalls += 1
        return sessionResult
    }

    override suspend fun dashboard(): ApiResult<FinanceDashboard> {
        dashboardCalls += 1
        return dashboardResult
    }

    override suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String,
        accountType: String,
        ownershipType: String,
    ): ApiResult<AccountSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun createAccount(
        name: String,
        currency: String,
        initialBalance: String,
        accountType: String,
        householdId: String?,
    ): ApiResult<AccountSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun createDemoCategory(
        householdId: String?,
        categoryType: String,
    ): ApiResult<CategorySummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun createCategory(
        name: String,
        householdId: String?,
        categoryType: String,
    ): ApiResult<CategorySummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun updateCategory(category: CategorySummary): ApiResult<CategorySummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun archiveCategory(categoryId: String): ApiResult<CategorySummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun restoreCategory(categoryId: String): ApiResult<CategorySummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun createDemoTransaction(
        account: AccountSummary,
        category: CategorySummary?,
        transactionType: String,
        amount: String,
    ): ApiResult<TransactionSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun deleteTransaction(transactionId: String): ApiResult<Unit> {
        return ApiResult.Failure("unused")
    }

    override suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun createDemoTransfer(
        source: AccountSummary,
        destination: AccountSummary,
        amount: String,
    ): ApiResult<TransactionSummary> {
        return ApiResult.Failure("unused")
    }

    override suspend fun logout(): ApiResult<Unit> {
        return ApiResult.Failure("unused")
    }
}
