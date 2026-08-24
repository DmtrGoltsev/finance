package com.finance.mvp.api

import com.finance.mvp.session.SecureTokenStore
import com.finance.mvp.session.StoredSessionTokens
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.math.BigDecimal
import java.math.RoundingMode
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Locale
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONException
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
    suspend fun dashboard(startDate: String? = null, endDate: String? = null): ApiResult<FinanceDashboard>
    suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String = "12.34",
        accountType: String = "cash",
        ownershipType: String = if (householdId.isNullOrBlank()) "personal" else "shared",
        isPaymentAccount: Boolean = true,
    ): ApiResult<AccountSummary>
    suspend fun createAccount(
        name: String,
        currency: String,
        initialBalance: String,
        accountType: String,
        householdId: String?,
        assetCategoryId: String? = null,
        isPaymentAccount: Boolean = true,
    ): ApiResult<AccountSummary>
    suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary>
    suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary>
    suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary>
    suspend fun createAssetCategory(request: AssetCategoryCreateRequest): ApiResult<AssetCategory> =
        ApiResult.Failure("Категории активов не поддерживаются этим клиентом")
    suspend fun createInvestmentMigration(request: InvestmentMigrationCreateRequest): ApiResult<InvestmentMigrationResult> =
        ApiResult.Failure("Миграция инвестиционных групп не поддерживается этим клиентом")
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
        transactionDate: String = todayDate(),
    ): ApiResult<TransactionSummary>
    suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary>
    suspend fun deleteTransaction(transactionId: String): ApiResult<Unit>
    suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary>
    suspend fun createDemoTransfer(
        source: AccountSummary,
        destination: AccountSummary,
        amount: String = "1.00",
        transactionDate: String = todayDate(),
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
    suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> =
        ApiResult.Failure("Sync push is not supported by this client")
    suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> =
        ApiResult.Failure("Sync pull is not supported by this client")
    suspend fun logout(): ApiResult<Unit>
}

data class SessionStatus(
    val isAuthenticated: Boolean,
    val displayName: String?,
    val householdId: String?,
    val userId: String? = null,
    val sessionId: String? = null,
)

internal data class AuthenticatedSessionLease(
    val generation: Long,
    val sessionIdentity: String,
    val authenticatedUserId: String,
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
    val isPaymentAccount: Boolean = true,
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
    val iconKey: String = "",
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
    val iconKey: String = "",
    val accountCount: Int? = null,
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
    val iconKey: String = "",
)

data class InvestmentMigrationCreateRequest(
    val assetCategoryId: String,
    val name: String,
    val iconKey: String? = null,
    val color: String? = null,
    val assetType: String,
    val currency: String,
    val scope: String,
    val householdId: String? = null,
    val accountIds: List<String>,
    val accountVersions: Map<String, Int>,
)

data class InvestmentMigrationResult(
    val assetCategory: AssetCategory,
    val accounts: List<AccountSummary>,
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
    val transactionDate: String = occurredAt.take(10),
    val createdAt: String = occurredAt,
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
    val occurredDate: String,
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
    val occurredDate: String? = null,
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
    val occurredDate: String,
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

data class SyncMutationRequest(
    val clientMutationId: String,
    val entityType: String,
    val entityId: String,
    val operation: String,
    val baseVersion: Int? = null,
    val payload: JSONObject? = null,
)

data class SyncPushRequest(
    val deviceId: String,
    val clientSchemaVersion: Int = ANDROID_SYNC_SCHEMA_VERSION,
    val mutations: List<SyncMutationRequest>,
)

data class SyncMutationResult(
    val clientMutationId: String,
    val entityType: String,
    val entityId: String,
    val operation: String,
    val status: String,
    val serverVersion: Int? = null,
    val changeSeq: Long? = null,
    val errorCode: String? = null,
    val message: String? = null,
    val data: JSONObject? = null,
)

data class SyncPushResponse(
    val deviceId: String,
    val serverTime: String,
    val results: List<SyncMutationResult>,
)

data class SyncPullRequest(
    val deviceId: String,
    val clientSchemaVersion: Int = ANDROID_SYNC_SCHEMA_VERSION,
    val cursor: Long = 0,
    val limit: Int = 100,
    val entityTypes: List<String>? = null,
)

data class SyncChange(
    val seq: Long,
    val entityType: String,
    val entityId: String,
    val changeType: String,
    val entityVersion: Int? = null,
    val entityUpdatedAt: String? = null,
    val changedByUserId: String? = null,
    val clientMutationId: String? = null,
    val payload: JSONObject? = null,
    val tombstonePayload: JSONObject? = null,
    val createdAt: String,
)

data class SyncPullResponse(
    val changes: List<SyncChange>,
    val nextCursor: Long,
    val hasMore: Boolean,
    val serverTime: String,
)

const val ANDROID_SYNC_SCHEMA_VERSION: Int = 1

enum class ApiFailureKind {
    HTTP,
    NETWORK,
    CONTRACT,
    SESSION_CHANGED,
    UNKNOWN,
}

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class Failure(
        val message: String,
        val cause: Throwable? = null,
        val statusCode: Int? = null,
        val kind: ApiFailureKind = defaultApiFailureKind(statusCode, cause),
    ) : ApiResult<Nothing> {
        val isNetworkFailure: Boolean
            get() = kind == ApiFailureKind.NETWORK
    }
}

private fun defaultApiFailureKind(statusCode: Int?, cause: Throwable?): ApiFailureKind {
    return when {
        statusCode != null -> ApiFailureKind.HTTP
        cause is IOException -> ApiFailureKind.NETWORK
        cause is JSONException || cause is IllegalArgumentException || cause is IllegalStateException ->
            ApiFailureKind.CONTRACT
        cause != null -> ApiFailureKind.UNKNOWN
        else -> ApiFailureKind.UNKNOWN
    }
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
        persistBearerSession(response)
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
            clearSession()
            return@safeCall RegistrationResult.Accepted(
                response.optString("message").takeIf { it.isNotBlank() }
                    ?: "Заявка на регистрацию принята",
            )
        }
        persistBearerSession(response)
        RegistrationResult.Authenticated(parseSession(response))
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> = safeCall { currentSessionStatus() }

    override suspend fun dashboard(startDate: String?, endDate: String?): ApiResult<FinanceDashboard> = safeCall {
        val session = currentSessionStatus()
        val accounts = requestAllPages(
            path = "/api/v1/accounts",
            query = mapOf("ownershipType" to "personal"),
        )
            .map(::parseAccount)
            .filter { it.ownershipType == "personal" && it.householdId == null }
        val categories = requestAllPages(
            path = "/api/v1/categories",
            query = mapOf("scope" to "personal"),
        )
            .map(::parseCategory)
            .filter { it.scope != "household" && it.householdId == null }
        val assetCategories = runCatching {
            requestAllPages(
                path = "/api/v1/asset-categories",
                query = mapOf("scopeType" to "personal"),
            )
                .map(::parseAssetCategory)
                .filter { it.scopeType == "personal" && it.householdId == null }
        }.getOrDefault(emptyList())
        val dateQuery = reportDateQuery(startDate, endDate)
        val personalAccountIds = accounts.map { it.id }.toSet()
        val personalCategoryIds = categories.map { it.id }.toSet()
        val transactions = requestAllPages(
            path = "/api/v1/transactions",
            query = mapOf(
                "ownershipType" to "personal",
                "sort" to "-occurredAt",
            ) + dateQuery,
        ).map(::parseTransaction)
            .filter { transaction ->
                transaction.accountId in personalAccountIds &&
                    (transaction.categoryId == null || transaction.categoryId in personalCategoryIds) &&
                    (
                        transaction.counterpartyAccountId == null ||
                            transaction.counterpartyAccountId in personalAccountIds
                        ) &&
                    (transaction.type != "transfer" || transaction.counterpartyAccountId != null)
            }
            .sortedWith(transactionNewestFirstComparator)
        val reportData = runCatching {
            request(
                path = "/api/v1/reports/summary",
                method = "GET",
                query = mapOf("reportMode" to "personal") + dateQuery,
            ).optJSONObject("data")
        }.getOrNull()
        val totals = reportData
            ?.optJSONArray("totalsByCurrency")
            ?.toObjectList()
            ?.map(::parseMoneyTotal)
            ?: emptyList()
        val accountBalancesData = runCatching {
            request(
                path = "/api/v1/reports/account-balances",
                method = "GET",
                query = mapOf("reportMode" to "personal") + dateQuery,
            ).optJSONObject("data")
        }.getOrNull()
        val assetCategoryGroups = accountBalancesData
            ?.optJSONArray("assetCategoryGroups")
            ?.toObjectList()
            ?.map(::parseAssetCategoryGroup)
            ?: emptyList()
        val calculatedInvestmentsByCurrency = monthlyInvestmentTransfers(
            transactions = transactions,
            accounts = accounts,
            assetCategories = assetCategories,
        )
        val reportedInvestmentsByCurrency = reportData?.investmentTotalsByCurrency().orEmpty()
        val investmentsByCurrency = calculatedInvestmentsByCurrency.ifEmpty { reportedInvestmentsByCurrency }
        val investmentsTotal = investmentsByCurrency.firstOrNull()
        val reportTransferCount = runCatching {
            requestAllPages(
                path = "/api/v1/reports/transactions",
                query = mapOf(
                    "reportMode" to "personal",
                    "currency" to (accounts.firstOrNull()?.currency ?: "USD"),
                    "transactionTypes" to "transfer",
                ) + dateQuery,
            ).size
        }.getOrDefault(0)

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
        isPaymentAccount: Boolean,
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
                .put("isPaymentAccount", isPaymentAccount)
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
        isPaymentAccount: Boolean,
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
                .put("isPaymentAccount", isPaymentAccount)
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
            .put("isPaymentAccount", account.isPaymentAccount)
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

    override suspend fun createInvestmentMigration(
        request: InvestmentMigrationCreateRequest,
    ): ApiResult<InvestmentMigrationResult> = safeCall {
        request(
            path = "/api/v1/asset-categories/investment-migrations",
            method = "POST",
            body = request.toJsonForApi().toString(),
            expectedCodes = setOf(HttpURLConnection.HTTP_CREATED),
        ).dataObject().let(::parseInvestmentMigrationResult)
    }

    override suspend fun updateAssetCategory(category: AssetCategory): ApiResult<AssetCategory> = safeCall {
        request(
            path = "/api/v1/asset-categories/${category.id.urlEncodePath()}",
            method = "PATCH",
            body = category.toUpdateJsonForApi().toString(),
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
        transactionDate: String,
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
                .put("transactionDate", transactionDate)
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
        transactionDate: String,
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
                .put("transactionDate", transactionDate)
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
        screenshotOcrRequest(
            imageBytes = imageBytes,
            contentType = contentType,
            capturedAt = capturedAt,
            householdId = householdId,
        )
    }

    private suspend fun screenshotOcrRequest(
        imageBytes: ByteArray,
        contentType: String,
        capturedAt: String?,
        householdId: String?,
        allowRefreshRetry: Boolean = true,
        requiredSession: SessionExpectation? = null,
    ): ScreenshotOcrResponse {
        val requestSession = authorizedSession(requiredSession)
        val boundary = "Boundary-${System.currentTimeMillis()}"
        val connection = (URL("${config.normalizedBaseUrl}/api/v1/capture-drafts/screenshot-ocr").openConnection() as HttpURLConnection)
        connection.requestMethod = "POST"
        connection.connectTimeout = 30_000
        connection.readTimeout = 30_000
        connection.doOutput = true
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        requestSession?.accessToken?.let {
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
        if (code == HttpURLConnection.HTTP_UNAUTHORIZED) {
            when (
                if (allowRefreshRetry) refreshAccessToken(requestSession)
                else RefreshAttempt.REJECTED
            ) {
                RefreshAttempt.SUCCEEDED -> return screenshotOcrRequest(
                    imageBytes = imageBytes,
                    contentType = contentType,
                    capturedAt = capturedAt,
                    householdId = householdId,
                    allowRefreshRetry = false,
                    requiredSession = requestSession?.expectation(),
                )
                RefreshAttempt.SESSION_CHANGED -> throw SessionChangedException()
                RefreshAttempt.TRANSIENT_FAILURE -> throw IOException(
                    "Session refresh is temporarily unavailable",
                )
                RefreshAttempt.NOT_AVAILABLE,
                RefreshAttempt.REJECTED,
                -> clearSessionIfMatches(requestSession)
            }
        }
        if (code !in setOf(HttpURLConnection.HTTP_OK)) {
            throw ApiException(parseError(text, code), code)
        }
        ensureSessionStillCurrent(requestSession)
        return parseScreenshotOcrResponse(JSONObject(text))
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
            expectedCodes = setOf(HttpURLConnection.HTTP_OK, HttpURLConnection.HTTP_NOT_FOUND),
        ).takeUnless { it.length() == 0 || it.optJSONObject("error") != null }
            ?.planningPlanObjectOrNull()
            ?.let(::parsePlanningPlan)
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

    override suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> =
        syncPushRequest(request, requiredSession = null)

    internal suspend fun syncPushWithLease(
        request: SyncPushRequest,
        lease: AuthenticatedSessionLease,
    ): ApiResult<SyncPushResponse> = syncPushRequest(request, lease.expectation())

    private suspend fun syncPushRequest(
        request: SyncPushRequest,
        requiredSession: SessionExpectation?,
    ): ApiResult<SyncPushResponse> = safeCall {
        this.request(
            path = "/api/v1/sync/push",
            method = "POST",
            body = request.toJsonForApi().toString(),
            requiredSession = requiredSession,
        ).let(::parseSyncPushResponse)
    }

    override suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> =
        syncPullRequest(request, requiredSession = null)

    internal suspend fun syncPullWithLease(
        request: SyncPullRequest,
        lease: AuthenticatedSessionLease,
    ): ApiResult<SyncPullResponse> = syncPullRequest(request, lease.expectation())

    private suspend fun syncPullRequest(
        request: SyncPullRequest,
        requiredSession: SessionExpectation?,
    ): ApiResult<SyncPullResponse> = safeCall {
        this.request(
            path = "/api/v1/sync/pull",
            method = "POST",
            body = request.toJsonForApi().toString(),
            requiredSession = requiredSession,
        ).let(::parseSyncPullResponse)
    }

    internal suspend fun captureAuthenticatedSessionLease(
        expectedUserId: String,
    ): ApiResult<AuthenticatedSessionLease> = AndroidSessionRefreshCoordinator.mutex.withLock {
        val current = tokenStore.readSession()
        if (
            current == null ||
            current.authenticatedUserId != expectedUserId ||
            current.sessionIdentity.isNullOrBlank()
        ) {
            ApiResult.Failure(
                "Сессия синхронизации изменилась.",
                SessionChangedException(),
                kind = ApiFailureKind.SESSION_CHANGED,
            )
        } else {
            ApiResult.Success(current.authenticatedLease())
        }
    }

    internal suspend fun <T> withAuthenticatedSessionLease(
        lease: AuthenticatedSessionLease,
        block: suspend () -> T,
    ): ApiResult<T> = AndroidSessionRefreshCoordinator.mutex.withLock {
        if (tokenStore.readSession()?.expectation() != lease.expectation()) {
            ApiResult.Failure(
                "Сессия синхронизации изменилась.",
                SessionChangedException(),
                kind = ApiFailureKind.SESSION_CHANGED,
            )
        } else {
            ApiResult.Success(block())
        }
    }

    override suspend fun logout(): ApiResult<Unit> {
        val logoutSession = AndroidSessionRefreshCoordinator.mutex.withLock {
            tokenStore.readSession()
        }
        val remoteResult = safeCall {
            request(
                path = "/api/v1/sessions/current",
                method = "DELETE",
                expectedCodes = setOf(HttpURLConnection.HTTP_NO_CONTENT),
                requiredSession = logoutSession?.expectation(),
            )
            Unit
        }
        return try {
            if (clearSessionIfExpectationMatches(logoutSession?.expectation())) {
                remoteResult
            } else {
                ApiResult.Failure(
                    "Сессия уже изменилась; новая авторизация сохранена.",
                    SessionChangedException(),
                    kind = ApiFailureKind.SESSION_CHANGED,
                )
            }
        } catch (error: Exception) {
            ApiResult.Failure(
                "Не удалось очистить локальную сессию: ${error.message ?: error::class.java.simpleName}",
                error,
                kind = ApiFailureKind.UNKNOWN,
            )
        }
    }

    private inline fun <T> safeCall(block: () -> T): ApiResult<T> {
        return try {
            ApiResult.Success(block())
        } catch (error: CancellationException) {
            throw error
        } catch (error: SessionChangedException) {
            ApiResult.Failure(
                error.message ?: "Сессия изменилась. Повторите действие.",
                error,
                kind = ApiFailureKind.SESSION_CHANGED,
            )
        } catch (error: ApiException) {
            ApiResult.Failure(error.message ?: "Ошибка API", error, error.statusCode, ApiFailureKind.HTTP)
        } catch (error: IOException) {
            ApiResult.Failure(
                "Не удалось подключиться к API: ${error.message ?: error::class.java.simpleName}",
                error,
                kind = ApiFailureKind.NETWORK,
            )
        } catch (error: JSONException) {
            ApiResult.Failure(
                "API response did not match expected contract: ${error.message ?: error::class.java.simpleName}",
                error,
                kind = ApiFailureKind.CONTRACT,
            )
        } catch (error: IllegalArgumentException) {
            ApiResult.Failure(
                "API response did not match expected contract: ${error.message ?: error::class.java.simpleName}",
                error,
                kind = ApiFailureKind.CONTRACT,
            )
        } catch (error: IllegalStateException) {
            ApiResult.Failure(
                "API response did not match expected contract: ${error.message ?: error::class.java.simpleName}",
                error,
                kind = ApiFailureKind.CONTRACT,
            )
        } catch (error: Exception) {
            ApiResult.Failure(
                "API request failed: ${error.message ?: error::class.java.simpleName}",
                error,
                kind = ApiFailureKind.UNKNOWN,
            )
        }
    }

    private suspend fun request(
        path: String,
        method: String,
        query: Map<String, String> = emptyMap(),
        body: String? = null,
        authorize: Boolean = true,
        expectedCodes: Set<Int> = setOf(HttpURLConnection.HTTP_OK),
        allowRefreshRetry: Boolean = true,
        requiredSession: SessionExpectation? = null,
    ): JSONObject {
        val queryString = query.entries.joinToString("&") {
            "${it.key.urlEncode()}=${it.value.urlEncode()}"
        }.takeIf { it.isNotBlank() }?.let { "?$it" } ?: ""
        val connection = (URL("${config.normalizedBaseUrl}$path$queryString").openConnection() as HttpURLConnection)
        connection.requestMethod = method
        connection.connectTimeout = 5_000
        connection.readTimeout = 5_000
        connection.setRequestProperty("Accept", "application/json")
        val requestSession = if (authorize) authorizedSession(requiredSession) else null
        requestSession?.accessToken?.let {
            connection.setRequestProperty("Authorization", "Bearer $it")
        }
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        }

        val code = connection.responseCode
        val text = connection.readText(code)
        if (code !in expectedCodes) {
            if (authorize && code == HttpURLConnection.HTTP_UNAUTHORIZED) {
                when (
                    if (allowRefreshRetry) refreshAccessToken(requestSession)
                    else RefreshAttempt.REJECTED
                ) {
                    RefreshAttempt.SUCCEEDED -> return request(
                        path = path,
                        method = method,
                        query = query,
                        body = body,
                        authorize = true,
                        expectedCodes = expectedCodes,
                        allowRefreshRetry = false,
                        requiredSession = requestSession?.expectation(),
                    )
                    RefreshAttempt.SESSION_CHANGED -> throw SessionChangedException()
                    RefreshAttempt.TRANSIENT_FAILURE -> throw IOException(
                        "Session refresh is temporarily unavailable",
                    )
                    RefreshAttempt.NOT_AVAILABLE,
                    RefreshAttempt.REJECTED,
                    -> clearSessionIfMatches(requestSession)
                }
            }
            throw ApiException(parseError(text, code), code)
        }
        if (authorize) {
            ensureSessionStillCurrent(requestSession)
        }
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private suspend fun refreshAccessToken(failedSession: StoredSessionTokens?): RefreshAttempt =
        AndroidSessionRefreshCoordinator.mutex.withLock {
            val currentSession = tokenStore.readSession()
            if (failedSession == null) {
                return@withLock if (currentSession == null) {
                    RefreshAttempt.NOT_AVAILABLE
                } else {
                    RefreshAttempt.SESSION_CHANGED
                }
            }
            if (currentSession == null || !currentSession.hasSameIdentity(failedSession)) {
                return@withLock RefreshAttempt.SESSION_CHANGED
            }
            if (currentSession.accessToken != failedSession.accessToken) {
                return@withLock RefreshAttempt.SUCCEEDED
            }
            val refreshToken = currentSession.refreshToken ?: return@withLock RefreshAttempt.NOT_AVAILABLE
            return@withLock try {
                val response = request(
                    path = "/api/v1/sessions/refresh",
                    method = "POST",
                    body = JSONObject().put("refreshToken", refreshToken).toString(),
                    authorize = false,
                    expectedCodes = setOf(HttpURLConnection.HTTP_OK),
                    allowRefreshRetry = false,
                )
                val tokens = bearerSessionTokens(response)
                if (
                    tokens.sessionIdentity != currentSession.sessionIdentity ||
                    tokens.authenticatedUserId != currentSession.authenticatedUserId
                ) {
                    throw JSONException("Refreshed bearer session identity changed")
                }
                if (
                    tokenStore.rotateSessionTokens(
                        expectedGeneration = currentSession.generation,
                        expectedIdentity = currentSession.sessionIdentity,
                        accessToken = tokens.accessToken,
                        refreshToken = tokens.refreshToken,
                    )
                ) {
                    RefreshAttempt.SUCCEEDED
                } else {
                    RefreshAttempt.SESSION_CHANGED
                }
            } catch (error: ApiException) {
                if (error.statusCode == HttpURLConnection.HTTP_UNAUTHORIZED) {
                    val latestSession = tokenStore.readSession()
                    if (latestSession == currentSession) {
                        tokenStore.clear()
                    }
                    RefreshAttempt.REJECTED
                } else {
                    RefreshAttempt.TRANSIENT_FAILURE
                }
            } catch (_: IOException) {
                RefreshAttempt.TRANSIENT_FAILURE
            }
        }

    private enum class RefreshAttempt {
        SUCCEEDED,
        NOT_AVAILABLE,
        REJECTED,
        TRANSIENT_FAILURE,
        SESSION_CHANGED,
    }

    private suspend fun persistBearerSession(response: JSONObject) {
        val tokens = bearerSessionTokens(response)
        AndroidSessionRefreshCoordinator.mutex.withLock {
            tokenStore.saveSessionTokens(
                accessToken = tokens.accessToken,
                refreshToken = tokens.refreshToken,
                sessionIdentity = tokens.sessionIdentity,
                authenticatedUserId = tokens.authenticatedUserId,
            )
        }
    }

    private fun bearerSessionTokens(response: JSONObject): BearerSessionTokens {
        val accessToken = response.optString("accessToken").takeIf { it.isNotBlank() }
            ?: throw JSONException("Bearer session response is missing accessToken")
        val refreshToken = response.optString("refreshToken").takeIf { it.isNotBlank() }
            ?: throw JSONException("Bearer session response is missing refreshToken")
        val actor = response.optJSONObject("actor")
            ?: throw JSONException("Bearer session response is missing actor")
        val authenticatedUserId = actor.optString("userId").takeIf { it.isNotBlank() }
            ?: throw JSONException("Bearer session response is missing authenticated user ID")
        val sessionIdentity = actor.optString("sessionId").takeIf { it.isNotBlank() }
            ?: authenticatedUserId
        return BearerSessionTokens(accessToken, refreshToken, sessionIdentity, authenticatedUserId)
    }

    private suspend fun clearSession() {
        AndroidSessionRefreshCoordinator.mutex.withLock {
            tokenStore.clear()
        }
    }

    private suspend fun clearSessionIfMatches(expectedSession: StoredSessionTokens?): Boolean =
        AndroidSessionRefreshCoordinator.mutex.withLock {
            if (tokenStore.readSession() == expectedSession) {
                tokenStore.clear()
                true
            } else {
                false
            }
        }

    private suspend fun clearSessionIfExpectationMatches(expectedSession: SessionExpectation?): Boolean =
        AndroidSessionRefreshCoordinator.mutex.withLock {
            if (tokenStore.readSession()?.expectation() == expectedSession) {
                tokenStore.clear()
                true
            } else {
                false
            }
        }

    private suspend fun currentSessionStatus(): SessionStatus {
        val expectedSession = tokenStore.readSession()
        val response = request(
            path = "/api/v1/sessions/current",
            method = "GET",
            requiredSession = expectedSession?.expectation(),
        )
        val status = parseSession(response)
        bindLegacyForegroundSession(expectedSession, status)
        return status
    }

    private suspend fun bindLegacyForegroundSession(
        expectedSession: StoredSessionTokens?,
        status: SessionStatus,
    ) {
        val legacySession = expectedSession?.takeIf { it.authenticatedUserId == null } ?: return
        val userId = status.userId ?: return
        val sessionIdentity = status.sessionId ?: userId
        AndroidSessionRefreshCoordinator.mutex.withLock {
            tokenStore.bindAuthenticatedUser(
                expectedGeneration = legacySession.generation,
                expectedIdentity = legacySession.sessionIdentity,
                sessionIdentity = sessionIdentity,
                authenticatedUserId = userId,
            )
        }
    }

    private suspend fun authorizedSession(requiredSession: SessionExpectation?): StoredSessionTokens? {
        val session = tokenStore.readSession()
        if (requiredSession != null && session?.expectation() != requiredSession) {
            throw SessionChangedException()
        }
        return session
    }

    private suspend fun ensureSessionStillCurrent(requestSession: StoredSessionTokens?) {
        if (requestSession != null && tokenStore.readSession()?.expectation() != requestSession.expectation()) {
            throw SessionChangedException()
        }
    }

    private suspend fun requestAllPages(
        path: String,
        query: Map<String, String> = emptyMap(),
    ): List<JSONObject> {
        val itemsById = linkedMapOf<String, JSONObject>()
        val seenCursors = mutableSetOf<String>()
        var cursor: String? = null
        var anonymousIndex = 0

        while (true) {
            val pageQuery = query + mapOf("limit" to "100") +
                (cursor?.let { mapOf("cursor" to it) } ?: emptyMap())
            val response = request(path = path, method = "GET", query = pageQuery)
            val envelope = response.optJSONObject("data") ?: response
            envelope.items().forEach { item ->
                val id = item.optString("id").takeIf { it.isNotBlank() }
                    ?: "__anonymous_${anonymousIndex++}"
                itemsById.putIfAbsent(id, item)
            }

            val page = envelope.optJSONObject("page") ?: response.optJSONObject("page")
            if (page?.optBoolean("hasMore", false) != true) break
            val nextCursor = page.optNullableString("nextCursor")
            if (nextCursor == null || !seenCursors.add(nextCursor)) {
                throw ApiException("Invalid pagination cursor for $path")
            }
            cursor = nextCursor
        }

        return itemsById.values.toList()
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

private object AndroidSessionRefreshCoordinator {
    val mutex = Mutex()
}

private data class BearerSessionTokens(
    val accessToken: String,
    val refreshToken: String,
    val sessionIdentity: String,
    val authenticatedUserId: String,
)

private data class SessionExpectation(
    val generation: Long,
    val sessionIdentity: String?,
    val authenticatedUserId: String?,
)

private fun StoredSessionTokens.expectation(): SessionExpectation =
    SessionExpectation(generation, sessionIdentity, authenticatedUserId)

private fun AuthenticatedSessionLease.expectation(): SessionExpectation =
    SessionExpectation(generation, sessionIdentity, authenticatedUserId)

private fun StoredSessionTokens.authenticatedLease(): AuthenticatedSessionLease =
    AuthenticatedSessionLease(
        generation = generation,
        sessionIdentity = requireNotNull(sessionIdentity),
        authenticatedUserId = requireNotNull(authenticatedUserId),
    )

private fun StoredSessionTokens.hasSameIdentity(other: StoredSessionTokens): Boolean =
    expectation() == other.expectation()

private class SessionChangedException : Exception("Сессия изменилась. Повторите действие.")

class ApiException(
    message: String,
    val statusCode: Int? = null,
) : Exception(message)

private fun parseSession(json: JSONObject): SessionStatus {
    val actor = json.optJSONObject("actor")
        ?: json.optJSONObject("data")?.optJSONObject("actor")
        ?: json.optJSONObject("data")?.optJSONObject("user")
        ?: json.optJSONObject("user")
    val userId = actor?.optString("userId")?.takeIf { it.isNotBlank() }
        ?: actor?.optString("id")?.takeIf { it.isNotBlank() }
    val sessionId = actor?.optString("sessionId")?.takeIf { it.isNotBlank() }
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
        userId = userId,
        sessionId = sessionId,
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
        isPaymentAccount = json.optBoolean("isPaymentAccount", true),
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
        iconKey = json.optString("iconKey", ""),
        recordStatus = json.optString("recordStatus", json.optString("status", "active")),
        version = json.optIntOrNull("version"),
    )
}

private fun parseInvestmentMigrationResult(json: JSONObject): InvestmentMigrationResult {
    return InvestmentMigrationResult(
        assetCategory = parseAssetCategory(json.getJSONObject("assetCategory")),
        accounts = json.optJSONArray("accounts")?.toObjectList()?.map(::parseAccount).orEmpty(),
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
    val accountCount = when {
        json.has("accountCount") -> json.optInt("accountCount")
        json.has("accounts") -> json.optJSONArray("accounts")?.length()
        else -> null
    }
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
        iconKey = json.optString("iconKey", category?.optString("iconKey", "") ?: ""),
        accountCount = accountCount,
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
    val occurredAt = json.optString("occurredAt").ifBlank {
        json.optString("transactionDate").takeIf { it.isNotBlank() }?.let { "${it}T00:00:00Z" }.orEmpty()
    }
    return TransactionSummary(
        type = json.optString("transactionType"),
        amount = json.optString("amount"),
        currency = json.optString("currency"),
        occurredAt = occurredAt,
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
        transactionDate = json.optString("transactionDate").ifBlank { occurredAt.take(10) },
        createdAt = json.optString("createdAt").ifBlank { occurredAt },
    )
}

private val transactionNewestFirstComparator =
    compareByDescending<TransactionSummary> { it.transactionDate }
        .thenByDescending { it.occurredAt }
        .thenByDescending { it.createdAt }
        .thenByDescending { it.id }

private fun monthlyInvestmentTransfers(
    transactions: List<TransactionSummary>,
    accounts: List<AccountSummary>,
    assetCategories: List<AssetCategory>,
): List<MoneyAmount> {
    val accountsById = accounts.associateBy { it.id }
    val investmentCategoryIds = assetCategories
        .filter { it.recordStatus == "active" && it.isInvestment }
        .mapTo(mutableSetOf()) { it.id }
    return transactions
        .asSequence()
        .filter { it.type == "transfer" && it.counterpartyAccountId != null }
        .mapNotNull { transaction ->
            val destination = accountsById[transaction.counterpartyAccountId] ?: return@mapNotNull null
            val isInvestmentDestination = destination.assetCategoryId in investmentCategoryIds ||
                destination.type.lowercase(Locale.US) in setOf("brokerage", "investment")
            transaction.takeIf { isInvestmentDestination }
        }
        .groupBy { it.currency }
        .map { (currency, items) ->
            MoneyAmount(
                currency = currency,
                amount = items.fold(BigDecimal.ZERO) { total, item -> total + item.amount.toBigDecimal() }
                    .toPlainString(),
            )
        }
        .sortedBy { it.currency }
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
    val occurredDate = json.optString("occurredDate").ifBlank {
        json.optString("occurredAt").take(10)
    }
    val occurredAt = json.optString("occurredAt").ifBlank {
        occurredDate.takeIf { it.isNotBlank() }?.let { "${it}T00:00:00Z" }.orEmpty()
    }
    return CaptureDraft(
        id = json.optString("id").ifBlank { json.optString("draftId") },
        status = json.optString("status", "pending"),
        amount = json.optString("amount"),
        currency = json.optString("currency"),
        description = json.optString("description").takeIf { it.isNotBlank() && it != "null" },
        merchantName = json.optString("merchantName").takeIf { it.isNotBlank() && it != "null" },
        capturedAt = json.optString("capturedAt").takeIf { it.isNotBlank() && it != "null" },
        occurredAt = occurredAt,
        occurredDate = occurredDate,
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

private fun JSONObject.investmentTotalsByCurrency(): List<MoneyAmount> {
    return optJSONArray("totalsByCurrency")
        ?.toObjectList()
        ?.filter { item ->
            item.has("investmentsTotal") || item.has("investmentTotal") || item.has("investmentsAmount")
        }
        ?.map { item ->
            MoneyAmount(
                currency = item.optString("currency", "USD"),
                amount = item.optString(
                    "investmentsTotal",
                    item.optString("investmentTotal", item.optString("investmentsAmount", "0")),
                ),
            )
        }
        ?: emptyList()
}

private fun parseSyncPushResponse(json: JSONObject): SyncPushResponse {
    val data = json.optJSONObject("data") ?: json
    return SyncPushResponse(
        deviceId = data.optString("deviceId"),
        serverTime = data.optString("serverTime"),
        results = data.optJSONArray("results")?.toObjectList()?.map(::parseSyncMutationResult).orEmpty(),
    )
}

private fun parseSyncMutationResult(json: JSONObject): SyncMutationResult {
    return SyncMutationResult(
        clientMutationId = json.optString("clientMutationId"),
        entityType = json.optString("entityType"),
        entityId = json.optString("entityId"),
        operation = json.optString("operation"),
        status = json.optString("status"),
        serverVersion = json.optIntOrNull("serverVersion"),
        changeSeq = json.optLongOrNull("changeSeq"),
        errorCode = json.optNullableString("errorCode"),
        message = json.optNullableString("message"),
        data = json.optJSONObject("data"),
    )
}

private fun parseSyncPullResponse(json: JSONObject): SyncPullResponse {
    val data = json.optJSONObject("data") ?: json
    return SyncPullResponse(
        changes = data.optJSONArray("changes")?.toObjectList()?.map(::parseSyncChange).orEmpty(),
        nextCursor = data.optLong("nextCursor", 0),
        hasMore = data.optBoolean("hasMore", false),
        serverTime = data.optString("serverTime"),
    )
}

private fun parseSyncChange(json: JSONObject): SyncChange {
    return SyncChange(
        seq = json.optLong("seq"),
        entityType = json.optString("entityType"),
        entityId = json.optString("entityId"),
        changeType = json.optString("changeType"),
        entityVersion = json.optIntOrNull("entityVersion"),
        entityUpdatedAt = json.optNullableString("entityUpdatedAt"),
        changedByUserId = json.optNullableString("changedByUserId"),
        clientMutationId = json.optNullableString("clientMutationId"),
        payload = json.optJSONObject("payload"),
        tombstonePayload = json.optJSONObject("tombstonePayload"),
        createdAt = json.optString("createdAt"),
    )
}

private fun CaptureDraftCreateRequest.toJson(): JSONObject {
    return JSONObject()
        .put("amount", amount)
        .put("currency", currency)
        .put("description", description)
        .put("merchantName", merchantName)
        .put("capturedAt", capturedAt)
        .put("occurredDate", occurredDate)
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

internal fun InvestmentMigrationCreateRequest.toJsonForApi(): JSONObject {
    return JSONObject()
        .put("assetCategoryId", assetCategoryId)
        .put("name", name.trim().take(120))
        .apply {
            iconKey?.takeIf { it.isNotBlank() }?.let { put("icon", it) }
            color?.takeIf { it.isNotBlank() }?.let { put("color", it) }
        }
        .put("assetType", assetType)
        .put("currency", currency)
        .put("scope", if (scope == "household" || scope == "shared") "household" else "personal")
        .apply { householdId?.takeIf { it.isNotBlank() }?.let { put("householdId", it) } }
        .put(
            "accountIds",
            JSONArray().apply {
                accountIds.forEach { put(it) }
            },
        )
        .put(
            "accountVersions",
            JSONObject().apply {
                accountIds.forEach { accountId ->
                    accountVersions[accountId]?.let { put(accountId, it) }
                }
                accountVersions.keys
                    .filterNot { it in accountIds }
                    .sorted()
                    .forEach { accountId -> put(accountId, accountVersions.getValue(accountId)) }
            },
        )
}

internal fun AssetCategory.toUpdateJsonForApi(): JSONObject {
    return JSONObject()
        .put("name", name.take(80))
        .put("manualAmount", manualAmount)
        .put("isInvestment", isInvestment)
        .put("assetType", assetType)
        .apply {
            iconKey.takeIf { it.isNotBlank() }?.let { put("iconKey", it) }
            version?.let { put("version", it) }
        }
}

internal fun SyncPushRequest.toJsonForApi(): JSONObject {
    return JSONObject()
        .put("deviceId", deviceId)
        .put("clientSchemaVersion", clientSchemaVersion)
        .put(
            "mutations",
            JSONArray().apply {
                mutations.forEach { put(it.toJsonForApi()) }
            },
        )
}

internal fun SyncPullRequest.toJsonForApi(): JSONObject {
    return JSONObject()
        .put("deviceId", deviceId)
        .put("clientSchemaVersion", clientSchemaVersion)
        .put("cursor", cursor)
        .put("limit", limit)
        .apply {
            entityTypes?.let { types ->
                put(
                    "entityTypes",
                    JSONArray().apply {
                        types.forEach { put(it) }
                    },
                )
            }
        }
}

internal fun SyncMutationRequest.toJsonForApi(): JSONObject {
    return JSONObject()
        .put("clientMutationId", clientMutationId)
        .put("entityType", entityType)
        .put("entityId", entityId)
        .put("operation", operation)
        .apply {
            baseVersion?.let { put("baseVersion", it) }
            payload?.let { put("payload", it) }
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
        occurredDate?.let { put("occurredDate", it) }
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

private fun JSONObject.optLongOrNull(name: String): Long? = if (has(name) && !isNull(name)) optLong(name) else null

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

private fun reportDateQuery(startDate: String?, endDate: String?): Map<String, String> {
    return listOfNotNull(
        startDate?.takeIf { it.isNotBlank() }?.let { "startDate" to it },
        endDate?.takeIf { it.isNotBlank() }?.let { "endDate" to it },
    ).toMap()
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

private fun todayDate(): String = java.time.LocalDate.now().toString()
