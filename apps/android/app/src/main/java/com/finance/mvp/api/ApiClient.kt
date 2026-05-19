package com.finance.mvp.api

import com.finance.mvp.session.SecureTokenStore
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import org.json.JSONArray
import org.json.JSONObject

data class ApiConfig(
    val baseUrl: String,
) {
    val normalizedBaseUrl: String = baseUrl.trim().trimEnd('/')

    init {
        require(normalizedBaseUrl.startsWith("http://") || normalizedBaseUrl.startsWith("https://")) {
            "API base URL must start with http:// or https://"
        }
    }
}

interface FinanceApiClient {
    val config: ApiConfig

    suspend fun login(email: String, password: String): ApiResult<SessionStatus>
    suspend fun sessionStatus(): ApiResult<SessionStatus>
    suspend fun dashboard(): ApiResult<FinanceDashboard>
    suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String = "12.34",
        accountType: String = "cash",
        ownershipType: String = if (householdId.isNullOrBlank()) "personal" else "shared",
    ): ApiResult<AccountSummary>
    suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary>
    suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary>
    suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary>
    suspend fun createDemoCategory(
        householdId: String?,
        categoryType: String = "expense",
    ): ApiResult<CategorySummary>
    suspend fun updateCategory(category: CategorySummary): ApiResult<CategorySummary>
    suspend fun archiveCategory(categoryId: String): ApiResult<CategorySummary>
    suspend fun restoreCategory(categoryId: String): ApiResult<CategorySummary>
    suspend fun createDemoTransaction(
        account: AccountSummary,
        category: CategorySummary?,
        transactionType: String = "expense",
        amount: String = "17.00",
    ): ApiResult<TransactionSummary>
    suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary>
    suspend fun deleteTransaction(transactionId: String): ApiResult<Unit>
    suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary>
    suspend fun createDemoTransfer(
        source: AccountSummary,
        destination: AccountSummary,
        amount: String = "1.00",
    ): ApiResult<TransactionSummary>
    suspend fun previewImportReport(request: ImportReportPreviewRequest): ApiResult<ImportReportPreviewResponse>
    suspend fun logout(): ApiResult<Unit>
}

data class SessionStatus(
    val isAuthenticated: Boolean,
    val displayName: String?,
    val householdId: String?,
)

data class FinanceDashboard(
    val session: SessionStatus,
    val accounts: List<AccountSummary>,
    val categories: List<CategorySummary>,
    val transactions: List<TransactionSummary>,
    val totals: List<MoneyTotal>,
    val reportTransferCount: Int,
)

data class AccountSummary(
    val name: String,
    val type: String,
    val ownershipType: String,
    val currency: String,
    val currentBalance: String,
    val id: String = "",
    val householdId: String? = null,
    val status: String = "active",
    val version: Int? = null,
)

data class CategorySummary(
    val name: String,
    val type: String,
    val scope: String,
    val id: String = "",
    val householdId: String? = null,
    val status: String = "active",
    val iconKey: String = "",
    val color: String = "",
    val version: Int? = null,
)

data class TransactionSummary(
    val type: String,
    val amount: String,
    val currency: String,
    val occurredAt: String,
    val description: String?,
    val transferScope: String?,
    val transferStatus: String?,
    val id: String = "",
    val accountId: String = "",
    val counterpartyAccountId: String? = null,
    val categoryId: String? = null,
    val sourceType: String = "manual",
    val version: Int? = null,
)

data class MoneyTotal(
    val currency: String,
    val incomeTotal: String,
    val expenseTotal: String,
    val netTotal: String,
)

data class ImportReportPreviewRequest(
    val reportType: String,
    val targetScope: String,
    val householdId: String? = null,
    val fileName: String? = null,
    val fileSizeBytes: Long? = null,
    val mimeType: String? = null,
    val sourceType: String = "file_metadata_only",
)

data class ImportReportPreviewResponse(
    val status: String,
    val canConfirm: Boolean,
    val willChangeData: Boolean,
    val message: String,
)

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class Failure(val message: String, val cause: Throwable? = null) : ApiResult<Nothing>
}

class LiveFinanceApiClient(
    override val config: ApiConfig,
    private val tokenStore: SecureTokenStore,
) : FinanceApiClient {
    override suspend fun login(email: String, password: String): ApiResult<SessionStatus> = safeCall {
        val response = request(
            path = "/api/v1/sessions",
            method = "POST",
            body = JSONObject()
                .put("email", email)
                .put("password", password)
                .put("transport", "android_bearer")
                .toString(),
            authorize = false,
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        )
        response.optString("accessToken").takeIf { it.isNotBlank() }?.let {
            tokenStore.saveAccessToken(it)
        }
        parseSession(response)
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> = safeCall {
        parseSession(request(path = "/api/v1/sessions/current", method = "GET"))
    }

    override suspend fun dashboard(): ApiResult<FinanceDashboard> = safeCall {
        val session = parseSession(request(path = "/api/v1/sessions/current", method = "GET"))
        val accounts = request(path = "/api/v1/accounts", method = "GET").items().map(::parseAccount)
        val categories = request(path = "/api/v1/categories", method = "GET").items().map(::parseCategory)
        val transactions = request(path = "/api/v1/transactions", method = "GET").items().map(::parseTransaction)
        val reportData = session.householdId?.let { householdId ->
            request(
                path = "/api/v1/reports/summary",
                method = "GET",
                query = mapOf(
                    "reportMode" to "combined_viewer_overview",
                    "householdId" to householdId,
                    "currency" to (accounts.firstOrNull()?.currency ?: "USD"),
                ),
            ).optJSONObject("data")
        }
        val totals = reportData
            ?.optJSONArray("totalsByCurrency")
            ?.toObjectList()
            ?.map(::parseMoneyTotal)
            ?: emptyList()
        val reportTransferCount = session.householdId?.let { householdId ->
            request(
                path = "/api/v1/reports/transactions",
                method = "GET",
                query = mapOf(
                    "reportMode" to "combined_viewer_overview",
                    "householdId" to householdId,
                    "currency" to (accounts.firstOrNull()?.currency ?: "USD"),
                    "transactionTypes" to "transfer",
                ),
            ).optJSONObject("data")
                ?.optJSONArray("items")
                ?.length()
                ?: 0
        } ?: 0

        FinanceDashboard(
            session = session,
            accounts = accounts,
            categories = categories,
            transactions = transactions,
            totals = totals,
            reportTransferCount = reportTransferCount,
        )
    }

    override suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String,
        accountType: String,
        ownershipType: String,
    ): ApiResult<AccountSummary> = safeCall {
        val stamp = System.currentTimeMillis().toString().takeLast(6)
        request(
            path = "/api/v1/accounts",
            method = "POST",
            body = JSONObject()
                .put("name", "Новый актив $stamp")
                .put("accountType", accountType)
                .put("ownershipType", normalizeAccountOwnershipType(ownershipType))
                .apply {
                    accountHouseholdIdForOwnership(householdId, ownershipType)?.let { put("householdId", it) }
                }
                .put("currency", currency)
                .put("initialBalance", initialBalance)
                .toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        ).dataObject().let(::parseAccount)
    }

    override suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary> = safeCall {
        request(
            path = "/api/v1/accounts/${account.id.urlEncodePath()}",
            method = "PATCH",
            body = JSONObject()
                .put("name", "${account.name.take(80)} upd")
                .apply { account.version?.let { put("version", it) } }
                .toString(),
        ).dataObject().let(::parseAccount)
    }

    override suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary> = safeCall {
        request(path = "/api/v1/accounts/${accountId.urlEncodePath()}/archive", method = "POST")
            .dataObject()
            .let(::parseAccount)
    }

    override suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary> = safeCall {
        request(path = "/api/v1/accounts/${accountId.urlEncodePath()}/restore", method = "POST")
            .dataObject()
            .let(::parseAccount)
    }

    override suspend fun createDemoCategory(
        householdId: String?,
        categoryType: String,
    ): ApiResult<CategorySummary> = safeCall {
        val stamp = System.currentTimeMillis().toString().takeLast(6)
        val type = normalizeTransactionCategoryType(categoryType)
        request(
            path = "/api/v1/categories",
            method = "POST",
            body = JSONObject()
                .put("name", "Новая категория $stamp")
                .put("type", type)
                .put("scope", categoryScopeForHousehold(householdId))
                .apply { householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) } }
                .put("iconKey", if (type == "income") "income" else "android")
                .put("color", if (type == "income") "#2E7D62" else "#2E7D32")
                .toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        ).dataObject().let(::parseCategory)
    }

    override suspend fun updateCategory(category: CategorySummary): ApiResult<CategorySummary> = safeCall {
        request(
            path = "/api/v1/categories/${category.id.urlEncodePath()}",
            method = "PATCH",
            body = JSONObject()
                .put("name", "${category.name.take(80)} upd")
                .put("color", "#1565C0")
                .apply { category.version?.let { put("version", it) } }
                .toString(),
        ).dataObject().let(::parseCategory)
    }

    override suspend fun archiveCategory(categoryId: String): ApiResult<CategorySummary> = safeCall {
        request(path = "/api/v1/categories/${categoryId.urlEncodePath()}/archive", method = "POST")
            .dataObject()
            .let(::parseCategory)
    }

    override suspend fun restoreCategory(categoryId: String): ApiResult<CategorySummary> = safeCall {
        request(path = "/api/v1/categories/${categoryId.urlEncodePath()}/restore", method = "POST")
            .dataObject()
            .let(::parseCategory)
    }

    override suspend fun createDemoTransaction(
        account: AccountSummary,
        category: CategorySummary?,
        transactionType: String,
        amount: String,
    ): ApiResult<TransactionSummary> = safeCall {
        request(
            path = "/api/v1/transactions",
            method = "POST",
            body = JSONObject()
                .put("transactionType", transactionType)
                .put("accountId", account.id)
                .apply { category?.id?.takeIf { it.isNotBlank() }?.let { put("categoryId", it) } }
                .put("amount", amount)
                .put("currency", account.currency)
                .put("occurredAt", nowIso())
                .put("description", category?.name ?: if (transactionType == "income") "Доход" else "Расход")
                .put("sourceType", "manual")
                .toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        ).dataObject().let(::parseTransaction)
    }

    override suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary> = safeCall {
        request(
            path = "/api/v1/transactions/${transaction.id.urlEncodePath()}",
            method = "PATCH",
            body = JSONObject()
                .put("amount", "18.0000")
                .put("description", "Операция обновлена")
                .apply { transaction.version?.let { put("version", it) } }
                .toString(),
        ).dataObject().let(::parseTransaction)
    }

    override suspend fun deleteTransaction(transactionId: String): ApiResult<Unit> = safeCall {
        request(
            path = "/api/v1/transactions/${transactionId.urlEncodePath()}",
            method = "DELETE",
            expectedCodes = setOf(HttpURLConnection.HTTP_NO_CONTENT),
        )
        Unit
    }

    override suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary> = safeCall {
        request(path = "/api/v1/transactions/${transactionId.urlEncodePath()}/restore", method = "POST")
            .dataObject()
            .let(::parseTransaction)
    }

    override suspend fun createDemoTransfer(
        source: AccountSummary,
        destination: AccountSummary,
        amount: String,
    ): ApiResult<TransactionSummary> = safeCall {
        request(
            path = "/api/v1/transactions",
            method = "POST",
            body = JSONObject()
                .put("transactionType", "transfer")
                .put("accountId", source.id)
                .put("counterpartyAccountId", destination.id)
                .put("amount", amount)
                .put("currency", source.currency)
                .put("occurredAt", nowIso())
                .put("description", "Между счетами")
                .put("sourceType", "manual")
                .toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        ).dataObject().let(::parseTransaction)
    }

    override suspend fun previewImportReport(request: ImportReportPreviewRequest): ApiResult<ImportReportPreviewResponse> = safeCall {
        val body = JSONObject()
            .put("reportType", request.reportType)
            .put("sourceType", "file_metadata_only")
            .put("targetScope", request.targetScope)
            .put("householdId", request.householdId)
            .apply {
                request.fileName?.take(255)?.let { put("fileName", it) }
                request.fileSizeBytes?.takeIf { it >= 0 }?.let { put("fileSizeBytes", it) }
                request.mimeType?.let { put("mimeType", it) }
            }
            .toString()

        request(
            path = "/api/v1/imports/report-preview",
            method = "POST",
            body = body,
        ).let(::parseImportReportPreview)
    }

    override suspend fun logout(): ApiResult<Unit> = safeCall {
        request(
            path = "/api/v1/sessions/current",
            method = "DELETE",
            expectedCodes = setOf(HttpURLConnection.HTTP_NO_CONTENT),
        )
        tokenStore.clear()
    }

    private inline fun <T> safeCall(block: () -> T): ApiResult<T> {
        return try {
            ApiResult.Success(block())
        } catch (error: ApiException) {
            ApiResult.Failure(error.message ?: "Ошибка API", error)
        } catch (error: Exception) {
            ApiResult.Failure("Не удалось подключиться к API: ${error.message ?: error::class.java.simpleName}", error)
        }
    }

    private suspend fun request(
        path: String,
        method: String,
        query: Map<String, String> = emptyMap(),
        body: String? = null,
        authorize: Boolean = true,
        expectedCodes: Set<Int> = setOf(HttpURLConnection.HTTP_OK),
    ): JSONObject {
        val queryString = query.entries.joinToString("&") {
            "${it.key.urlEncode()}=${it.value.urlEncode()}"
        }.takeIf { it.isNotBlank() }?.let { "?$it" } ?: ""
        val connection = (URL("${config.normalizedBaseUrl}$path$queryString").openConnection() as HttpURLConnection)
        connection.requestMethod = method
        connection.connectTimeout = 5_000
        connection.readTimeout = 5_000
        connection.setRequestProperty("Accept", "application/json")
        if (authorize) {
            tokenStore.readAccessToken()?.let {
                connection.setRequestProperty("Authorization", "Bearer $it")
            }
        }
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        }

        val code = connection.responseCode
        val text = connection.readText(code)
        if (code !in expectedCodes) {
            throw ApiException(parseError(text, code))
        }
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun HttpURLConnection.readText(code: Int): String {
        val stream = if (code >= 400) errorStream else inputStream
        if (stream == null) return ""
        return BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { reader ->
            reader.readText()
        }
    }

    private fun parseError(text: String, code: Int): String {
        val fallback = "API вернул HTTP $code"
        return runCatching {
            JSONObject(text).optJSONObject("error")?.optString("message")?.takeIf { it.isNotBlank() }
        }.getOrNull() ?: fallback
    }
}

class ApiException(message: String) : Exception(message)

private fun parseSession(json: JSONObject): SessionStatus {
    val actor = json.optJSONObject("actor")
        ?: json.optJSONObject("data")?.optJSONObject("actor")
        ?: json.optJSONObject("data")?.optJSONObject("user")
        ?: json.optJSONObject("user")
    val userId = actor?.optString("userId")?.takeIf { it.isNotBlank() }
        ?: actor?.optString("id")?.takeIf { it.isNotBlank() }
    val householdId = actor?.optJSONArray("memberships")
        ?.toObjectList()
        ?.firstOrNull { it.optString("status") == "active" }
        ?.optString("householdId")
        ?.takeIf { it.isNotBlank() }
    return SessionStatus(
        isAuthenticated = actor != null || json.has("accessToken"),
        displayName = userId?.take(8)?.let { "Пользователь $it" },
        householdId = householdId,
    )
}

private fun parseAccount(json: JSONObject): AccountSummary {
    return AccountSummary(
        name = userFacingSeedText(json.optString("name", "Счет")),
        type = json.optString("accountType"),
        ownershipType = json.optString("ownershipType"),
        currency = json.optString("currency"),
        currentBalance = json.optString("currentBalance"),
        id = json.optString("id"),
        householdId = json.optString("householdId").takeIf { it.isNotBlank() && it != "null" },
        status = json.optString("status", "active"),
        version = json.optIntOrNull("version"),
    )
}

private fun parseCategory(json: JSONObject): CategorySummary {
    return CategorySummary(
        name = userFacingSeedText(json.optString("name", "Категория")),
        type = json.optString("type"),
        scope = json.optString("scope"),
        id = json.optString("id"),
        householdId = json.optString("householdId").takeIf { it.isNotBlank() && it != "null" },
        status = json.optString("status", "active"),
        iconKey = json.optString("iconKey"),
        color = json.optString("color"),
        version = json.optIntOrNull("version"),
    )
}

private fun parseTransaction(json: JSONObject): TransactionSummary {
    return TransactionSummary(
        type = json.optString("transactionType"),
        amount = json.optString("amount"),
        currency = json.optString("currency"),
        occurredAt = json.optString("occurredAt"),
        description = userFacingSeedText(json.optString("description"))
            .takeIf { it.isNotBlank() && it != "null" },
        transferScope = json.optString("transferScope").takeIf { it.isNotBlank() && it != "null" },
        transferStatus = json.optString("transferStatus").takeIf { it.isNotBlank() && it != "null" },
        id = json.optString("id"),
        accountId = json.optString("accountId"),
        counterpartyAccountId = json.optString("counterpartyAccountId").takeIf { it.isNotBlank() && it != "null" },
        categoryId = json.optString("categoryId").takeIf { it.isNotBlank() && it != "null" },
        sourceType = json.optString("sourceType", "manual"),
        version = json.optIntOrNull("version"),
    )
}

private fun parseMoneyTotal(json: JSONObject): MoneyTotal {
    return MoneyTotal(
        currency = json.optString("currency"),
        incomeTotal = json.optString("incomeTotal"),
        expenseTotal = json.optString("expenseTotal"),
        netTotal = json.optString("netTotal"),
    )
}

private fun parseImportReportPreview(json: JSONObject): ImportReportPreviewResponse {
    return ImportReportPreviewResponse(
        status = json.optString("status", "preview_placeholder"),
        canConfirm = json.optBoolean("canConfirm", false),
        willChangeData = json.optBoolean("willChangeData", false),
        message = json.optString("message", "Файл не импортирован. Сейчас показана только предварительная сводка."),
    )
}

internal fun normalizeAccountOwnershipType(value: String): String {
    return if (value == "shared") "shared" else "personal"
}

internal fun categoryScopeForHousehold(householdId: String?): String {
    return if (householdId.isNullOrBlank()) "personal" else "household"
}

internal fun normalizeTransactionCategoryType(value: String): String {
    return if (value == "income") "income" else "expense"
}

internal fun userFacingSeedText(value: String?): String {
    val trimmed = value?.trim().orEmpty()
    val labels = mapOf(
        "Dev Personal Cash" to "Личные наличные",
        "Dev Household Card" to "Семейная карта",
        "Dev Household Deposit" to "Общий вклад",
        "Dev Brokerage" to "Брокерский счет",
        "Dev Metal" to "Металлы",
        "Dev Groceries" to "Продукты",
        "Dev Home" to "Дом",
        "Dev Salary" to "Зарплата",
        "Dev household supplies" to "Домашние покупки",
        "Dev sample income" to "Зарплата",
        "Dev same-household transfer" to "Между общими счетами",
        "Dev brokerage asset buy" to "Покупка актива",
        "Dev deposit interest" to "Проценты по вкладу",
        "Dev brokerage dividend" to "Дивиденды",
    )

    return labels[trimmed] ?: trimmed.replace(Regex("^Dev\\s+", RegexOption.IGNORE_CASE), "")
}

internal fun accountHouseholdIdForOwnership(householdId: String?, ownershipType: String): String? {
    return householdId?.takeIf { normalizeAccountOwnershipType(ownershipType) == "shared" && it.isNotBlank() }
}

private fun JSONObject.items(): List<JSONObject> = optJSONArray("items")?.toObjectList() ?: emptyList()

private fun JSONObject.dataObject(): JSONObject = optJSONObject("data") ?: this

private fun JSONObject.optIntOrNull(name: String): Int? = if (has(name) && !isNull(name)) optInt(name) else null

private fun JSONArray.toObjectList(): List<JSONObject> {
    return (0 until length()).mapNotNull { index -> optJSONObject(index) }
}

private fun String.urlEncode(): String = URLEncoder.encode(this, Charsets.UTF_8.name())

private fun String.urlEncodePath(): String = urlEncode().replace("+", "%20")

private fun nowIso(): String = java.time.Instant.now().toString()
