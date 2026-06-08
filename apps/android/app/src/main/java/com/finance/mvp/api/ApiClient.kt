package com.finance.mvp.api

import com.finance.mvp.session.SecureTokenStore
import java.io.BufferedReader
import java.io.InputStreamReader
import java.math.BigDecimal
import java.math.RoundingMode
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
    suspend fun register(email: String, password: String, displayName: String? = null): ApiResult<RegistrationResult> =
        ApiResult.Failure("Регистрация не поддерживается этим клиентом")
    suspend fun sessionStatus(): ApiResult<SessionStatus>
    suspend fun dashboard(): ApiResult<FinanceDashboard>
    suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String = "12.34",
        accountType: String = "cash",
        ownershipType: String = if (householdId.isNullOrBlank()) "personal" else "shared",
    ): ApiResult<AccountSummary>
    suspend fun createAccount(
        name: String,
        currency: String,
        initialBalance: String,
        accountType: String,
        householdId: String?,
        assetCategoryId: String? = null,
    ): ApiResult<AccountSummary>
    suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary>
    suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary>
    suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary>
    suspend fun createAssetCategory(request: AssetCategoryCreateRequest): ApiResult<AssetCategory> =
        ApiResult.Failure("Категории активов не поддерживаются этим клиентом")
    suspend fun updateAssetCategory(category: AssetCategory): ApiResult<AssetCategory> =
        ApiResult.Failure("Категории активов не поддерживаются этим клиентом")
    suspend fun archiveAssetCategory(categoryId: String): ApiResult<AssetCategory> =
        ApiResult.Failure("Категории активов не поддерживаются этим клиентом")
    suspend fun createDemoCategory(
        householdId: String?,
        categoryType: String = "expense",
    ): ApiResult<CategorySummary>
    suspend fun createCategory(
        name: String,
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
    suspend fun createCaptureDraft(request: CaptureDraftCreateRequest): ApiResult<CaptureDraft> =
        ApiResult.Failure("Черновики операций не поддерживаются этим клиентом")
    suspend fun listCaptureDrafts(status: String = "pending"): ApiResult<List<CaptureDraft>> =
        ApiResult.Failure("Черновики операций не поддерживаются этим клиентом")
    suspend fun updateCaptureDraft(draftId: String, request: CaptureDraftUpdateRequest): ApiResult<CaptureDraft> =
        ApiResult.Failure("Черновики операций не поддерживаются этим клиентом")
    suspend fun confirmCaptureDraft(draftId: String): ApiResult<CaptureDraft> =
        ApiResult.Failure("Черновики операций не поддерживаются этим клиентом")
    suspend fun discardCaptureDraft(draftId: String): ApiResult<Unit> =
        ApiResult.Failure("Черновики операций не поддерживаются этим клиентом")
    suspend fun screenshotOcr(
        imageBytes: ByteArray,
        contentType: String,
        capturedAt: String?,
        householdId: String?,
    ): ApiResult<ScreenshotOcrResponse> =
        ApiResult.Failure("Распознавание скриншотов не поддерживается этим клиентом")
    suspend fun listPlanningPlans(scope: String, month: String, householdId: String? = null): ApiResult<PlanningPlan?> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun listPlanningPlanHistory(scope: String, householdId: String? = null): ApiResult<List<PlanningPlan>> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun createPlanningPlan(request: PlanningPlanCreateRequest): ApiResult<PlanningPlan> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun getPlanningPlan(planId: String): ApiResult<PlanningPlan> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun createPlanningIncomeSource(
        planId: String,
        request: PlanningIncomeSourceCreateRequest,
    ): ApiResult<PlanningIncomeSource> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun updatePlanningIncomeSource(
        incomeSourceId: String,
        request: PlanningIncomeSourceUpdateRequest,
    ): ApiResult<PlanningIncomeSource> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun confirmPlanningIncomeSource(incomeSourceId: String): ApiResult<PlanningIncomeSource> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun deletePlanningIncomeSource(incomeSourceId: String): ApiResult<Unit> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun createPlanningAllocation(
        planId: String,
        request: PlanningAllocationCreateRequest,
    ): ApiResult<PlanningAllocation> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun updatePlanningAllocation(
        allocationId: String,
        request: PlanningAllocationUpdateRequest,
    ): ApiResult<PlanningAllocation> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun deletePlanningAllocation(allocationId: String): ApiResult<Unit> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun copyPlanningPlan(planId: String, request: PlanningPlanCopyRequest): ApiResult<PlanningPlan> =
        ApiResult.Failure("Планирование не поддерживается этим клиентом")
    suspend fun logout(): ApiResult<Unit>
}

data class SessionStatus(
    val isAuthenticated: Boolean,
    val displayName: String?,
    val householdId: String?,
)

sealed interface RegistrationResult {
    data class Authenticated(val session: SessionStatus?) : RegistrationResult
    data class Accepted(val message: String) : RegistrationResult
}

data class FinanceDashboard(
    val session: SessionStatus,
    val accounts: List<AccountSummary>,
    val categories: List<CategorySummary>,
    val transactions: List<TransactionSummary>,
    val totals: List<MoneyTotal>,
    val reportTransferCount: Int,
    val assetCategories: List<AssetCategory> = emptyList(),
    val assetCategoryGroups: List<AssetCategoryGroup> = emptyList(),
    val investmentsByCurrency: List<MoneyAmount> = emptyList(),
    val investmentsTotal: MoneyAmount? = null,
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
    val assetCategoryId: String? = null,
    val version: Int? = null,
)

data class AssetCategory(
    val id: String,
    val name: String,
    val scopeType: String,
    val householdId: String? = null,
    val ownerUserId: String? = null,
    val currency: String,
    val manualAmount: String,
    val isInvestment: Boolean,
    val assetType: String,
    val recordStatus: String = "active",
    val version: Int? = null,
)

data class AssetCategoryGroup(
    val assetCategoryId: String,
    val name: String,
    val scopeType: String,
    val householdId: String? = null,
    val currency: String,
    val manualAmount: String,
    val accountsTotal: String,
    val totalAmount: String,
    val isInvestment: Boolean,
    val assetType: String,
    val accountCount: Int = 0,
)

data class MoneyAmount(
    val currency: String,
    val amount: String,
)

data class AssetCategoryCreateRequest(
    val name: String,
    val scopeType: String,
    val householdId: String? = null,
    val currency: String,
    val manualAmount: String = "0",
    val isInvestment: Boolean = false,
    val assetType: String = "bank",
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

data class CaptureDraftCreateRequest(
    val amount: String,
    val currency: String,
    val description: String?,
    val merchantName: String?,
    val capturedAt: String,
    val occurredAt: String,
    val captureSource: String,
    val idempotencyKey: String,
    val confidence: Double,
    val sourceAppPackage: String?,
    val sourceAppLabel: String?,
    val evidenceHash: String,
    val categoryId: String? = null,
)

data class CaptureDraftUpdateRequest(
    val amount: String? = null,
    val currency: String? = null,
    val description: String? = null,
    val merchantName: String? = null,
    val occurredAt: String? = null,
    val confidence: Double? = null,
    val accountId: String? = null,
    val categoryId: String? = null,
)

data class ScreenshotOcrCandidate(
    val candidateType: String,
    val externalLabel: String,
    val amount: String,
    val currency: String,
    val operationCount: Int,
    val description: String,
    val confidence: Double,
    val idempotencyKey: String,
    val evidenceHash: String,
)

data class ScreenshotOcrResponse(
    val items: List<ScreenshotOcrCandidate>,
)

data class CaptureDraft(
    val id: String,
    val status: String,
    val amount: String,
    val currency: String,
    val description: String?,
    val merchantName: String?,
    val capturedAt: String?,
    val occurredAt: String,
    val captureSource: String,
    val confidence: Double,
    val sourceAppPackage: String?,
    val sourceAppLabel: String?,
    val evidenceHash: String,
    val idempotencyKey: String,
    val accountId: String? = null,
    val categoryId: String? = null,
    val version: Int? = null,
)

data class PlanningPlan(
    val id: String,
    val scope: String,
    val month: String,
    val currency: String,
    val householdId: String? = null,
    val totalPlannedIncome: String = "0",
    val previousMonthSurplus: String = "0",
    val allocatedTotal: String = "0",
    val remainingAmount: String = "0",
    val overallocatedAmount: String = "0",
    val isUnderallocated: Boolean = false,
    val isOverallocated: Boolean = false,
    val status: String? = null,
    val progressStatus: String? = null,
    val progressPercent: String? = null,
    val incomeSources: List<PlanningIncomeSource> = emptyList(),
    val allocations: List<PlanningAllocation> = emptyList(),
    val version: Int? = null,
)

data class PlanningIncomeSource(
    val id: String,
    val planId: String,
    val amount: String,
    val source: String,
    val description: String?,
    val dayOfMonth: Int?,
    val confirmed: Boolean,
    val effectiveDate: String?,
    val version: Int? = null,
)

data class PlanningAllocation(
    val id: String,
    val planId: String,
    val targetType: String,
    val targetId: String?,
    val targetSnapshot: String?,
    val requiresAttention: Boolean,
    val attentionReason: String?,
    val comment: String?,
    val allocationMode: String,
    val allocationValue: String,
    val calculatedAmount: String,
    val recurrenceType: String? = null,
    val isSavingsGoal: Boolean = false,
    val goalTargetAmount: String? = null,
    val goalDueMonth: String? = null,
    val goalMonthlyAmount: String? = null,
    val actualAmount: String? = null,
    val varianceAmount: String? = null,
    val progressPercent: String? = null,
    val progressStatus: String? = null,
    val status: String? = null,
    val version: Int? = null,
)

data class PlanningPlanCreateRequest(
    val scope: String,
    val month: String,
    val currency: String,
    val householdId: String? = null,
)

data class PlanningPlanCopyRequest(
    val targetMonth: String,
)

data class PlanningIncomeSourceCreateRequest(
    val amount: String,
    val source: String,
    val description: String? = null,
    val dayOfMonth: Int,
    val effectiveDate: String? = null,
)

data class PlanningIncomeSourceUpdateRequest(
    val amount: String? = null,
    val source: String? = null,
    val description: String? = null,
    val dayOfMonth: Int? = null,
    val confirmed: Boolean? = null,
    val effectiveDate: String? = null,
    val version: Int? = null,
)

data class PlanningAllocationCreateRequest(
    val targetType: String,
    val targetId: String,
    val targetSnapshot: String? = null,
    val comment: String? = null,
    val allocationMode: String,
    val allocationValue: String,
    val recurrenceType: String? = null,
    val isSavingsGoal: Boolean = false,
    val goalTargetAmount: String? = null,
    val goalDueMonth: String? = null,
)

data class PlanningAllocationUpdateRequest(
    val targetType: String? = null,
    val targetId: String? = null,
    val targetSnapshot: String? = null,
    val requiresAttention: Boolean? = null,
    val attentionReason: String? = null,
    val comment: String? = null,
    val allocationMode: String? = null,
    val allocationValue: String? = null,
    val recurrenceType: String? = null,
    val isSavingsGoal: Boolean? = null,
    val goalTargetAmount: String? = null,
    val goalDueMonth: String? = null,
    val version: Int? = null,
)

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class Failure(
        val message: String,
        val cause: Throwable? = null,
        val statusCode: Int? = null,
    ) : ApiResult<Nothing>
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

    override suspend fun register(
        email: String,
        password: String,
        displayName: String?,
    ): ApiResult<RegistrationResult> = safeCall {
        val body = JSONObject()
            .put("email", email)
            .put("password", password)
            .put("transport", "android_bearer")
        displayName?.takeIf { it.isNotBlank() }?.let { body.put("displayName", it) }
        val response = request(
            path = "/api/v1/users",
            method = "POST",
            body = body.toString(),
            authorize = false,
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_ACCEPTED),
        )
        if (response.optBoolean("registrationAccepted", false)) {
            tokenStore.clear()
            return@safeCall RegistrationResult.Accepted(
                response.optString("message").takeIf { it.isNotBlank() }
                    ?: "Заявка на регистрацию принята",
            )
        }
        response.optString("accessToken").takeIf { it.isNotBlank() }?.let {
            tokenStore.saveAccessToken(it)
        }
        RegistrationResult.Authenticated(parseSession(response))
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> = safeCall {
        parseSession(request(path = "/api/v1/sessions/current", method = "GET"))
    }

    override suspend fun dashboard(): ApiResult<FinanceDashboard> = safeCall {
        val session = parseSession(request(path = "/api/v1/sessions/current", method = "GET"))
        val accounts = request(path = "/api/v1/accounts", method = "GET").items().map(::parseAccount)
        val categories = request(path = "/api/v1/categories", method = "GET").items().map(::parseCategory)
        val assetCategories = runCatching {
            request(path = "/api/v1/asset-categories", method = "GET").items().map(::parseAssetCategory)
        }.getOrDefault(emptyList())
        val transactions = request(path = "/api/v1/transactions", method = "GET").items().map(::parseTransaction)
        val reportData = runCatching {
            val householdId = session.householdId
            request(
                path = "/api/v1/reports/summary",
                method = "GET",
                query = (
                    if (householdId.isNullOrBlank()) {
                        mapOf("reportMode" to "personal")
                    } else {
                        mapOf("reportMode" to "combined_viewer_overview", "householdId" to householdId)
                    }
                    ) + mapOf("currency" to (accounts.firstOrNull()?.currency ?: "USD")),
            ).optJSONObject("data")
        }.getOrNull()
        val totals = reportData
            ?.optJSONArray("totalsByCurrency")
            ?.toObjectList()
            ?.map(::parseMoneyTotal)
            ?: emptyList()
        val accountBalancesData = runCatching {
            val householdId = session.householdId
            request(
                path = "/api/v1/reports/account-balances",
                method = "GET",
                query = (
                    if (householdId.isNullOrBlank()) {
                        mapOf("reportMode" to "personal")
                    } else {
                        mapOf("reportMode" to "combined_viewer_overview", "householdId" to householdId)
                    }
                    ) + mapOf("currency" to (accounts.firstOrNull()?.currency ?: "USD")),
            ).optJSONObject("data")
        }.getOrNull()
        val assetCategoryGroups = accountBalancesData
            ?.optJSONArray("assetCategoryGroups")
            ?.toObjectList()
            ?.map(::parseAssetCategoryGroup)
            ?: emptyList()
        val investmentsByCurrency = accountBalancesData
            ?.optJSONArray("investmentsByCurrency")
            ?.toObjectList()
            ?.map(::parseMoneyAmount)
            ?: emptyList()
        val investmentsTotal = reportData?.optJSONObject("investmentsTotal")?.let(::parseMoneyAmount)
            ?: accountBalancesData?.optJSONObject("investmentsTotal")?.let(::parseMoneyAmount)
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
            assetCategories = assetCategories,
            assetCategoryGroups = assetCategoryGroups,
            investmentsByCurrency = investmentsByCurrency,
            investmentsTotal = investmentsTotal,
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

    override suspend fun createAccount(
        name: String,
        currency: String,
        initialBalance: String,
        accountType: String,
        householdId: String?,
        assetCategoryId: String?,
    ): ApiResult<AccountSummary> = safeCall {
        val ownershipType = if (householdId.isNullOrBlank()) "personal" else "shared"
        request(
            path = "/api/v1/accounts",
            method = "POST",
            body = JSONObject()
                .put("name", name.trim().take(80))
                .put("accountType", accountType)
                .put("ownershipType", ownershipType)
                .apply { householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) } }
                .apply { assetCategoryId?.takeIf { it.isNotBlank() }?.let { put("assetCategoryId", it) } }
                .put("currency", currency)
                .put("initialBalance", initialBalance)
                .toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        ).dataObject().let(::parseAccount)
    }

    override suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary> = safeCall {
        val body = JSONObject()
            .put("name", account.name.take(80))
            .put("currentBalance", account.currentBalance)
            .put("currency", account.currency)
            .put("assetCategoryId", account.assetCategoryId?.takeIf { it.isNotBlank() } ?: JSONObject.NULL)
        account.version?.let { body.put("version", it) }
        request(
            path = "/api/v1/accounts/${account.id.urlEncodePath()}",
            method = "PATCH",
            body = body.toString(),
        ).dataObject().let(::parseAccount)
    }

    override suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary> = safeCall {
        request(path = "/api/v1/accounts/${accountId.urlEncodePath()}/archive", method = "POST")
            .dataObject()
            .let(::parseAccount)
    }

    override suspend fun createAssetCategory(request: AssetCategoryCreateRequest): ApiResult<AssetCategory> = safeCall {
        request(
            path = "/api/v1/asset-categories",
            method = "POST",
            body = request.toJson().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_OK),
        ).dataObject().let(::parseAssetCategory)
    }

    override suspend fun updateAssetCategory(category: AssetCategory): ApiResult<AssetCategory> = safeCall {
        val body = JSONObject()
            .put("name", category.name.take(80))
            .put("manualAmount", category.manualAmount)
            .put("isInvestment", category.isInvestment)
            .put("assetType", category.assetType)
        category.version?.let { body.put("version", it) }
        request(
            path = "/api/v1/asset-categories/${category.id.urlEncodePath()}",
            method = "PATCH",
            body = body.toString(),
        ).dataObject().let(::parseAssetCategory)
    }

    override suspend fun archiveAssetCategory(categoryId: String): ApiResult<AssetCategory> = safeCall {
        request(path = "/api/v1/asset-categories/${categoryId.urlEncodePath()}/archive", method = "POST")
            .dataObject()
            .let(::parseAssetCategory)
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

    override suspend fun createCategory(
        name: String,
        householdId: String?,
        categoryType: String,
    ): ApiResult<CategorySummary> = safeCall {
        val type = normalizeTransactionCategoryType(categoryType)
        request(
            path = "/api/v1/categories",
            method = "POST",
            body = JSONObject()
                .put("name", name.trim().take(80))
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
        val body = JSONObject()
            .put("name", category.name.take(80))
            .apply { category.version?.let { put("version", it) } }
        request(
            path = "/api/v1/categories/${category.id.urlEncodePath()}",
            method = "PATCH",
            body = body.toString(),
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
                .put("amount", transaction.amount)
                .put("description", transaction.description)
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

    override suspend fun createCaptureDraft(request: CaptureDraftCreateRequest): ApiResult<CaptureDraft> = safeCall {
        request(
            path = "/api/v1/capture-drafts",
            method = "POST",
            body = request.toJson().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_OK),
        ).captureDraftObject().let(::parseCaptureDraft)
    }

    override suspend fun listCaptureDrafts(status: String): ApiResult<List<CaptureDraft>> = safeCall {
        request(
            path = "/api/v1/capture-drafts",
            method = "GET",
            query = status.takeIf { it.isNotBlank() }?.let { mapOf("status" to it) } ?: emptyMap(),
        ).captureDraftItems().map(::parseCaptureDraft)
    }

    override suspend fun updateCaptureDraft(
        draftId: String,
        request: CaptureDraftUpdateRequest,
    ): ApiResult<CaptureDraft> = safeCall {
        request(
            path = "/api/v1/capture-drafts/${draftId.urlEncodePath()}",
            method = "PATCH",
            body = request.toJsonForApi().toString(),
        ).captureDraftObject().let(::parseCaptureDraft)
    }

    override suspend fun confirmCaptureDraft(draftId: String): ApiResult<CaptureDraft> = safeCall {
        request(
            path = "/api/v1/capture-drafts/${draftId.urlEncodePath()}/confirm",
            method = "POST",
            expectedCodes = setOf(HttpURLConnection.HTTP_OK, HttpURLConnection.HTTP_CREATED),
        ).captureDraftObject().let(::parseCaptureDraft)
    }

    override suspend fun discardCaptureDraft(draftId: String): ApiResult<Unit> = safeCall {
        request(
            path = "/api/v1/capture-drafts/${draftId.urlEncodePath()}/discard",
            method = "POST",
            expectedCodes = setOf(HttpURLConnection.HTTP_OK, HttpURLConnection.HTTP_NO_CONTENT),
        )
        Unit
    }

    override suspend fun screenshotOcr(
        imageBytes: ByteArray,
        contentType: String,
        capturedAt: String?,
        householdId: String?,
    ): ApiResult<ScreenshotOcrResponse> = safeCall {
        val boundary = "Boundary-${System.currentTimeMillis()}"
        val connection = (URL("${config.normalizedBaseUrl}/api/v1/capture-drafts/screenshot-ocr").openConnection() as HttpURLConnection)
        connection.requestMethod = "POST"
        connection.connectTimeout = 30_000
        connection.readTimeout = 30_000
        connection.doOutput = true
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        tokenStore.readAccessToken()?.let {
            connection.setRequestProperty("Authorization", "Bearer $it")
        }
        connection.outputStream.use { stream ->
            val partBuilder = StringBuilder()
            partBuilder.append("--$boundary\r\n")
            partBuilder.append("Content-Disposition: form-data; name=\"image\"; filename=\"screenshot.jpg\"\r\n")
            partBuilder.append("Content-Type: ${contentType.ifBlank { "image/jpeg" }}\r\n\r\n")
            stream.write(partBuilder.toString().toByteArray(Charsets.UTF_8))
            stream.write(imageBytes)
            stream.write("\r\n".toByteArray(Charsets.UTF_8))
            if (!capturedAt.isNullOrBlank()) {
                val capPart = "--$boundary\r\nContent-Disposition: form-data; name=\"capturedAt\"\r\n\r\n$capturedAt\r\n"
                stream.write(capPart.toByteArray(Charsets.UTF_8))
            }
            if (!householdId.isNullOrBlank()) {
                val hhPart = "--$boundary\r\nContent-Disposition: form-data; name=\"householdId\"\r\n\r\n$householdId\r\n"
                stream.write(hhPart.toByteArray(Charsets.UTF_8))
            }
            stream.write("--$boundary--\r\n".toByteArray(Charsets.UTF_8))
        }
        val code = connection.responseCode
        val text = connection.readText(code)
        if (code !in setOf(HttpURLConnection.HTTP_OK)) {
            throw ApiException(parseError(text, code), code)
        }
        parseScreenshotOcrResponse(JSONObject(text))
    }

    override suspend fun listPlanningPlans(
        scope: String,
        month: String,
        householdId: String?,
    ): ApiResult<PlanningPlan?> = safeCall {
        request(
            path = "/api/v1/planning/plans",
            method = "GET",
            query = planningScopeQuery(scope, householdId) + mapOf("month" to month),
        ).planningPlanObjectOrNull()?.let(::parsePlanningPlan)
    }

    override suspend fun listPlanningPlanHistory(
        scope: String,
        householdId: String?,
    ): ApiResult<List<PlanningPlan>> = safeCall {
        request(
            path = "/api/v1/planning/plans/history",
            method = "GET",
            query = planningScopeQuery(scope, householdId),
        ).planningPlanItems().map(::parsePlanningPlan)
    }

    override suspend fun createPlanningPlan(request: PlanningPlanCreateRequest): ApiResult<PlanningPlan> = safeCall {
        request(
            path = "/api/v1/planning/plans",
            method = "POST",
            body = request.toJson().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_OK),
        ).planningPlanObject().let(::parsePlanningPlan)
    }

    override suspend fun getPlanningPlan(planId: String): ApiResult<PlanningPlan> = safeCall {
        request(
            path = "/api/v1/planning/plans/${planId.urlEncodePath()}",
            method = "GET",
        ).planningPlanObject().let(::parsePlanningPlan)
    }

    override suspend fun createPlanningIncomeSource(
        planId: String,
        request: PlanningIncomeSourceCreateRequest,
    ): ApiResult<PlanningIncomeSource> = safeCall {
        this.request(
            path = "/api/v1/planning/plans/${planId.urlEncodePath()}/income-sources",
            method = "POST",
            body = request.toJson().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_OK),
        ).planningIncomeSourceObject().let(::parsePlanningIncomeSource)
    }

    override suspend fun updatePlanningIncomeSource(
        incomeSourceId: String,
        request: PlanningIncomeSourceUpdateRequest,
    ): ApiResult<PlanningIncomeSource> = safeCall {
        this.request(
            path = "/api/v1/planning/income-sources/${incomeSourceId.urlEncodePath()}",
            method = "PATCH",
            body = request.toJsonForApi().toString(),
        ).planningIncomeSourceObject().let(::parsePlanningIncomeSource)
    }

    override suspend fun confirmPlanningIncomeSource(incomeSourceId: String): ApiResult<PlanningIncomeSource> = safeCall {
        request(
            path = "/api/v1/planning/income-sources/${incomeSourceId.urlEncodePath()}/confirm",
            method = "POST",
            expectedCodes = setOf(HttpURLConnection.HTTP_OK, HttpURLConnection.HTTP_CREATED),
        ).planningIncomeSourceObject().let(::parsePlanningIncomeSource)
    }

    override suspend fun deletePlanningIncomeSource(incomeSourceId: String): ApiResult<Unit> = safeCall {
        request(
            path = "/api/v1/planning/income-sources/${incomeSourceId.urlEncodePath()}",
            method = "DELETE",
            expectedCodes = setOf(HttpURLConnection.HTTP_NO_CONTENT, HttpURLConnection.HTTP_OK),
        )
        Unit
    }

    override suspend fun createPlanningAllocation(
        planId: String,
        request: PlanningAllocationCreateRequest,
    ): ApiResult<PlanningAllocation> = safeCall {
        this.request(
            path = "/api/v1/planning/plans/${planId.urlEncodePath()}/allocations",
            method = "POST",
            body = request.toJsonForApi().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_OK),
        ).planningAllocationObject().let(::parsePlanningAllocation)
    }

    override suspend fun updatePlanningAllocation(
        allocationId: String,
        request: PlanningAllocationUpdateRequest,
    ): ApiResult<PlanningAllocation> = safeCall {
        this.request(
            path = "/api/v1/planning/allocations/${allocationId.urlEncodePath()}",
            method = "PATCH",
            body = request.toJsonForApi().toString(),
        ).planningAllocationObject().let(::parsePlanningAllocation)
    }

    override suspend fun deletePlanningAllocation(allocationId: String): ApiResult<Unit> = safeCall {
        request(
            path = "/api/v1/planning/allocations/${allocationId.urlEncodePath()}",
            method = "DELETE",
            expectedCodes = setOf(HttpURLConnection.HTTP_NO_CONTENT, HttpURLConnection.HTTP_OK),
        )
        Unit
    }

    override suspend fun copyPlanningPlan(planId: String, request: PlanningPlanCopyRequest): ApiResult<PlanningPlan> = safeCall {
        this.request(
            path = "/api/v1/planning/plans/${planId.urlEncodePath()}/copy",
            method = "POST",
            body = request.toJson().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED, HttpURLConnection.HTTP_OK),
        ).planningPlanObject().let(::parsePlanningPlan)
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
            ApiResult.Failure(error.message ?: "Ошибка API", error, error.statusCode)
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
            if (authorize && code.isAuthenticationFailureStatus()) {
                tokenStore.clear()
            }
            throw ApiException(parseError(text, code), code)
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
            val error = JSONObject(text).optJSONObject("error")
            when (error?.optString("code")) {
                "ACCOUNT_CURRENCY_IMMUTABLE_AFTER_TRANSACTIONS" ->
                    "Валюту счета нельзя изменить после создания операций."
                else -> error?.optString("message")?.takeIf { it.isNotBlank() }
            }
        }.getOrNull() ?: fallback
    }
}

class ApiException(
    message: String,
    val statusCode: Int? = null,
) : Exception(message)

private fun Int.isAuthenticationFailureStatus(): Boolean {
    return this == HttpURLConnection.HTTP_UNAUTHORIZED || this == HttpURLConnection.HTTP_FORBIDDEN
}

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
        displayName = actor?.optString("displayName")?.takeIf { it.isNotBlank() }
            ?: userId?.take(8)?.let { "Пользователь $it" },
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
        assetCategoryId = json.optString("assetCategoryId").takeIf { it.isNotBlank() && it != "null" },
        version = json.optIntOrNull("version"),
    )
}

private fun parseAssetCategory(json: JSONObject): AssetCategory {
    return AssetCategory(
        id = json.optString("id"),
        name = userFacingSeedText(json.optString("name", "Категория активов")),
        scopeType = json.optString("scopeType", json.optString("scope", "personal")),
        householdId = json.optNullableString("householdId"),
        ownerUserId = json.optNullableString("ownerUserId"),
        currency = json.optString("currency", "USD"),
        manualAmount = json.optString("manualAmount", "0"),
        isInvestment = json.optBoolean("isInvestment", false),
        assetType = json.optString("assetType", json.optString("accountType", "bank")),
        recordStatus = json.optString("recordStatus", json.optString("status", "active")),
        version = json.optIntOrNull("version"),
    )
}

private fun parseAssetCategoryGroup(json: JSONObject): AssetCategoryGroup {
    val category = json.optJSONObject("assetCategory") ?: json.optJSONObject("category")
    val categoryId = json.optNullableString("assetCategoryId")
        ?: category?.optNullableString("id")
        ?: json.optNullableString("id")
        ?: ""
    val manualAmount = json.optString("manualAmount", category?.optString("manualAmount", "0") ?: "0")
    val accountsTotal = json.optString(
        "linkedAccountsTotal",
        json.optString(
            "accountsTotal",
            json.optString("accountsBalance", json.optString("accountsAmount", "0")),
        ),
    )
    val fallbackTotal = (accountsTotal.toApiMoney() + manualAmount.toApiMoney()).toPlainString()
    return AssetCategoryGroup(
        assetCategoryId = categoryId,
        name = userFacingSeedText(
            json.optString("assetCategoryName").ifBlank {
                json.optString("name").ifBlank {
                    category?.optString("name", "Категория активов").orEmpty()
                }
            },
        ),
        scopeType = json.optString("scopeType", category?.optString("scopeType", "personal") ?: "personal"),
        householdId = json.optNullableString("householdId") ?: category?.optNullableString("householdId"),
        currency = json.optString("currency", category?.optString("currency", "USD") ?: "USD"),
        manualAmount = manualAmount,
        accountsTotal = accountsTotal,
        totalAmount = json.optString(
            "currentBalanceTotal",
            json.optString(
                "totalAmount",
                json.optString("total", json.optString("currentBalance", fallbackTotal)),
            ),
        ),
        isInvestment = json.optBoolean("isInvestment", category?.optBoolean("isInvestment", false) ?: false),
        assetType = json.optString("assetType", category?.optString("assetType", "bank") ?: "bank"),
        accountCount = json.optInt("accountCount", json.optJSONArray("accounts")?.length() ?: 0),
    )
}

private fun parseMoneyAmount(json: JSONObject): MoneyAmount {
    return MoneyAmount(
        currency = json.optString("currency", "USD"),
        amount = json.optString(
            "investmentsTotal",
            json.optString("amount", json.optString("total", json.optString("value", "0"))),
        ),
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

private fun parseCaptureDraft(json: JSONObject): CaptureDraft {
    return CaptureDraft(
        id = json.optString("id").ifBlank { json.optString("draftId") },
        status = json.optString("status", "pending"),
        amount = json.optString("amount"),
        currency = json.optString("currency"),
        description = json.optString("description").takeIf { it.isNotBlank() && it != "null" },
        merchantName = json.optString("merchantName").takeIf { it.isNotBlank() && it != "null" },
        capturedAt = json.optString("capturedAt").takeIf { it.isNotBlank() && it != "null" },
        occurredAt = json.optString("occurredAt"),
        captureSource = json.optString("captureSource"),
        confidence = json.optDouble("confidence", 0.0),
        sourceAppPackage = json.optString("sourceAppPackage").takeIf { it.isNotBlank() && it != "null" },
        sourceAppLabel = json.optString("sourceAppLabel").takeIf { it.isNotBlank() && it != "null" },
        evidenceHash = json.optString("evidenceHash"),
        idempotencyKey = json.optString("idempotencyKey"),
        accountId = json.optString("accountId").takeIf { it.isNotBlank() && it != "null" },
        categoryId = json.optString("categoryId").takeIf { it.isNotBlank() && it != "null" },
        version = json.optIntOrNull("version"),
    )
}

private fun parsePlanningPlan(json: JSONObject): PlanningPlan {
    val summary = json.optJSONObject("summary")
    return PlanningPlan(
        id = json.optString("id").ifBlank { json.optString("planId") },
        scope = json.optString("scope"),
        month = json.optString("month"),
        currency = json.optString("currency"),
        householdId = json.optNullableString("householdId"),
        totalPlannedIncome = summary?.optString("totalPlannedIncome", "0")
            ?: json.optString("totalPlannedIncome", "0"),
        previousMonthSurplus = summary?.optString("previousMonthSurplus", "0")
            ?: json.optString("previousMonthSurplus", "0"),
        allocatedTotal = summary?.optString("totalAllocatedAmount", "0")
            ?: json.optString("allocatedTotal", "0"),
        remainingAmount = summary?.optString("unallocatedAmount", "0")
            ?: json.optString("remainingAmount", "0"),
        overallocatedAmount = json.optString(
            "overallocatedAmount",
            if (summary?.optBoolean("overallocated", false) == true) {
                summary.optString("unallocatedAmount", "0").planningAbsoluteAmount()
            } else {
                "0"
            },
        ),
        isUnderallocated = summary?.optBoolean("underallocated", false)
            ?: json.optBoolean("isUnderallocated", false),
        isOverallocated = summary?.optBoolean("overallocated", false)
            ?: json.optBoolean("isOverallocated", false),
        status = json.optNullableString("status") ?: summary?.optNullableString("status"),
        progressStatus = json.optNullableString("progressStatus") ?: summary?.optNullableString("progressStatus"),
        progressPercent = json.optNullableString("progressPercent") ?: summary?.optNullableString("progressPercent"),
        incomeSources = json.optJSONArray("incomeSources")?.toObjectList()?.map(::parsePlanningIncomeSource)
            ?: emptyList(),
        allocations = json.optJSONArray("allocations")?.toObjectList()?.map(::parsePlanningAllocation)
            ?: emptyList(),
        version = json.optIntOrNull("version"),
    )
}

private fun parsePlanningIncomeSource(json: JSONObject): PlanningIncomeSource {
    return PlanningIncomeSource(
        id = json.optString("id").ifBlank { json.optString("incomeSourceId") },
        planId = json.optString("planId"),
        amount = json.optString("amount"),
        source = json.optString("source"),
        description = json.optNullableString("description"),
        dayOfMonth = json.optIntOrNull("dayOfMonth"),
        confirmed = json.optString("confirmationState").ifBlank {
            if (json.optBoolean("confirmed", false)) "confirmed" else "planned"
        } == "confirmed",
        effectiveDate = json.optNullableString("effectiveDate"),
        version = json.optIntOrNull("version"),
    )
}

private fun parsePlanningAllocation(json: JSONObject): PlanningAllocation {
    val targetType = json.planningAllocationTargetType()
    return PlanningAllocation(
        id = json.optString("id").ifBlank { json.optString("allocationId") },
        planId = json.optString("planId"),
        targetType = targetType,
        targetId = json.planningAllocationTargetId(targetType),
        targetSnapshot = json.optNullableJsonString("targetSnapshot"),
        requiresAttention = json.optBoolean("requiresAttention", false),
        attentionReason = json.optNullableString("attentionReason"),
        comment = json.optNullableString("comment"),
        allocationMode = json.optString("allocationMode"),
        allocationValue = json.optString("allocationValue"),
        calculatedAmount = json.optString("calculatedAmount"),
        recurrenceType = json.optNullableString("recurrenceType"),
        isSavingsGoal = json.optBoolean("isSavingsGoal", json.optBoolean("savingsGoal", false)),
        goalTargetAmount = json.optNullableString("goalTargetAmount"),
        goalDueMonth = json.optNullableString("goalDueMonth"),
        goalMonthlyAmount = json.optNullableString("goalMonthlyAmount"),
        actualAmount = json.optNullableString("actualAmount"),
        varianceAmount = json.optNullableString("varianceAmount"),
        progressPercent = json.optNullableString("progressPercent"),
        progressStatus = json.optNullableString("progressStatus"),
        status = json.optNullableString("status"),
        version = json.optIntOrNull("version"),
    )
}

private fun CaptureDraftCreateRequest.toJson(): JSONObject {
    return JSONObject()
        .put("amount", amount)
        .put("currency", currency)
        .put("description", description)
        .put("merchantName", merchantName)
        .put("capturedAt", capturedAt)
        .put("occurredAt", occurredAt)
        .put("captureSource", captureSource)
        .put("idempotencyKey", idempotencyKey)
        .put("confidence", confidence.toConfidenceString())
        .put("sourceAppPackage", sourceAppPackage)
        .put("sourceAppLabel", sourceAppLabel)
        .put("evidenceHash", evidenceHash)
        .apply { categoryId?.takeIf { it.isNotBlank() }?.let { put("categoryId", it) } }
}

private fun PlanningPlanCreateRequest.toJson(): JSONObject {
    return JSONObject()
        .put("scope", scope)
        .put("month", month)
        .put("currency", currency)
        .apply { householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) } }
}

private fun PlanningPlanCopyRequest.toJson(): JSONObject {
    return JSONObject()
        .put("targetMonth", targetMonth)
}

private fun AssetCategoryCreateRequest.toJson(): JSONObject {
    return JSONObject()
        .put("name", name.trim().take(80))
        .put("scopeType", if (scopeType == "household") "household" else "personal")
        .put("currency", currency)
        .put("manualAmount", manualAmount)
        .put("isInvestment", isInvestment)
        .put("assetType", assetType)
        .apply {
            householdId?.takeIf { it.isNotBlank() && scopeType == "household" }?.let { put("householdId", it) }
        }
}

private fun PlanningIncomeSourceCreateRequest.toJson(): JSONObject {
    return JSONObject()
        .put("amount", amount)
        .put("source", source)
        .put("dayOfMonth", dayOfMonth)
        .apply {
            description?.let { put("description", it) }
            effectiveDate?.let { put("effectiveDate", it) }
        }
}

internal fun PlanningIncomeSourceUpdateRequest.toJsonForApi(): JSONObject {
    return JSONObject().apply {
        amount?.let { put("amount", it) }
        source?.let { put("source", it) }
        description?.let { put("description", it) }
        dayOfMonth?.let { put("dayOfMonth", it) }
        confirmed?.let { put("confirmed", it) }
        effectiveDate?.let { put("effectiveDate", it) }
        version?.let { put("version", it) }
    }
}

internal fun PlanningAllocationCreateRequest.toJsonForApi(): JSONObject {
    return JSONObject()
        .put("targetType", targetType)
        .put("targetId", targetId)
        .put("allocationMode", allocationMode)
        .put("allocationValue", allocationValue)
        .apply {
            targetSnapshot?.let { put("targetSnapshot", it) }
            comment?.let { put("comment", it) }
            recurrenceType?.let { put("recurrenceType", it) }
            put("isSavingsGoal", isSavingsGoal)
            if (isSavingsGoal) {
                goalTargetAmount?.let { put("goalTargetAmount", it) }
                goalDueMonth?.let { put("goalDueMonth", it) }
            }
        }
}

internal fun PlanningAllocationUpdateRequest.toJsonForApi(): JSONObject {
    return JSONObject().apply {
        targetType?.let { put("targetType", it) }
        targetId?.let { put("targetId", it) }
        targetSnapshot?.let { put("targetSnapshot", it) }
        requiresAttention?.let { put("requiresAttention", it) }
        attentionReason?.let { put("attentionReason", it) }
        comment?.let { put("comment", it) }
        allocationMode?.let { put("allocationMode", it) }
        allocationValue?.let { put("allocationValue", it) }
        recurrenceType?.let { put("recurrenceType", it) }
        isSavingsGoal?.let { put("isSavingsGoal", it) }
        if (isSavingsGoal == false) {
            put("goalTargetAmount", JSONObject.NULL)
            put("goalDueMonth", JSONObject.NULL)
        } else {
            goalTargetAmount?.let { put("goalTargetAmount", it) }
            goalDueMonth?.let { put("goalDueMonth", it) }
        }
        version?.let { put("version", it) }
    }
}

internal fun CaptureDraftUpdateRequest.toJsonForApi(): JSONObject {
    return JSONObject().apply {
        amount?.let { put("amount", it) }
        currency?.let { put("currency", it) }
        description?.let { put("description", it) }
        merchantName?.let { put("merchantName", it) }
        occurredAt?.let { put("occurredAt", it) }
        confidence?.let { put("confidence", it.toConfidenceString()) }
        accountId?.let { put("accountId", it) }
        categoryId?.let { put("categoryId", it) }
    }
}

private fun Double.toConfidenceString(): String {
    return BigDecimal.valueOf(coerceIn(0.0, 1.0))
        .setScale(4, RoundingMode.HALF_UP)
        .toPlainString()
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

private fun JSONObject.captureDraftItems(): List<JSONObject> {
    return optJSONArray("items")?.toObjectList()
        ?: optJSONObject("data")?.optJSONArray("items")?.toObjectList()
        ?: optJSONArray("data")?.toObjectList()
        ?: emptyList()
}

private fun JSONObject.planningPlanItems(): List<JSONObject> {
    return optJSONArray("items")?.toObjectList()
        ?: optJSONObject("data")?.optJSONArray("items")?.toObjectList()
        ?: optJSONObject("data")?.optJSONArray("plans")?.toObjectList()
        ?: optJSONArray("plans")?.toObjectList()
        ?: optJSONArray("data")?.toObjectList()
        ?: emptyList()
}

private fun JSONObject.dataObject(): JSONObject = optJSONObject("data") ?: this

private fun JSONObject.planningPlanObjectOrNull(): JSONObject? {
    return optJSONObject("plan")
        ?: optJSONObject("planningPlan")
        ?: optJSONObject("data")?.optJSONObject("plan")
        ?: optJSONObject("data")?.optJSONObject("planningPlan")
        ?: optJSONObject("data")
        ?: takeUnless { has("data") && isNull("data") }
}

private fun JSONObject.captureDraftObject(): JSONObject {
    return optJSONObject("captureDraft")
        ?: optJSONObject("data")?.optJSONObject("captureDraft")
        ?: dataObject()
}

private fun JSONObject.planningPlanObject(): JSONObject {
    return optJSONObject("plan")
        ?: optJSONObject("planningPlan")
        ?: optJSONObject("data")?.optJSONObject("plan")
        ?: optJSONObject("data")?.optJSONObject("planningPlan")
        ?: dataObject()
}

private fun JSONObject.planningIncomeSourceObject(): JSONObject {
    return optJSONObject("incomeSource")
        ?: optJSONObject("planningIncomeSource")
        ?: optJSONObject("data")?.optJSONObject("incomeSource")
        ?: optJSONObject("data")?.optJSONObject("planningIncomeSource")
        ?: dataObject()
}

private fun JSONObject.planningAllocationObject(): JSONObject {
    return optJSONObject("allocation")
        ?: optJSONObject("planningAllocation")
        ?: optJSONObject("data")?.optJSONObject("allocation")
        ?: optJSONObject("data")?.optJSONObject("planningAllocation")
        ?: dataObject()
}

private fun JSONObject.optIntOrNull(name: String): Int? = if (has(name) && !isNull(name)) optInt(name) else null

private fun JSONObject.optNullableString(name: String): String? {
    return optString(name).takeIf { has(name) && !isNull(name) && it.isNotBlank() && it != "null" }
}

private fun JSONObject.optNullableJsonString(name: String): String? {
    if (!has(name) || isNull(name)) return null
    val value = opt(name) ?: return null
    return when (value) {
        is JSONObject, is JSONArray -> value.toString()
        else -> value.toString().takeIf { it.isNotBlank() && it != "null" }
    }
}

private fun JSONObject.planningAllocationTargetType(): String {
    val explicit = optString("targetType").takeIf { it.isNotBlank() && it != "null" }
    return explicit ?: when {
        optNullableString("assetCategoryId") != null -> "investment_asset_category"
        optNullableString("assetId") != null -> "asset"
        optNullableString("accountId") != null -> "account"
        optNullableString("categoryId") != null -> "expense_category"
        else -> ""
    }
}

private fun JSONObject.planningAllocationTargetId(targetType: String): String? {
    return optNullableString("targetId") ?: when (targetType) {
        "investment_asset_category" -> optNullableString("assetCategoryId")
        "asset" -> optNullableString("assetId")
        "account" -> optNullableString("accountId")
        "expense_category" -> optNullableString("categoryId")
        else -> optNullableString("assetId")
            ?: optNullableString("accountId")
            ?: optNullableString("categoryId")
    }
}

private fun String.planningAbsoluteAmount(): String = trim().removePrefix("-")

private fun String.toApiMoney(): BigDecimal {
    return runCatching { BigDecimal(trim().ifBlank { "0" }) }.getOrDefault(BigDecimal.ZERO)
}

private fun JSONArray.toObjectList(): List<JSONObject> {
    return (0 until length()).mapNotNull { index -> optJSONObject(index) }
}

private fun String.urlEncode(): String = URLEncoder.encode(this, Charsets.UTF_8.name())

private fun String.urlEncodePath(): String = urlEncode().replace("+", "%20")

private fun planningScopeQuery(scope: String, householdId: String?): Map<String, String> {
    return mapOf("scope" to scope) + (
        householdId
            ?.takeIf { it.isNotBlank() }
            ?.let { mapOf("householdId" to it) }
            ?: emptyMap()
        )
}

private fun parseScreenshotOcrResponse(json: JSONObject): ScreenshotOcrResponse {
    val data = json.optJSONObject("data") ?: json
    val itemsArray = data.optJSONArray("items") ?: return ScreenshotOcrResponse(emptyList())
    val items = (0 until itemsArray.length()).mapNotNull { index ->
        val item = itemsArray.optJSONObject(index) ?: return@mapNotNull null
        val categoryAggregate = item.optJSONObject("categoryAggregate")
        ScreenshotOcrCandidate(
            candidateType = item.optString("candidateType", "categoryAggregate"),
            externalLabel = categoryAggregate?.optString("externalLabel").orEmpty(),
            amount = item.optString("amount"),
            currency = item.optString("currency"),
            operationCount = item.optInt("operationCount", 0),
            description = item.optString("description"),
            confidence = item.optDouble("confidence", 0.0),
            idempotencyKey = item.optString("idempotencyKey"),
            evidenceHash = item.optString("evidenceHash"),
        )
    }
    return ScreenshotOcrResponse(items = items)
}

private fun nowIso(): String = java.time.Instant.now().toString()
