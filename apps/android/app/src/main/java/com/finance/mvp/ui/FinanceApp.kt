package com.finance.mvp.ui

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.annotation.DrawableRes
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.PlainTooltip
import androidx.compose.material3.TooltipBox
import androidx.compose.material3.TooltipDefaults
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.rememberTooltipState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.PointerInputScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.password
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.finance.mvp.BuildConfig
import com.finance.mvp.R
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiFailureKind
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.AssetCategory
import com.finance.mvp.api.AssetCategoryCreateRequest
import com.finance.mvp.api.AssetCategoryGroup
import com.finance.mvp.api.CaptureDraft
import com.finance.mvp.api.CaptureDraftUpdateRequest
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.InvestmentMigrationCreateRequest
import com.finance.mvp.api.MoneyAmount
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.RegistrationResult
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import com.finance.mvp.api.userFacingSeedText
import com.finance.mvp.capture.AndroidCategoryAggregateMappingStore
import com.finance.mvp.capture.CategoryAggregateCandidate
import com.finance.mvp.local.FinanceLocalDatabase
import com.finance.mvp.notifications.PlanningReminderNotifications
import com.finance.mvp.sync.PlanningRepository
import com.finance.mvp.sync.SyncIssueSummary
import com.finance.mvp.sync.SyncManager
import com.finance.mvp.sync.TransactionSyncWorker
import com.finance.mvp.ui.theme.FinanceTheme
import java.math.BigDecimal
import java.math.RoundingMode
import java.text.NumberFormat
import java.time.Instant
import java.time.LocalDate
import java.time.YearMonth
import java.time.ZoneOffset
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

private val AddAccountStateSaver = Saver<AddAccountState?, List<String>>(
    save = { state ->
        state?.let {
            listOf(it.kind.name, it.mode.name, it.assetCategoryId.orEmpty())
        }
    },
    restore = { saved ->
        val kind = runCatching { AssetKind.valueOf(saved.getOrNull(0).orEmpty()) }.getOrNull()
        val mode = runCatching { FinanceMode.valueOf(saved.getOrNull(1).orEmpty()) }.getOrNull()
        if (kind == null || mode == null) {
            null
        } else {
            AddAccountState(kind, mode, saved.getOrNull(2)?.takeIf { it.isNotBlank() })
        }
    },
)

private const val ASSET_CATEGORY_ORDER_PREFS = "finance_asset_category_order"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinanceApp(
    apiClient: FinanceApiClient,
    modifier: Modifier = Modifier,
    syncManager: SyncManager? = null,
    initialOpenPlanning: Boolean = false,
    openPlanningRequestKey: Int = if (initialOpenPlanning) 1 else 0,
) {
    val context = LocalContext.current
    val categoryAggregateMappingStore = remember(context) { AndroidCategoryAggregateMappingStore(context) }
    val planningRepository = remember(context, apiClient, syncManager) {
        syncManager?.let { manager ->
            PlanningRepository(
                database = FinanceLocalDatabase.getInstance(context),
                apiClient = apiClient,
                syncManager = manager,
            )
        }
    }
    var selectedSection by rememberSaveable {
        mutableStateOf(if (initialOpenPlanning) AppSection.Analytics else AppSection.Home)
    }
    val selectedMode = FinanceMode.Personal
    var selectedAnalyticsSubsection by rememberSaveable {
        mutableStateOf(if (initialOpenPlanning) AnalyticsSubsection.Planning else AnalyticsSubsection.Summary)
    }
    var selectedReportMonth by rememberSaveable { mutableStateOf(currentReportMonth()) }
    var showQuickAdd by rememberSaveable { mutableStateOf(false) }
    var quickAddOpenKey by rememberSaveable { mutableStateOf(0) }
    var quickAddError by rememberSaveable { mutableStateOf<String?>(null) }
    var authMode by rememberSaveable { mutableStateOf(AuthMode.Login) }
    var loginEmail by rememberSaveable { mutableStateOf("") }
    var loginPassword by remember { mutableStateOf("") }
    var registerConfirmPassword by remember { mutableStateOf("") }
    var registerDisplayName by rememberSaveable { mutableStateOf("") }
    var uiState by remember { mutableStateOf(FinanceUiState()) }
    var captureDrafts by remember { mutableStateOf<List<CaptureDraft>>(emptyList()) }
    var captureIsLoading by rememberSaveable { mutableStateOf(false) }
    var captureMessage by rememberSaveable { mutableStateOf<String?>(null) }
    var screenshotOcrStatus by rememberSaveable { mutableStateOf<String?>(null) }
    var screenshotAggregateDrafts by remember { mutableStateOf<List<ScreenshotAggregateDraftUi>>(emptyList()) }
    var assetGroupNames by rememberSaveable { mutableStateOf<Map<String, String>>(emptyMap()) }
    var addAccountState by rememberSaveable(stateSaver = AddAccountStateSaver) { mutableStateOf<AddAccountState?>(null) }
    var showAssetCategorySheet by rememberSaveable { mutableStateOf(false) }
    var syncUiState by remember { mutableStateOf(SyncUiState()) }
    var syncIssues by remember { mutableStateOf<List<SyncIssueSummary>>(emptyList()) }
    var showSyncIssuesSheet by rememberSaveable { mutableStateOf(false) }
    var syncIssuesLoading by rememberSaveable { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val sections = financeSections()

    LaunchedEffect(openPlanningRequestKey) {
        if (openPlanningRequestKey > 0) {
            selectedSection = AppSection.Analytics
            selectedAnalyticsSubsection = AnalyticsSubsection.Planning
        }
    }

    fun processScreenshotCapture(uri: Uri) {
        scope.launch {
            captureIsLoading = true
            screenshotOcrStatus = "Отправляем скриншот в backend OCR. Операции не создаются автоматически."
            screenshotAggregateDrafts = emptyList()
            val capturedAtMillis = System.currentTimeMillis()
            val capturedAt = java.time.Instant.ofEpochMilli(capturedAtMillis).toString()
            val ocrResult = withContext(Dispatchers.IO) {
                runCatching {
                    val inputStream = context.contentResolver.openInputStream(uri)
                        ?: throw IllegalStateException("Не удалось открыть изображение")
                    val imageBytes = inputStream.use { it.readBytes() }
                    val contentType = context.contentResolver.getType(uri) ?: "image/jpeg"
                    apiClient.screenshotOcr(
                        imageBytes = imageBytes,
                        contentType = contentType,
                        capturedAt = capturedAt,
                        householdId = null,
                    )
                }
            }
            val result = ocrResult.getOrNull()
            if (ocrResult.isFailure || result == null) {
                val errorMsg = (result as? ApiResult.Failure)?.message
                    ?: ocrResult.exceptionOrNull()?.message
                    ?: "Неизвестная ошибка"
                screenshotOcrStatus = "Backend OCR не вернул кандидатов для проверки"
                captureMessage = "$errorMsg. Выберите другой скриншот или добавьте расход вручную."
                captureIsLoading = false
                return@launch
            }

            when (result) {
                is ApiResult.Success -> {
                    val items = result.value.items
                    if (items.isEmpty()) {
                        screenshotOcrStatus = "Backend OCR не нашёл расходов на скриншоте"
                        captureMessage = "Выберите другой скриншот или добавьте расход вручную."
                        captureIsLoading = false
                        return@launch
                    }

                    val activeExpenseCategoryIds = uiState.dashboard
                        ?.categories
                        .orEmpty()
                        .filter { it.status == "active" && it.type == "expense" && it.id.isNotBlank() }
                        .map { it.id }
                        .toSet()
                    val mappingContext = aggregateMappingContext(uiState.session)
                    val drafts = items.map { serverCandidate ->
                        val candidate = CategoryAggregateCandidate(
                            externalLabel = serverCandidate.externalLabel,
                            amount = serverCandidate.amount,
                            currency = serverCandidate.currency,
                            operationCount = serverCandidate.operationCount,
                            capturedAt = capturedAt,
                            occurredAt = capturedAt,
                            idempotencyKey = serverCandidate.idempotencyKey,
                            confidence = serverCandidate.confidence,
                            evidenceHash = serverCandidate.evidenceHash,
                        )
                        val mappedCategoryId = withContext(Dispatchers.IO) {
                            categoryAggregateMappingStore.readCategoryId(mappingContext, candidate.externalLabel)
                        }?.takeIf { it in activeExpenseCategoryIds }
                        ScreenshotAggregateDraftUi(
                            candidate = candidate,
                            selectedCategoryId = mappedCategoryId.orEmpty(),
                            include = mappedCategoryId != null,
                        )
                    }
                    screenshotAggregateDrafts = drafts
                    screenshotOcrStatus = "Backend OCR сформировал ${drafts.size} кандидатов. Проверьте их перед созданием черновиков."
                    captureMessage = "Выберите категории и создайте черновики для ручной проверки."
                    captureIsLoading = false
                }
                is ApiResult.Failure -> {
                    screenshotOcrStatus = "Backend OCR не вернул черновики для проверки"
                    captureMessage = result.userFacingMessage()
                    captureIsLoading = false
                }
            }
        }
    }

    fun updateScreenshotAggregateCategory(candidateKey: String, categoryId: String) {
        screenshotAggregateDrafts = screenshotAggregateDrafts.map { draft ->
            if (draft.key == candidateKey) {
                draft.copy(selectedCategoryId = categoryId, include = categoryId.isNotBlank())
            } else {
                draft
            }
        }
    }

    fun updateScreenshotAggregateIncluded(candidateKey: String, include: Boolean) {
        screenshotAggregateDrafts = screenshotAggregateDrafts.map { draft ->
            if (draft.key == candidateKey) {
                draft.copy(include = include)
            } else {
                draft
            }
        }
    }

    fun createScreenshotAggregateDrafts() {
        val selectedDrafts = screenshotAggregateDrafts
            .filter { it.include && it.selectedCategoryId.isNotBlank() }
        if (selectedDrafts.isEmpty()) {
            captureMessage = "Выберите хотя бы одну категорию, чтобы создать черновик для проверки."
            return
        }
        scope.launch {
            captureIsLoading = true
            screenshotOcrStatus = "Создаём ${selectedDrafts.size} черновиков для проверки"
            val mappingContext = aggregateMappingContext(uiState.session)
            val result = withContext(Dispatchers.IO) {
                var failure: ApiResult.Failure? = null
                for (draft in selectedDrafts) {
                    when (
                        val createResult = apiClient.createCaptureDraft(
                            draft.candidate.toCreateRequest(draft.selectedCategoryId),
                        )
                    ) {
                        is ApiResult.Success -> categoryAggregateMappingStore.saveCategoryId(
                            userContext = mappingContext,
                            externalLabel = draft.candidate.externalLabel,
                            categoryId = draft.selectedCategoryId,
                        )
                        is ApiResult.Failure -> {
                            failure = createResult
                            break
                        }
                    }
                }
                failure ?: ApiResult.Success(Unit)
            }
            when (result) {
                is ApiResult.Success -> {
                    val refreshResult = withContext(Dispatchers.IO) {
                        apiClient.listCaptureDrafts(status = "pending")
                    }
                    if (refreshResult is ApiResult.Success) {
                        captureDrafts = refreshResult.value
                    }
                    screenshotAggregateDrafts = emptyList()
                    screenshotOcrStatus = "Черновики для проверки созданы: ${selectedDrafts.size}"
                    captureMessage = "Проверьте каждый черновик и только потом подтвердите операцию."
                    captureIsLoading = false
                }
                is ApiResult.Failure -> {
                    screenshotOcrStatus = "Не удалось создать черновики"
                    captureMessage = result.userFacingMessage()
                    captureIsLoading = false
                }
            }
        }
    }

    val screenshotPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri == null) {
            screenshotOcrStatus = "Выбор скриншота отменён"
            return@rememberLauncherForActivityResult
        }
        processScreenshotCapture(uri)
    }

    fun loadCaptureDrafts(successMessage: String? = null) {
        scope.launch {
            captureIsLoading = true
            val result = withContext(Dispatchers.IO) { apiClient.listCaptureDrafts(status = "pending") }
            when (result) {
                is ApiResult.Success -> {
                    captureDrafts = result.value
                    captureMessage = successMessage ?: "Черновики обновлены"
                }
                is ApiResult.Failure -> {
                    captureMessage = result.userFacingMessage()
                }
            }
            captureIsLoading = false
        }
    }

    suspend fun refreshSyncUiState(userId: String?, savedOffline: Boolean = syncUiState.savedOffline) {
        if (syncManager == null || userId.isNullOrBlank()) {
            syncUiState = SyncUiState()
            syncIssues = emptyList()
            showSyncIssuesSheet = false
            return
        }
        val pendingCount = syncManager.pendingAttentionCount(userId)
        val failedCount = syncManager.failedAttentionCount(userId)
        syncIssues = if (failedCount > 0) {
            syncManager.syncIssuesForUser(userId)
        } else {
            emptyList()
        }
        syncUiState = syncUiState.copy(
            pendingCount = pendingCount,
            failedCount = failedCount,
            savedOffline = savedOffline && pendingCount > 0,
            isSyncing = false,
        )
    }

    suspend fun markSavedOffline(userId: String, message: String) {
        TransactionSyncWorker.enqueue(context, userId)
        refreshSyncUiState(userId, savedOffline = true)
        uiState = uiState.copy(isLoading = false, message = message)
    }

    suspend fun enqueueOfflineCategoryCreateIfRetriable(
        failure: ApiResult.Failure,
        name: String,
        type: String,
        mode: FinanceMode,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueCategoryCreate(
                userId = userId,
                name = name,
                categoryType = type,
                scope = "personal",
                householdId = null,
            )
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем категорию позже.")
        return true
    }

    suspend fun enqueueOfflineCategoryUpdateIfRetriable(
        failure: ApiResult.Failure,
        category: CategorySummary,
        newName: String,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        val version = category.version ?: return false
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueCategoryUpdate(
                userId = userId,
                entityId = category.id,
                baseVersion = version,
                name = newName,
            )
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем категорию позже.")
        return true
    }

    suspend fun enqueueOfflineCategoryArchiveIfRetriable(
        failure: ApiResult.Failure,
        categoryId: String,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        val category = uiState.dashboard?.categories?.firstOrNull { it.id == categoryId }
        val version = category?.version ?: return false
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueCategoryArchive(userId = userId, entityId = categoryId, baseVersion = version)
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем удаление категории позже.")
        return true
    }

    suspend fun enqueueOfflineAccountCreateIfRetriable(
        failure: ApiResult.Failure,
        name: String,
        balance: String,
        currency: String,
        accountType: String,
        mode: FinanceMode,
        assetCategoryId: String?,
        isPaymentAccount: Boolean,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueAccountCreate(
                userId = userId,
                name = name,
                accountType = accountType,
                ownershipType = "personal",
                currency = currency,
                initialBalance = balance,
                householdId = null,
                assetCategoryId = assetCategoryId,
                isPaymentAccount = isPaymentAccount,
            )
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем актив позже.")
        return true
    }

    suspend fun enqueueOfflineAccountArchiveIfRetriable(
        failure: ApiResult.Failure,
        accountId: String,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        val account = uiState.dashboard?.accounts?.firstOrNull { it.id == accountId }
        val version = account?.version ?: return false
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueAccountArchive(userId = userId, entityId = accountId, baseVersion = version)
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем удаление актива позже.")
        return true
    }

    suspend fun enqueueOfflineAssetCategoryCreateIfRetriable(
        failure: ApiResult.Failure,
        request: AssetCategoryCreateRequest,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueAssetCategoryCreate(
                userId = userId,
                name = request.name,
                scopeType = request.scopeType,
                currency = request.currency,
                manualAmount = request.manualAmount,
                isInvestment = request.isInvestment,
                assetType = request.assetType,
                householdId = request.householdId,
                iconKey = request.iconKey,
            )
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем категорию активов позже.")
        return true
    }

    suspend fun enqueueOfflineInvestmentMigrationIfRetriable(
        failure: ApiResult.Failure,
        request: InvestmentMigrationCreateRequest,
        accounts: List<AccountSummary>,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueInvestmentMigrationCreate(
                userId = userId,
                request = request,
                accounts = accounts,
            )
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем инвестиционную миграцию позже.")
        return true
    }

    suspend fun enqueueOfflineAssetCategoryArchiveIfRetriable(
        failure: ApiResult.Failure,
        categoryId: String,
    ): Boolean {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        val category = uiState.dashboard?.assetCategories?.firstOrNull { it.id == categoryId }
        val version = category?.version ?: return false
        if (!failure.isRetriableForOfflineQueue() || userId == null || manager == null) return false
        withContext(Dispatchers.IO) {
            manager.enqueueAssetCategoryArchive(userId = userId, entityId = categoryId, baseVersion = version)
        }
        markSavedOffline(userId, "Сохранено на устройстве. Синхронизируем удаление категории активов позже.")
        return true
    }

    fun loadDashboard(successMessage: String = "Данные обновлены") {
        scope.launch {
            uiState = uiState.copy(isLoading = true, message = "Обновляем данные")
            val monthBoundary = selectedReportMonth.reportMonthBoundary()
            uiState = when (val result = withContext(Dispatchers.IO) {
                apiClient.dashboard(
                    startDate = monthBoundary.startDate,
                    endDate = monthBoundary.endDate,
                )
            }) {
                is ApiResult.Success -> FinanceUiState(
                    session = result.value.session,
                    dashboard = result.value,
                    message = successMessage,
                )
                is ApiResult.Failure -> {
                    if (result.isAuthenticationFailure()) {
                        FinanceUiState(message = "Сессия истекла. Войдите снова.")
                    } else {
                        uiState.copy(
                            isLoading = false,
                            message = result.userFacingMessage(),
                        )
                    }
                }
            }
            refreshSyncUiState(uiState.session?.syncUserIdOrNull())
        }
    }

    fun runManualSync() {
        val userId = uiState.session?.syncUserIdOrNull()
        if (syncManager == null || userId == null) {
            loadDashboard()
            return
        }
        val hadAttention = syncAttention(syncUiState) != null
        scope.launch {
            syncUiState = syncUiState.copy(isSyncing = true)
            uiState = uiState.copy(isLoading = true, message = "Синхронизируем")
            val result = withContext(Dispatchers.IO) {
                runCatching { syncManager.retryFailedIssuesAndSyncNow(userId) }
            }
            val summary = result.getOrNull()
            val syncFailed = result.isFailure ||
                summary?.pullSucceeded == false ||
                summary?.push?.failed.orZero() > 0 ||
                summary?.push?.rejected.orZero() > 0
            refreshSyncUiState(userId, savedOffline = if (syncFailed) syncUiState.savedOffline else false)
            if (syncFailed) {
                if (hadAttention) {
                    uiState = uiState.copy(
                        isLoading = false,
                        message = "Не удалось синхронизировать. Попробуйте позже.",
                    )
                } else {
                    loadDashboard()
                }
            } else {
                loadDashboard("Синхронизировано")
            }
        }
    }

    fun openSyncAttention() {
        val userId = uiState.session?.syncUserIdOrNull()
        val manager = syncManager
        if (manager == null || userId == null || syncUiState.failedCount <= 0) {
            runManualSync()
            return
        }
        showSyncIssuesSheet = true
        scope.launch {
            syncIssuesLoading = true
            syncIssues = runCatching {
                withContext(Dispatchers.IO) { manager.syncIssuesForUser(userId) }
            }.getOrElse { emptyList() }
            syncIssuesLoading = false
        }
    }

    fun confirmCaptureDraft(
        draft: CaptureDraft,
        accountId: String,
        categoryId: String,
        amountInput: String,
        occurredDate: String,
    ) {
        val selectedAccountId = accountId.takeIf { it.isNotBlank() }
        val selectedCategoryId = categoryId.takeIf { it.isNotBlank() }
        if (selectedAccountId == null || selectedCategoryId == null) {
            captureMessage = "Выберите счёт и категорию перед подтверждением"
            return
        }
        val normalizedAmount = amountInput.normalizedAmount()
        if (normalizedAmount == null || !occurredDate.isDateOnly()) {
            captureMessage = "Проверьте сумму и дату операции"
            return
        }
        scope.launch {
            captureIsLoading = true
            val result = withContext(Dispatchers.IO) {
                val shouldUpdateDraft = draft.accountId != selectedAccountId ||
                    draft.categoryId != selectedCategoryId ||
                    draft.amount.normalizedAmount() != normalizedAmount ||
                    draft.occurredDate != occurredDate
                val draftToConfirm = if (shouldUpdateDraft) {
                    when (
                        val updateResult = apiClient.updateCaptureDraft(
                            draft.id,
                            CaptureDraftUpdateRequest(
                                amount = normalizedAmount,
                                occurredDate = occurredDate,
                                accountId = selectedAccountId,
                                categoryId = selectedCategoryId,
                            ),
                        )
                    ) {
                        is ApiResult.Success -> updateResult.value
                        is ApiResult.Failure -> return@withContext updateResult
                    }
                } else {
                    draft
                }
                apiClient.confirmCaptureDraft(draftToConfirm.id)
            }
            when (result) {
                is ApiResult.Success -> {
                    captureMessage = "Черновик подтверждён"
                    loadDashboard("Черновик подтверждён")
                    loadCaptureDrafts()
                }
                is ApiResult.Failure -> {
                    captureMessage = result.userFacingMessage()
                    captureIsLoading = false
                }
            }
        }
    }

    fun discardCaptureDraft(draft: CaptureDraft) {
        scope.launch {
            captureIsLoading = true
            when (val result = withContext(Dispatchers.IO) { apiClient.discardCaptureDraft(draft.id) }) {
                is ApiResult.Success -> loadCaptureDrafts("Черновик отклонён")
                is ApiResult.Failure -> {
                    captureMessage = result.userFacingMessage()
                    captureIsLoading = false
                }
            }
        }
    }

    fun login(email: String, password: String) {
        val credentials = loginCredentialsOrNull(email, password)
        if (credentials == null) {
            uiState = uiState.copy(message = "Введите email и пароль")
            return
        }

        scope.launch {
            uiState = uiState.copy(isLoading = true, message = "Входим")
            val result = withContext(Dispatchers.IO) {
                apiClient.login(credentials.email, credentials.password)
            }
            loginPassword = ""
            when (result) {
                is ApiResult.Success -> loadDashboard()
                is ApiResult.Failure -> uiState = uiState.copy(
                    isLoading = false,
                    message = result.userFacingMessage(),
                )
            }
        }
    }

    fun register(email: String, password: String, confirmPassword: String, displayName: String) {
        when (val validation = registrationCredentialsOrError(email, password, confirmPassword, displayName)) {
            is RegistrationValidationResult.Invalid -> {
                uiState = uiState.copy(message = validation.message)
            }
            is RegistrationValidationResult.Valid -> {
                scope.launch {
                    uiState = uiState.copy(isLoading = true, message = "Регистрируем аккаунт")
                    val result = withContext(Dispatchers.IO) {
                        apiClient.register(
                            validation.credentials.email,
                            validation.credentials.password,
                            validation.credentials.displayName,
                        )
                    }
                    loginPassword = ""
                    registerConfirmPassword = ""
                    when (result) {
                        is ApiResult.Success -> when (result.value) {
                            is RegistrationResult.Authenticated -> loadDashboard()
                            is RegistrationResult.Accepted -> {
                                val update = registrationAcceptedUiUpdate()
                                authMode = update.mode
                                uiState = update.state
                            }
                        }
                        is ApiResult.Failure -> uiState = uiState.copy(
                            isLoading = false,
                            message = result.userFacingMessage(),
                        )
                    }
                }
            }
        }
    }

    fun logout() {
        scope.launch {
            val userId = uiState.session?.syncUserIdOrNull()
            userId?.let { TransactionSyncWorker.cancel(context, it) }
            uiState = uiState.copy(isLoading = true, message = "Выходим")
            val result = withContext(Dispatchers.IO) { apiClient.logout() }
            if (syncManager != null && userId != null) {
                withContext(Dispatchers.IO) { syncManager.clearUserData(userId) }
            }
            syncUiState = SyncUiState()
            syncIssues = emptyList()
            showSyncIssuesSheet = false
            uiState = withContext(Dispatchers.IO) { completedLogoutUiState(result, apiClient) }
        }
    }

    fun submitQuickAdd(draft: QuickAddDraft) {
        val dashboard = uiState.dashboard ?: return
        val amount = draft.amount.normalizedAmount()
        if (amount == null) {
            quickAddError = "Проверьте сумму"
            uiState = uiState.copy(message = "Проверьте сумму")
            return
        }

        scope.launch {
            quickAddError = null
            uiState = uiState.copy(isLoading = true, message = "Сохраняем")
            val result = withContext(Dispatchers.IO) {
                when (draft.type) {
                    QuickEntryType.Expense,
                    QuickEntryType.Income,
                    -> {
                        val account = dashboard.accounts
                            .writableOperationAccountsFor(draft.type, draft.visibility)
                            .firstByIdOrFirst(draft.accountId)
                            ?: return@withContext QuickAddSubmitResult.Failure(
                                failure = ApiResult.Failure("Нет активного личного счёта. Создайте счёт в «Активы» и повторите сохранение."),
                                offlineDraft = null,
                            )
                        val category = dashboard.categories
                            .filter { it.matchesWritableMode(draft.visibility) }
                            .quickAddCategoryFor(
                                categoryId = draft.categoryId,
                                transactionType = draft.type.apiValue,
                            )
                            ?: return@withContext QuickAddSubmitResult.Failure(
                                failure = ApiResult.Failure("Нет категории для ${draft.type.title.lowercase(Locale.getDefault())}. Создайте категорию и повторите сохранение."),
                                offlineDraft = null,
                            )
                        val offlineDraft = ManualTransactionCreate(
                            transactionType = draft.type.apiValue,
                            amount = amount,
                            currency = account.currency,
                            accountId = account.id,
                            categoryId = category.id,
                            counterpartyAccountId = null,
                            transactionDate = draft.transactionDate,
                            note = category.name,
                        )
                        when (
                            val apiResult = apiClient.createDemoTransaction(
                                account = account,
                                category = category,
                                transactionType = draft.type.apiValue,
                                amount = amount,
                                transactionDate = draft.transactionDate,
                            )
                        ) {
                            is ApiResult.Success -> QuickAddSubmitResult.Success
                            is ApiResult.Failure -> QuickAddSubmitResult.Failure(apiResult, offlineDraft)
                        }
                    }
                    QuickEntryType.Transfer -> {
                        val scopedAccounts = dashboard.accounts
                            .filter { it.status == "active" && it.id.isNotBlank() }
                            .filter { it.matchesWritableMode(draft.visibility) }
                        val source = scopedAccounts.firstByIdOrFirst(draft.accountId)
                        val destination = dashboard.accounts
                            .filter { it.matchesWritableMode(draft.visibility) && it.id != source?.id }
                            .firstByIdOrFirst(draft.destinationAccountId)
                        val validationMessage = transferPairValidationMessage(source, destination)
                        if (validationMessage != null) {
                            QuickAddSubmitResult.Failure(ApiResult.Failure(validationMessage), offlineDraft = null)
                        } else {
                            val offlineDraft = ManualTransactionCreate(
                                transactionType = draft.type.apiValue,
                                amount = amount,
                                currency = source!!.currency,
                                accountId = source.id,
                                categoryId = null,
                                counterpartyAccountId = destination!!.id,
                                transactionDate = draft.transactionDate,
                                note = "Между счетами",
                            )
                            when (val apiResult = apiClient.createDemoTransfer(
                                source,
                                destination,
                                amount,
                                draft.transactionDate,
                            )) {
                                is ApiResult.Success -> QuickAddSubmitResult.Success
                                is ApiResult.Failure -> QuickAddSubmitResult.Failure(apiResult, offlineDraft)
                            }
                        }
                    }
                    QuickEntryType.Asset -> {
                        QuickAddSubmitResult.Failure(
                            failure = ApiResult.Failure(
                                "Актив создаётся из раздела «Активы», чтобы выбрать название, валюту и доступ. Быстрое добавление не создаёт демо-счета.",
                            ),
                            offlineDraft = null,
                        )
                    }
                }
            }

            when (result) {
                is QuickAddSubmitResult.Success -> {
                    quickAddError = null
                    showQuickAdd = false
                    quickAddOpenKey += 1
                    loadDashboard("Сохранено")
                }
                is QuickAddSubmitResult.Failure -> {
                    val userId = uiState.session?.syncUserIdOrNull()
                    val offlineDraft = result.offlineDraft
                    if (
                        result.failure.isRetriableForOfflineQueue() &&
                        offlineDraft != null &&
                        syncManager != null &&
                        userId != null
                    ) {
                        withContext(Dispatchers.IO) {
                            syncManager.enqueueManualTransactionCreate(
                                userId = userId,
                                transactionType = offlineDraft.transactionType,
                                amount = offlineDraft.amount,
                                currency = offlineDraft.currency,
                                accountId = offlineDraft.accountId,
                                categoryId = offlineDraft.categoryId,
                                counterpartyAccountId = offlineDraft.counterpartyAccountId,
                                transactionDate = offlineDraft.transactionDate,
                                note = offlineDraft.note,
                            )
                        }
                        TransactionSyncWorker.enqueue(context, userId)
                        refreshSyncUiState(userId, savedOffline = true)
                        quickAddError = null
                        showQuickAdd = false
                        quickAddOpenKey += 1
                        uiState = uiState.copy(
                            isLoading = false,
                            message = "Сохранено на устройстве. Синхронизируем позже.",
                        )
                    } else {
                        val message = result.failure.userFacingMessage()
                        quickAddError = message
                        uiState = uiState.copy(
                            isLoading = false,
                            message = message,
                        )
                    }
                }
            }
        }
    }

    LaunchedEffect(apiClient) {
        uiState = withContext(Dispatchers.IO) { restoredFinanceUiState(apiClient) }
        refreshSyncUiState(uiState.session?.syncUserIdOrNull())
    }

    LaunchedEffect(apiClient, uiState.session?.isAuthenticated) {
        if (uiState.session?.isAuthenticated == true) {
            refreshSyncUiState(uiState.session?.syncUserIdOrNull())
            captureIsLoading = true
            when (val result = withContext(Dispatchers.IO) { apiClient.listCaptureDrafts(status = "pending") }) {
                is ApiResult.Success -> {
                    captureDrafts = result.value
                    captureMessage = "Черновики обновлены"
                }
                is ApiResult.Failure -> {
                    captureMessage = result.userFacingMessage()
                }
            }
            captureIsLoading = false
        }
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Финансы")
                        Text(
                            text = selectedSection.subtitle,
                            style = MaterialTheme.typography.labelSmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                },
                actions = {
                    SyncActionButton(
                        state = syncUiState,
                        enabled = !uiState.isLoading && uiState.session?.isAuthenticated == true,
                        onClick = { runManualSync() },
                    )
                    TextButton(
                        onClick = { logout() },
                        enabled = !uiState.isLoading && uiState.session?.isAuthenticated == true,
                    ) {
                        Text("Выйти")
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                sections.forEach { section ->
                    NavigationBarItem(
                        selected = selectedSection == section,
                        onClick = { selectedSection = section },
                        icon = { Icon(painterResource(section.icon()), contentDescription = section.title) },
                        label = null,
                        alwaysShowLabel = false,
                    )
                }
            }
        },
        floatingActionButton = {
            if (uiState.session?.isAuthenticated == true) {
                FloatingActionButton(
                    modifier = Modifier.testTag("quick-add-fab"),
                    onClick = {
                        quickAddError = null
                        quickAddOpenKey += 1
                        showQuickAdd = true
                    },
                ) {
                    Icon(painterResource(R.drawable.ic_add_24), contentDescription = "Добавить")
                }
            }
        },
    ) { innerPadding ->
        val dashboard = uiState.dashboard
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (uiState.session?.isAuthenticated != true) {
                item {
                    SignInCard(
                        state = uiState,
                        mode = authMode,
                        email = loginEmail,
                        password = loginPassword,
                        confirmPassword = registerConfirmPassword,
                        displayName = registerDisplayName,
                        onModeChange = {
                            authMode = it
                            uiState = uiState.copy(message = if (it == AuthMode.Login) "Войдите, чтобы увидеть финансы" else "Создайте новый аккаунт")
                        },
                        onEmailChange = { loginEmail = it },
                        onPasswordChange = { loginPassword = it },
                        onConfirmPasswordChange = { registerConfirmPassword = it },
                        onDisplayNameChange = { registerDisplayName = it },
                        onLogin = { login(loginEmail, loginPassword) },
                        onRegister = {
                            register(
                                loginEmail,
                                loginPassword,
                                registerConfirmPassword,
                                registerDisplayName,
                            )
                        },
                    )
                }
            }

            if (uiState.session?.isAuthenticated == true && dashboard == null && uiState.isLoading) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 32.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator()
                    }
                }
            }

            when (selectedSection) {
                AppSection.Home -> homeContent(
                    dashboard = dashboard,
                    selectedMode = selectedMode,
                    syncUiState = syncUiState,
                    onModeSelected = {},
                    onSyncAttentionClick = { openSyncAttention() },
                    onOpenPlanning = {
                        selectedSection = AppSection.Analytics
                        selectedAnalyticsSubsection = AnalyticsSubsection.Planning
                    },
                )
                AppSection.Operations -> operationsContent(
                    dashboard = dashboard,
                    selectedMode = selectedMode,
                    onModeSelected = {},
                    captureDrafts = captureDrafts,
                    screenshotAggregateDrafts = screenshotAggregateDrafts,
                    captureIsLoading = captureIsLoading,
                    captureMessage = captureMessage,
                    screenshotOcrStatus = screenshotOcrStatus,
                    onRefreshCaptureDrafts = { loadCaptureDrafts() },
                    onPickScreenshot = {
                        screenshotPickerLauncher.launch(
                            PickVisualMediaRequest(
                                ActivityResultContracts.PickVisualMedia.ImageOnly,
                            ),
                        )
                    },
                    onAggregateCategorySelected = ::updateScreenshotAggregateCategory,
                    onAggregateIncludedChanged = ::updateScreenshotAggregateIncluded,
                    onAggregateCreateCategory = { draftKey, categoryName ->
                        scope.launch {
                                uiState = uiState.copy(isLoading = true, message = "Создаём категорию")
                                val result = withContext(Dispatchers.IO) {
                                    apiClient.createCategory(
                                        name = categoryName,
                                        householdId = null,
                                        categoryType = "expense",
                                    )
                                }
                                when (result) {
                                    is ApiResult.Success -> {
                                        val newCategoryId = result.value.id
                                        updateScreenshotAggregateCategory(draftKey, newCategoryId)
                                        updateScreenshotAggregateIncluded(draftKey, true)
                                        loadDashboard("Категория «$categoryName» создана")
                                    }
                                    is ApiResult.Failure -> uiState = uiState.copy(
                                        isLoading = false,
                                        message = result.userFacingMessage(),
                                    )
                                }
                        }
                    },
                    onConfirmAggregateDrafts = ::createScreenshotAggregateDrafts,
                    onClearAggregateDrafts = {
                        screenshotAggregateDrafts = emptyList()
                        screenshotOcrStatus = null
                    },
                    onConfirmCaptureDraft = ::confirmCaptureDraft,
                    onDiscardCaptureDraft = ::discardCaptureDraft,
                    onDeleteTransaction = { transactionId ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Удаляем операцию")
                            when (val result = withContext(Dispatchers.IO) { apiClient.deleteTransaction(transactionId) }) {
                                is ApiResult.Success -> loadDashboard("Операция удалена")
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                )
                AppSection.Assets -> assetsContent(
                    dashboard = dashboard,
                    selectedMode = selectedMode,
                    onModeSelected = {},
                    groupNames = assetGroupNames,
                    onRenameGroup = { kind, newName ->
                        assetGroupNames = assetGroupNames + (kind.apiValue to newName)
                    },
                    onMigrateLegacyGroupToInvestment = migrate@ { kind, newName, accounts, onComplete ->
                        val fallbackCurrency = uiState.dashboard
                            ?.viewFor(selectedMode)
                            ?.primaryCurrency
                            ?.takeIf { it.isNotBlank() }
                        val targetSelection = selectLegacyAssetCategoryMigrationTarget(
                            selectedMode = selectedMode,
                            accounts = accounts,
                            sessionHouseholdId = uiState.session?.householdId,
                            fallbackCurrency = fallbackCurrency,
                            groupName = newName,
                        )
                        val target = when (targetSelection) {
                            is LegacyAssetCategoryMigrationTargetSelection.Ready -> targetSelection.target
                            is LegacyAssetCategoryMigrationTargetSelection.Blocked -> {
                                uiState = uiState.copy(message = targetSelection.message)
                                onComplete(LegacyGroupMigrationResult.Failure(targetSelection.message))
                                return@migrate
                            }
                        }
                        if (target.scopeType == "household" && target.householdId.isNullOrBlank()) {
                            val message = "Для общей инвестиционной категории нужна активная семья."
                            uiState = uiState.copy(message = message)
                            onComplete(LegacyGroupMigrationResult.Failure(message))
                            return@migrate
                        }
                        val requestSelection = legacyInvestmentMigrationCreateRequest(
                            kind = kind,
                            nameDraft = newName,
                            target = target,
                            accounts = accounts,
                            assetCategoryId = UUID.randomUUID().toString(),
                        )
                        val migrationRequest = when (requestSelection) {
                            is LegacyInvestmentMigrationRequestSelection.Ready -> requestSelection.request
                            is LegacyInvestmentMigrationRequestSelection.Blocked -> {
                                uiState = uiState.copy(message = requestSelection.message)
                                onComplete(LegacyGroupMigrationResult.Failure(requestSelection.message))
                                return@migrate
                            }
                        }
                        val activeAccounts = accounts.filter { it.status == "active" && it.assetCategoryId.isNullOrBlank() }
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Создаём инвестиционную категорию активов")
                            val result = withContext(Dispatchers.IO) {
                                apiClient.createInvestmentMigration(migrationRequest)
                            }
                            when (result) {
                                is ApiResult.Success -> {
                                    assetGroupNames = assetGroupNames - kind.apiValue
                                    onComplete(LegacyGroupMigrationResult.Success)
                                    loadDashboard("Legacy-группа «$newName» стала инвестиционной категорией")
                                }
                                is ApiResult.Failure -> {
                                    if (enqueueOfflineInvestmentMigrationIfRetriable(result, migrationRequest, activeAccounts)) {
                                        assetGroupNames = assetGroupNames - kind.apiValue
                                        onComplete(LegacyGroupMigrationResult.Success)
                                    } else {
                                        val message = result.userFacingMessage()
                                        uiState = uiState.copy(isLoading = false, message = message)
                                        onComplete(LegacyGroupMigrationResult.Failure(message))
                                    }
                                }
                            }
                        }
                    },
                    onCreateLegacyManualCategory = manual@ { kind, name, manualAmount, isInvestment, onComplete ->
                        val fallbackCurrency = uiState.dashboard
                            ?.viewFor(selectedMode)
                            ?.primaryCurrency
                            ?.takeIf { it.isNotBlank() }
                        val targetSelection = selectLegacyAssetCategoryMigrationTarget(
                            selectedMode = selectedMode,
                            accounts = emptyList(),
                            sessionHouseholdId = uiState.session?.householdId,
                            fallbackCurrency = fallbackCurrency,
                            groupName = name,
                        )
                        val target = when (targetSelection) {
                            is LegacyAssetCategoryMigrationTargetSelection.Ready -> targetSelection.target
                            is LegacyAssetCategoryMigrationTargetSelection.Blocked -> {
                                uiState = uiState.copy(message = targetSelection.message)
                                onComplete(LegacyGroupMigrationResult.Failure(targetSelection.message))
                                return@manual
                            }
                        }
                        val request = legacyManualAssetCategoryCreateRequest(
                            kind = kind,
                            nameDraft = name,
                            manualAmountDraft = manualAmount,
                            isInvestmentChecked = isInvestment,
                            target = target,
                        )
                        if (request == null) {
                            val message = "Введите корректную ручную сумму"
                            uiState = uiState.copy(message = message)
                            onComplete(LegacyGroupMigrationResult.Failure(message))
                            return@manual
                        }
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Создаём ручную категорию активов")
                            when (val result = withContext(Dispatchers.IO) { apiClient.createAssetCategory(request) }) {
                                is ApiResult.Success -> {
                                    assetGroupNames = assetGroupNames - kind.apiValue
                                    onComplete(LegacyGroupMigrationResult.Success)
                                    loadDashboard("Ручная категория активов «${request.name}» создана")
                                }
                                is ApiResult.Failure -> {
                                    if (enqueueOfflineAssetCategoryCreateIfRetriable(result, request)) {
                                        assetGroupNames = assetGroupNames - kind.apiValue
                                        onComplete(LegacyGroupMigrationResult.Success)
                                    } else {
                                        val message = result.userFacingMessage()
                                        uiState = uiState.copy(isLoading = false, message = message)
                                        onComplete(LegacyGroupMigrationResult.Failure(message))
                                    }
                                }
                            }
                        }
                    },
                    onCreateAssetCategory = { showAssetCategorySheet = true },
                    onUpdateAssetCategory = { category ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Обновляем категорию активов")
                            val result = withContext(Dispatchers.IO) { apiClient.updateAssetCategory(category) }
                            when (result) {
                                is ApiResult.Success -> {
                                    uiState = uiState.copy(
                                        isLoading = false,
                                        dashboard = uiState.dashboard?.withUpdatedAssetCategory(result.value),
                                        message = "Категория активов обновлена",
                                    )
                                    loadDashboard("Категория активов обновлена")
                                }
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                    onUpdateAccount = { updatedAccount ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Обновляем актив")
                            val result = withContext(Dispatchers.IO) {
                                apiClient.updateAccount(updatedAccount)
                            }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Актив обновлён")
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                    onArchiveAccount = { accountId ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Удаляем актив")
                            val result = withContext(Dispatchers.IO) { apiClient.archiveAccount(accountId) }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Актив удалён")
                                is ApiResult.Failure -> {
                                    if (!enqueueOfflineAccountArchiveIfRetriable(result, accountId)) {
                                        uiState = uiState.copy(
                                            isLoading = false,
                                            message = result.userFacingMessage(),
                                        )
                                    }
                                }
                            }
                        }
                    },
                    onArchiveAssetCategory = { categoryId ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Удаляем категорию активов")
                            val result = withContext(Dispatchers.IO) { apiClient.archiveAssetCategory(categoryId) }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория активов удалена")
                                is ApiResult.Failure -> {
                                    if (!enqueueOfflineAssetCategoryArchiveIfRetriable(result, categoryId)) {
                                        uiState = uiState.copy(
                                            isLoading = false,
                                            message = result.userFacingMessage(),
                                        )
                                    }
                                }
                            }
                        }
                    },
                    onAddAccount = { kind ->
                        addAccountState = AddAccountState(kind, FinanceMode.Personal)
                    },
                    onAddAccountToCategory = { category ->
                        addAccountState = AddAccountState(category.assetType.assetKindOrBank(), FinanceMode.Personal, category.id)
                    },
                )
                AppSection.Categories -> categoriesContent(
                    dashboard = dashboard,
                    onAddCategory = { name, type, mode ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Добавляем категорию")
                            val result = withContext(Dispatchers.IO) {
                                apiClient.createCategory(
                                    name = name,
                                    householdId = null,
                                    categoryType = "expense",
                                )
                            }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория добавлена")
                                is ApiResult.Failure -> {
                                    if (!enqueueOfflineCategoryCreateIfRetriable(result, name, type.apiValue, mode)) {
                                        uiState = uiState.copy(
                                            isLoading = false,
                                            message = result.userFacingMessage(),
                                        )
                                    }
                                }
                            }
                        }
                    },
                    onUpdateCategory = { category, newName ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Обновляем категорию")
                            val result = withContext(Dispatchers.IO) {
                                apiClient.updateCategory(category.copy(name = newName))
                            }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория обновлена")
                                is ApiResult.Failure -> {
                                    if (!enqueueOfflineCategoryUpdateIfRetriable(result, category, newName)) {
                                        uiState = uiState.copy(
                                            isLoading = false,
                                            message = result.userFacingMessage(),
                                        )
                                    }
                                }
                            }
                        }
                    },
                    onArchiveCategory = { categoryId ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Удаляем категорию")
                            val result = withContext(Dispatchers.IO) { apiClient.archiveCategory(categoryId) }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория удалена")
                                is ApiResult.Failure -> {
                                    if (!enqueueOfflineCategoryArchiveIfRetriable(result, categoryId)) {
                                        uiState = uiState.copy(
                                            isLoading = false,
                                            message = result.userFacingMessage(),
                                        )
                                    }
                                }
                            }
                        }
                    },
                )
                AppSection.Analytics -> analyticsContent(
                    apiClient = apiClient,
                    dashboard = dashboard,
                    planningRepository = planningRepository,
                    selectedMode = selectedMode,
                    selectedSubsection = selectedAnalyticsSubsection,
                    selectedReportMonth = selectedReportMonth,
                    onModeSelected = {},
                    onSubsectionSelected = { selectedAnalyticsSubsection = it },
                    onReportMonthSelected = { month ->
                        selectedReportMonth = month
                        loadDashboard("Данные обновлены", )
                    },
                    onCreatePlanningCategory = { name, mode ->
                        val result = withContext(Dispatchers.IO) {
                            apiClient.createCategory(
                                name = name,
                                householdId = null,
                                categoryType = "expense",
                            )
                        }
                        if (result is ApiResult.Success) {
                            loadDashboard("Категория добавлена")
                        }
                        result
                    },
                    onCreatePlanningAccount = { name, currency, accountType, mode ->
                        val result = withContext(Dispatchers.IO) {
                            apiClient.createAccount(
                                name = name,
                                currency = currency,
                                initialBalance = "0",
                                accountType = accountType,
                                householdId = null,
                            )
                        }
                        if (result is ApiResult.Success) {
                            loadDashboard("Счёт добавлен")
                        }
                        result
                    },
                    onPlanningNotificationCandidate = { candidate ->
                        PlanningReminderNotifications.applyCandidate(context.applicationContext, candidate)
                    },
                    onPlanningOfflineMutationQueued = { queuedUserId ->
                        TransactionSyncWorker.enqueue(context, queuedUserId)
                        scope.launch {
                            refreshSyncUiState(queuedUserId, savedOffline = true)
                        }
                    },
                )
            }

            item { Spacer(modifier = Modifier.height(72.dp)) }
        }
    }

    if (showQuickAdd) {
        QuickAddSheet(
            sheetKey = quickAddOpenKey,
            dashboard = uiState.dashboard,
            selectedMode = selectedMode,
            errorMessage = quickAddError,
            onDismiss = {
                quickAddError = null
                showQuickAdd = false
            },
            onSubmit = ::submitQuickAdd,
        )
    }

    if (addAccountState != null) {
        val state = addAccountState!!
        val kind = state.kind
        AddAccountSheet(
            kind = kind,
            initialMode = state.mode,
            hasHousehold = !uiState.session?.householdId.isNullOrBlank(),
            onDismiss = { addAccountState = null },
            onSubmit = { name, balance, currency, mode, isPaymentAccount ->
                scope.launch {
                    uiState = uiState.copy(isLoading = true, message = "Добавляем актив")
                    val result = withContext(Dispatchers.IO) {
                        apiClient.createAccount(
                            name = name,
                            currency = currency,
                            initialBalance = balance,
                            accountType = kind.apiValue,
                            householdId = null,
                            assetCategoryId = state.assetCategoryId,
                            isPaymentAccount = isPaymentAccount,
                        )
                    }
                    when (result) {
                        is ApiResult.Success -> {
                            addAccountState = null
                            loadDashboard("Актив добавлен")
                        }
                        is ApiResult.Failure -> {
                            if (enqueueOfflineAccountCreateIfRetriable(
                                    failure = result,
                                    name = name,
                                    balance = balance,
                                    currency = currency,
                                    accountType = kind.apiValue,
                                    mode = mode,
                                    assetCategoryId = state.assetCategoryId,
                                    isPaymentAccount = isPaymentAccount,
                                )
                            ) {
                                addAccountState = null
                            } else {
                                uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    }
                }
            },
        )
    }

    if (showAssetCategorySheet) {
        AssetCategorySheet(
            mode = selectedMode,
            householdId = uiState.session?.householdId,
            onDismiss = { showAssetCategorySheet = false },
            onCreate = { request ->
                scope.launch {
                    uiState = uiState.copy(isLoading = true, message = "Добавляем категорию активов")
                    val result = withContext(Dispatchers.IO) { apiClient.createAssetCategory(request) }
                    when (result) {
                        is ApiResult.Success -> {
                            showAssetCategorySheet = false
                            loadDashboard("Категория активов добавлена")
                        }
                        is ApiResult.Failure -> {
                            if (enqueueOfflineAssetCategoryCreateIfRetriable(result, request)) {
                                showAssetCategorySheet = false
                            } else {
                                uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    }
                }
            },
        )
    }

    if (showSyncIssuesSheet) {
        SyncIssuesSheet(
            issues = syncIssues,
            loading = syncIssuesLoading,
            syncing = syncUiState.isSyncing,
            onRetry = { runManualSync() },
            onDismiss = { showSyncIssuesSheet = false },
        )
    }
}

internal data class LoginCredentials(
    val email: String,
    val password: String,
)

internal data class RegistrationCredentials(
    val email: String,
    val password: String,
    val displayName: String?,
)

internal enum class AuthMode {
    Login,
    Register,
}

internal data class RegistrationUiUpdate(
    val mode: AuthMode,
    val state: FinanceUiState,
)

internal sealed interface RegistrationValidationResult {
    data class Valid(val credentials: RegistrationCredentials) : RegistrationValidationResult
    data class Invalid(val message: String) : RegistrationValidationResult
}

private const val MIN_REGISTRATION_PASSWORD_LENGTH = 12
internal const val REGISTRATION_ACCEPTED_MESSAGE = "Заявка принята. Если аккаунт доступен, войдите по email и паролю."

internal fun registrationAcceptedUiUpdate(): RegistrationUiUpdate {
    return RegistrationUiUpdate(
        mode = AuthMode.Login,
        state = FinanceUiState(message = REGISTRATION_ACCEPTED_MESSAGE),
    )
}

internal fun loginCredentialsOrNull(email: String, password: String): LoginCredentials? {
    val normalizedEmail = email.trim()
    return LoginCredentials(normalizedEmail, password)
        .takeIf { it.email.isNotBlank() && it.password.isNotBlank() }
}

internal fun registrationCredentialsOrError(
    email: String,
    password: String,
    confirmPassword: String,
    displayName: String,
): RegistrationValidationResult {
    val normalizedEmail = email.trim()
    val normalizedDisplayName = displayName.trim().takeIf { it.isNotBlank() }
    return when {
        normalizedEmail.isBlank() -> RegistrationValidationResult.Invalid("Введите email")
        password.isBlank() -> RegistrationValidationResult.Invalid("Введите пароль")
        confirmPassword.isBlank() -> RegistrationValidationResult.Invalid("Повторите пароль")
        password.length < MIN_REGISTRATION_PASSWORD_LENGTH -> RegistrationValidationResult.Invalid("Пароль должен быть не короче 12 символов")
        password != confirmPassword -> RegistrationValidationResult.Invalid("Пароли не совпадают")
        else -> RegistrationValidationResult.Valid(
            RegistrationCredentials(
                email = normalizedEmail,
                password = password,
                displayName = normalizedDisplayName,
            ),
        )
    }
}

@Composable
private fun SignInCard(
    state: FinanceUiState,
    mode: AuthMode,
    email: String,
    password: String,
    confirmPassword: String,
    displayName: String,
    onModeChange: (AuthMode) -> Unit,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onConfirmPasswordChange: (String) -> Unit,
    onDisplayNameChange: (String) -> Unit,
    onLogin: () -> Unit,
    onRegister: () -> Unit,
) {
    ElevatedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("signin-card"),
        colors = CardDefaults.elevatedCardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_wallet_24),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = state.message,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = state.session?.displayName ?: "Личный кабинет",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = mode == AuthMode.Login,
                    onClick = { onModeChange(AuthMode.Login) },
                    label = { Text("Вход") },
                    enabled = !state.isLoading,
                )
                FilterChip(
                    selected = mode == AuthMode.Register,
                    onClick = { onModeChange(AuthMode.Register) },
                    label = { Text("Регистрация") },
                    enabled = !state.isLoading,
                )
            }
            OutlinedTextField(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("login-email-field"),
                value = email,
                onValueChange = onEmailChange,
                label = { Text("Электронная почта") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                enabled = !state.isLoading,
            )
            OutlinedTextField(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("login-password-field")
                    .semantics { password() },
                value = password,
                onValueChange = onPasswordChange,
                label = { Text("Пароль") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                enabled = !state.isLoading,
            )
            if (mode == AuthMode.Register) {
                OutlinedTextField(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("register-confirm-password-field")
                        .semantics { password() },
                    value = confirmPassword,
                    onValueChange = onConfirmPasswordChange,
                    label = { Text("Повторите пароль") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    enabled = !state.isLoading,
                )
                OutlinedTextField(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("register-display-name-field"),
                    value = displayName,
                    onValueChange = onDisplayNameChange,
                    label = { Text("Имя (необязательно)") },
                    singleLine = true,
                    enabled = !state.isLoading,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                Button(
                    modifier = Modifier.testTag("login-submit-button"),
                    onClick = if (mode == AuthMode.Login) onLogin else onRegister,
                    enabled = !state.isLoading,
                ) {
                    Text(if (mode == AuthMode.Login) "Войти" else "Создать аккаунт")
                }
            }
        }
    }
}

private fun LazyListScope.homeContent(
    dashboard: FinanceDashboard?,
    selectedMode: FinanceMode,
    syncUiState: SyncUiState,
    onModeSelected: (FinanceMode) -> Unit,
    onSyncAttentionClick: () -> Unit,
    onOpenPlanning: () -> Unit,
) {
    val view = dashboard.viewFor(selectedMode)
    syncAttention(syncUiState)?.let { attention ->
        item { SyncAttentionChip(attention, onClick = onSyncAttentionClick) }
    }
    item { PlanningEntryCard(onOpenPlanning) }
    item { CapitalCard(view) }
    item { AssetChips(view.assetSummaries) }
    item { MonthExpenseCard(view) }
    item { TopCategoriesCard(view.topCategories) }
    item { RecentOperationsCard(view.recentTransactions) }
}

private fun LazyListScope.operationsContent(
    dashboard: FinanceDashboard?,
    selectedMode: FinanceMode,
    onModeSelected: (FinanceMode) -> Unit,
    captureDrafts: List<CaptureDraft>,
    screenshotAggregateDrafts: List<ScreenshotAggregateDraftUi>,
    captureIsLoading: Boolean,
    captureMessage: String?,
    screenshotOcrStatus: String?,
    onRefreshCaptureDrafts: () -> Unit,
    onPickScreenshot: () -> Unit,
    onAggregateCategorySelected: (String, String) -> Unit,
    onAggregateIncludedChanged: (String, Boolean) -> Unit,
    onAggregateCreateCategory: (String, String) -> Unit,
    onConfirmAggregateDrafts: () -> Unit,
    onClearAggregateDrafts: () -> Unit,
    onConfirmCaptureDraft: (CaptureDraft, String, String, String, String) -> Unit,
    onDiscardCaptureDraft: (CaptureDraft) -> Unit,
    onDeleteTransaction: (String) -> Unit,
) {
    val view = dashboard.viewFor(selectedMode)
    val items = dashboard.transactionsFor(selectedMode)
    val reviewAccounts = dashboard?.accounts.orEmpty()
        .filter { it.status == "active" && it.id.isNotBlank() }
        .filter { it.matchesWritableMode(selectedMode) }
    val reviewCategories = dashboard?.categories.orEmpty()
        .filter { it.status == "active" && it.id.isNotBlank() }
        .filter { it.matchesWritableMode(selectedMode) }
    item {
        CaptureDraftReviewCard(
            isAuthenticated = dashboard?.session?.isAuthenticated == true,
            drafts = captureDrafts,
            screenshotAggregateDrafts = screenshotAggregateDrafts,
            accounts = reviewAccounts,
            categories = reviewCategories,
            isLoading = captureIsLoading,
            message = captureMessage,
            screenshotOcrStatus = screenshotOcrStatus,
            onRefresh = onRefreshCaptureDrafts,
            onPickScreenshot = onPickScreenshot,
            onAggregateCategorySelected = onAggregateCategorySelected,
            onAggregateIncludedChanged = onAggregateIncludedChanged,
            onAggregateCreateCategory = onAggregateCreateCategory,
            onConfirmAggregateDrafts = onConfirmAggregateDrafts,
            onClearAggregateDrafts = onClearAggregateDrafts,
            onConfirm = onConfirmCaptureDraft,
            onDiscard = onDiscardCaptureDraft,
        )
    }
    if (items.isEmpty()) {
        item {
            EmptyState(
                "Операций пока нет. Добавьте расход, доход или перевод.",
            )
        }
    }
    item { Text("Операции", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
    items(items.sortedNewestFirst(), key = { it.id }) { transaction ->
        TransactionRow(transaction, dashboard?.categories.orEmpty()) {
            onDeleteTransaction(transaction.id)
        }
    }
}

@Composable
private fun CaptureDraftReviewCard(
    isAuthenticated: Boolean,
    drafts: List<CaptureDraft>,
    screenshotAggregateDrafts: List<ScreenshotAggregateDraftUi>,
    accounts: List<AccountSummary>,
    categories: List<CategorySummary>,
    isLoading: Boolean,
    message: String?,
    screenshotOcrStatus: String?,
    onRefresh: () -> Unit,
    onPickScreenshot: () -> Unit,
    onAggregateCategorySelected: (String, String) -> Unit,
    onAggregateIncludedChanged: (String, Boolean) -> Unit,
    onAggregateCreateCategory: (String, String) -> Unit,
    onConfirmAggregateDrafts: () -> Unit,
    onClearAggregateDrafts: () -> Unit,
    onConfirm: (CaptureDraft, String, String, String, String) -> Unit,
    onDiscard: (CaptureDraft) -> Unit,
) {
    ElevatedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("capture-draft-review"),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(R.drawable.ic_receipt_24, Color(0xFF227C9D), size = 36)
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("Черновики операций", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("Проверьте распознанные данные перед созданием", style = MaterialTheme.typography.bodySmall)
                }
            }

            Button(
                onClick = onPickScreenshot,
                enabled = isAuthenticated && !isLoading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Выбрать скриншот")
            }

            screenshotOcrStatus?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = onRefresh,
                    enabled = isAuthenticated && !isLoading,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Обновить")
                }
            }

            message?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }

            if (screenshotAggregateDrafts.isNotEmpty()) {
                ScreenshotAggregateDraftList(
                    drafts = screenshotAggregateDrafts,
                    categories = categories,
                    isLoading = isLoading,
                    onCategorySelected = onAggregateCategorySelected,
                    onIncludedChanged = onAggregateIncludedChanged,
                    onCreateCategory = onAggregateCreateCategory,
                    onConfirm = onConfirmAggregateDrafts,
                    onClear = onClearAggregateDrafts,
                )
            }

            if (!isAuthenticated) {
                Text("Войдите, чтобы синхронизировать черновики.", style = MaterialTheme.typography.bodySmall)
            } else if ((drafts.isNotEmpty() || screenshotAggregateDrafts.isNotEmpty()) && (accounts.isEmpty() || categories.isEmpty())) {
                Text(
                    "Для проверки OCR-черновиков сначала создайте личный счёт и категорию расходов.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else if (drafts.isEmpty() && screenshotAggregateDrafts.isEmpty()) {
                Text("Нет черновиков на проверку. Отправьте скрин в backend OCR или обновите список.", style = MaterialTheme.typography.bodySmall)
            } else {
                drafts.forEach { draft ->
                    CaptureDraftRow(
                        draft = draft,
                        accounts = accounts,
                        categories = categories,
                        isLoading = isLoading,
                        onConfirm = onConfirm,
                        onDiscard = onDiscard,
                    )
                }
            }
        }
    }
}

@Composable
private fun ScreenshotAggregateDraftList(
    drafts: List<ScreenshotAggregateDraftUi>,
    categories: List<CategorySummary>,
    isLoading: Boolean,
    onCategorySelected: (String, String) -> Unit,
    onIncludedChanged: (String, Boolean) -> Unit,
    onCreateCategory: (String, String) -> Unit,
    onConfirm: () -> Unit,
    onClear: () -> Unit,
) {
    val expenseCategories = categories
        .filter { it.status == "active" && it.type == "expense" && it.id.isNotBlank() }
        .sortedBy { it.displayName() }
    val selectedCount = drafts.count { it.include && it.selectedCategoryId.isNotBlank() }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            "Категории на скриншоте",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        drafts.forEach { draft ->
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            draft.candidate.externalLabel,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            "${draft.candidate.operationCount} операций",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Text(
                        "-${draft.candidate.amount} ${draft.candidate.currency}",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Color(0xFFE35D4F),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = draft.include,
                        onClick = { onIncludedChanged(draft.key, !draft.include) },
                        enabled = !isLoading,
                        label = { Text(if (draft.include) "Включено" else "Пропустить") },
                    )
                    val matchedCategory = expenseCategories.firstOrNull { it.id == draft.selectedCategoryId }
                    if (matchedCategory == null) {
                        OutlinedButton(
                            onClick = { onCreateCategory(draft.key, draft.candidate.externalLabel) },
                            enabled = !isLoading,
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                        ) {
                            Text("Новая", style = MaterialTheme.typography.labelLarge)
                        }
                    }
                }
                if (expenseCategories.isEmpty()) {
                    Text("Нет активных категорий расходов", style = MaterialTheme.typography.bodySmall)
                } else {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(expenseCategories) { category ->
                            FilterChip(
                                selected = draft.selectedCategoryId == category.id,
                                onClick = { onCategorySelected(draft.key, category.id) },
                                enabled = !isLoading,
                                label = {
                                    Text(
                                        category.displayName(),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                },
                                leadingIcon = {
                                    Icon(
                                        painter = painterResource(category.icon()),
                                        contentDescription = null,
                                        modifier = Modifier.size(18.dp),
                                    )
                                },
                            )
                        }
                    }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = onClear,
                enabled = !isLoading,
                modifier = Modifier.weight(1f),
            ) {
                Text("Отмена")
            }
            Button(
                onClick = onConfirm,
                enabled = !isLoading && selectedCount > 0,
                modifier = Modifier.weight(1f),
            ) {
                Text("Создать $selectedCount")
            }
        }
    }
}

@Composable
private fun CaptureDraftRow(
    draft: CaptureDraft,
    accounts: List<AccountSummary>,
    categories: List<CategorySummary>,
    isLoading: Boolean,
    onConfirm: (CaptureDraft, String, String, String, String) -> Unit,
    onDiscard: (CaptureDraft) -> Unit,
) {
    var selectedAccountId by rememberSaveable(draft.id, draft.accountId) { mutableStateOf(draft.accountId.orEmpty()) }
    var selectedCategoryId by rememberSaveable(draft.id, draft.categoryId) { mutableStateOf(draft.categoryId.orEmpty()) }
    var amount by rememberSaveable(draft.id, draft.amount) { mutableStateOf(draft.amount) }
    var occurredDate by rememberSaveable(draft.id, draft.occurredDate, draft.capturedAt) {
        mutableStateOf(draft.occurredDate.ifBlank { draft.capturedAt?.take(10).orEmpty() }.ifBlank { currentDateString() })
    }
    val activeAccounts = accounts
        .filter { it.status == "active" && it.id.isNotBlank() && it.isPaymentAccount }
        .sortedBy { it.displayName() }
    val expenseCategories = categories
        .filter { it.status == "active" && it.type == "expense" && it.id.isNotBlank() }
        .sortedBy { it.displayName() }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = draft.merchantName ?: draft.description ?: "Распознанный платёж",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "${draft.captureSource.localizedCaptureSource()} $occurredDate",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text(
                text = "-${amount.ifBlank { draft.amount }} ${draft.currency}",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFFE35D4F),
            )
        }
        Text(
            text = "Точность ${(draft.confidence * 100).toInt()}% | След ${draft.evidenceHash.take(12)}",
            style = MaterialTheme.typography.bodySmall,
        )
        OutlinedTextField(
            value = amount,
            onValueChange = { amount = it.filter { char -> char.isDigit() || char == '.' || char == ',' } },
            label = { Text("Сумма") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        DatePickerField(
            label = "Дата операции",
            date = occurredDate,
            onDateSelected = { occurredDate = it },
        )
        Text("Счёт", style = MaterialTheme.typography.labelLarge)
        if (activeAccounts.isEmpty()) {
            Text("Нет активных счетов", style = MaterialTheme.typography.bodySmall)
        } else {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(activeAccounts) { account ->
                    FilterChip(
                        selected = selectedAccountId == account.id,
                        onClick = { selectedAccountId = account.id },
                        label = {
                            Text(
                                account.displayName(),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        },
                    )
                }
            }
        }
        Text("Категория", style = MaterialTheme.typography.labelLarge)
        if (expenseCategories.isEmpty()) {
            Text("Нет активных категорий расходов", style = MaterialTheme.typography.bodySmall)
        } else {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(expenseCategories) { category ->
                    FilterChip(
                        selected = selectedCategoryId == category.id,
                        onClick = { selectedCategoryId = category.id },
                        label = {
                            Text(
                                category.displayName(),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        },
                    )
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = { onDiscard(draft) },
                enabled = !isLoading && draft.id.isNotBlank(),
                modifier = Modifier.weight(1f),
            ) {
                Text("Отклонить")
            }
            Button(
                onClick = { onConfirm(draft, selectedAccountId, selectedCategoryId, amount, occurredDate) },
                enabled = !isLoading &&
                    draft.id.isNotBlank() &&
                    selectedAccountId.isNotBlank() &&
                    selectedCategoryId.isNotBlank() &&
                    amount.normalizedAmount() != null &&
                    occurredDate.isDateOnly(),
                modifier = Modifier.weight(1f),
            ) {
                Text("Подтвердить")
            }
        }
    }
}

private fun LazyListScope.assetsContent(
    dashboard: FinanceDashboard?,
    selectedMode: FinanceMode,
    onModeSelected: (FinanceMode) -> Unit,
    groupNames: Map<String, String>,
    onRenameGroup: (AssetKind, String) -> Unit,
    onMigrateLegacyGroupToInvestment: (AssetKind, String, List<AccountSummary>, (LegacyGroupMigrationResult) -> Unit) -> Unit,
    onCreateLegacyManualCategory: (AssetKind, String, String, Boolean, (LegacyGroupMigrationResult) -> Unit) -> Unit,
    onCreateAssetCategory: () -> Unit,
    onUpdateAssetCategory: (AssetCategory) -> Unit,
    onUpdateAccount: (AccountSummary) -> Unit,
    onArchiveAccount: (String) -> Unit,
    onArchiveAssetCategory: (String) -> Unit,
    onAddAccount: (AssetKind) -> Unit,
    onAddAccountToCategory: (AssetCategory) -> Unit,
) {
    val allAccounts = dashboard?.accounts.orEmpty()
    val categoryRows = dashboard.assetCategoryRows(selectedMode)
    val modeAccounts = allAccounts.filterByMode(selectedMode)
    val legacyAccounts = modeAccounts.filter { it.status == "active" && it.assetCategoryId.isNullOrBlank() }
    val representedAssetTypes = categoryRows.map { it.category.assetType }.toSet()
    val summaries = assetSummaries(legacyAccounts).filter { summary ->
        summary.count > 0 || summary.kind.apiValue !in representedAssetTypes
    }
    item { Text("Активы", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
    item {
        OutlinedButton(onClick = onCreateAssetCategory, modifier = Modifier.fillMaxWidth()) {
            Text("Добавить категорию активов")
        }
    }
    if (categoryRows.isNotEmpty()) {
        item {
            ReorderableAssetCategoryList(
                rows = categoryRows,
                accounts = modeAccounts,
                selectedMode = selectedMode,
                onUpdateCategory = onUpdateAssetCategory,
                onArchiveCategory = onArchiveAssetCategory,
                onUpdateAccount = onUpdateAccount,
                onArchiveAccount = onArchiveAccount,
                onAddAccountToCategory = onAddAccountToCategory,
            )
        }
    }
    if (categoryRows.isEmpty() && modeAccounts.filter { it.status == "active" }.isEmpty()) {
        item { EmptyState("Активов пока нет") }
    }
    items(summaries) { summary ->
        AssetCategoryCard(
            summary = summary,
            accounts = legacyAccounts.filter { it.assetKind() == summary.kind },
            displayName = groupNames[summary.kind.apiValue] ?: summary.kind.title,
            onRenameGroup = { name ->
                onRenameGroup(summary.kind, name)
            },
            onCreateManualCategory = { name, manualAmount, isInvestment, onComplete ->
                onCreateLegacyManualCategory(summary.kind, name, manualAmount, isInvestment, onComplete)
            },
            onMigrateGroupToInvestment = { name, onComplete ->
                val groupAccounts = legacyAccounts.filter { it.assetKind() == summary.kind }
                onMigrateLegacyGroupToInvestment(summary.kind, name, groupAccounts, onComplete)
            },
            onUpdate = onUpdateAccount,
            onArchive = onArchiveAccount,
            onAdd = { onAddAccount(summary.kind) },
        )
    }
}

private fun LazyListScope.categoriesContent(
    dashboard: FinanceDashboard?,
    onAddCategory: (String, QuickEntryType, FinanceMode) -> Unit,
    onUpdateCategory: (CategorySummary, String) -> Unit,
    onArchiveCategory: (String) -> Unit,
) {
    item {
        CategoryManagementCard(
            categories = dashboard?.categories.orEmpty(),
            isAuthenticated = dashboard?.session?.isAuthenticated == true,
            onAddCategory = onAddCategory,
            onUpdateCategory = onUpdateCategory,
            onArchiveCategory = onArchiveCategory,
        )
    }
}

private fun LazyListScope.analyticsContent(
    apiClient: FinanceApiClient,
    dashboard: FinanceDashboard?,
    planningRepository: PlanningRepository?,
    selectedMode: FinanceMode,
    selectedSubsection: AnalyticsSubsection,
    selectedReportMonth: String,
    onModeSelected: (FinanceMode) -> Unit,
    onSubsectionSelected: (AnalyticsSubsection) -> Unit,
    onReportMonthSelected: (String) -> Unit,
    onCreatePlanningCategory: suspend (String, FinanceMode) -> ApiResult<CategorySummary>,
    onCreatePlanningAccount: suspend (String, String, String, FinanceMode) -> ApiResult<AccountSummary>,
    onPlanningNotificationCandidate: (PlanningNotificationCandidate) -> Unit,
    onPlanningOfflineMutationQueued: (String) -> Unit,
) {
    val view = dashboard.viewFor(selectedMode)
    item {
        AnalyticsSubsectionTabs(
            selected = selectedSubsection,
            onSelected = onSubsectionSelected,
        )
    }
    when (selectedSubsection) {
        AnalyticsSubsection.Summary -> {
            item {
                ReportMonthSwitcher(
                    selectedMonth = selectedReportMonth,
                    onSelected = onReportMonthSelected,
                )
            }
            item { AnalyticsSummaryCard(view, dashboard?.investmentsTotal) }
            item { InvestmentsCard(dashboard?.investmentsTotal, dashboard?.investmentsByCurrency.orEmpty(), view.primaryCurrency) }
            item { CategoryBreakdownCard(view.topCategories) }
            item { CapitalBreakdownCard(view.assetSummaries) }
        }
        AnalyticsSubsection.Planning -> {
            item {
                PlanningUi(
                    apiClient = apiClient,
                    dashboard = dashboard,
                    selectedMode = selectedMode,
                    onModeSelected = onModeSelected,
                    onCreateCategory = onCreatePlanningCategory,
                    onCreateAccount = onCreatePlanningAccount,
                    onPlanningNotificationCandidate = onPlanningNotificationCandidate,
                    planningRepository = planningRepository,
                    onOfflineMutationQueued = onPlanningOfflineMutationQueued,
                )
            }
        }
    }
}

@Composable
private fun SyncActionButton(
    state: SyncUiState,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val attention = syncAttention(state)
    IconButton(
        onClick = onClick,
        enabled = enabled && !state.isSyncing,
        modifier = Modifier.testTag("sync-action-button"),
    ) {
        Icon(
            painterResource(R.drawable.ic_refresh_24),
            contentDescription = attention?.actionDescription ?: "Обновить и синхронизировать",
            tint = if (attention?.type == SyncAttentionType.Failed) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
    }
}

@Composable
private fun SyncAttentionChip(
    attention: SyncAttention,
    onClick: () -> Unit,
) {
    AssistChip(
        onClick = onClick,
        modifier = Modifier.testTag("sync-attention-chip"),
        leadingIcon = {
            Icon(
                painter = painterResource(R.drawable.ic_refresh_24),
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
        },
        label = { Text(attention.label) },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SyncIssuesSheet(
    issues: List<SyncIssueSummary>,
    loading: Boolean,
    syncing: Boolean,
    onRetry: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp)
                .testTag("sync-issues-sheet"),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Требует внимания", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(
                "Проблемы синхронизации",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (loading) {
                Box(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator()
                }
            } else if (issues.isEmpty()) {
                Text(
                    "Нет проблем синхронизации.",
                    modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                    style = MaterialTheme.typography.bodyMedium,
                )
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    issues.forEach { issue ->
                        SyncIssueRow(issue)
                    }
                }
            }
            Text(
                "Для отклонённых изменений: исправьте данные или обновите с сервера.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Закрыть")
                }
                Button(
                    onClick = onRetry,
                    enabled = !loading && !syncing,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(if (syncing) "Повторяем" else "Повторить")
                }
            }
        }
    }
}

@Composable
private fun SyncIssueRow(issue: SyncIssueSummary) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(
            containerColor = if (issue.status == SyncManager.MUTATION_STATUS_REJECTED) {
                MaterialTheme.colorScheme.errorContainer
            } else {
                MaterialTheme.colorScheme.surface
            },
        ),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                "${syncIssueEntityLabel(issue.entityType)} • ${syncIssueOperationLabel(issue.operation)}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                syncIssueStatusLabel(issue.status),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                syncIssueSafeError(issue.lastError),
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                listOf(
                    "Попыток: ${issue.attempts}",
                    syncIssueTimestampLabel(issue.updatedAtEpochMillis, issue.createdAtEpochMillis),
                ).joinToString(" • "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PlanningEntryCard(onOpenPlanning: () -> Unit) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBubble(R.drawable.ic_analytics_24, Color(0xFF4267D5))
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("План месяца", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("Доходы и распределения на месяц.", style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(onClick = onOpenPlanning) {
                Text("Открыть")
            }
        }
    }
}

@Composable
private fun CapitalCard(view: DashboardView) {
    ElevatedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("capital-card"),
        colors = CardDefaults.elevatedCardColors(
            containerColor = MaterialTheme.colorScheme.primary,
        ),
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = "Капитал",
                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.78f),
                style = MaterialTheme.typography.labelLarge,
            )
            Text(
                text = view.capital.formatMoney(view.primaryCurrency),
                color = MaterialTheme.colorScheme.onPrimary,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "${view.accountCount} активов • ${view.operationCount} операций",
                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.78f),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun AssetChips(summaries: List<AssetSummary>) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(summaries.filter { it.count > 0 }.ifEmpty { summaries.take(3) }) { summary ->
            AssistChip(
                onClick = {},
                leadingIcon = {
                    Icon(
                        painter = painterResource(summary.kind.icon),
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                },
                label = { Text("${summary.kind.title} ${summary.balance.formatMoney(summary.currency)}") },
            )
        }
    }
}

@Composable
private fun MonthExpenseCard(view: DashboardView) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBubble(R.drawable.ic_receipt_24, Color(0xFFE35D4F))
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("Расходы месяца", style = MaterialTheme.typography.labelLarge)
                Text(
                    text = view.monthExpenses.formatMoney(view.primaryCurrency),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("Доходы", style = MaterialTheme.typography.labelSmall)
                Text(view.monthIncome.formatMoney(view.primaryCurrency), fontWeight = FontWeight.Medium)
            }
        }
    }
}

@Composable
private fun TopCategoriesCard(categories: List<CategorySpend>) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Топ категории", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (categories.isEmpty()) {
                Text("Расходов пока нет. Добавьте расход.", style = MaterialTheme.typography.bodySmall)
            } else {
                categories.take(3).forEach { category ->
                    CategorySpendRow(category)
                }
            }
        }
    }
}

@Composable
private fun RecentOperationsCard(transactions: List<TransactionSummary>) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Последние операции", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (transactions.isEmpty()) {
                Text("Движений пока нет. Добавьте первую операцию.", style = MaterialTheme.typography.bodySmall)
            } else {
                transactions.take(4).forEach { transaction ->
                    CompactTransactionRow(transaction)
                }
            }
        }
    }
}

@Composable
private fun TransactionRow(
    transaction: TransactionSummary,
    categories: List<CategorySummary>,
    onDelete: () -> Unit,
) {
    val category = categories.firstOrNull { it.id == transaction.categoryId }
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBubble(transaction.icon(), transaction.tint())
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = category?.displayName() ?: transaction.localizedType(),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "${transaction.displayDate()} • ${transaction.displayDescription()}",
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                text = transaction.signedAmount(),
                color = transaction.tint(),
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = onDelete,
                modifier = Modifier.size(32.dp),
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_delete_24),
                    contentDescription = "Удалить",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}

@Composable
private fun CompactTransactionRow(transaction: TransactionSummary) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth(),
    ) {
        IconBubble(transaction.icon(), transaction.tint(), size = 34)
        Spacer(modifier = Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = transaction.displayDescription(),
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(transaction.displayDate(), style = MaterialTheme.typography.labelSmall)
        }
        Text(
            text = transaction.signedAmount(),
            color = transaction.tint(),
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun ReorderableAssetCategoryList(
    rows: List<AssetCategoryUiRow>,
    accounts: List<AccountSummary>,
    selectedMode: FinanceMode,
    onUpdateCategory: (AssetCategory) -> Unit,
    onArchiveCategory: (String) -> Unit,
    onUpdateAccount: (AccountSummary) -> Unit,
    onArchiveAccount: (String) -> Unit,
    onAddAccountToCategory: (AssetCategory) -> Unit,
) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val reorderThresholdPx = with(density) { 72.dp.toPx() }
    var savedOrder by remember(selectedMode) {
        mutableStateOf(loadAssetCategoryOrder(context, selectedMode))
    }
    val orderedRows = remember(rows, savedOrder) {
        rows.applyAssetCategoryOrder(savedOrder)
    }

    fun moveCategory(fromIndex: Int, toIndex: Int) {
        if (fromIndex !in orderedRows.indices || toIndex !in orderedRows.indices || fromIndex == toIndex) return
        val nextOrder = orderedRows.map { it.category.id }.toMutableList()
        val moved = nextOrder.removeAt(fromIndex)
        nextOrder.add(toIndex, moved)
        savedOrder = nextOrder
        saveAssetCategoryOrder(context, selectedMode, nextOrder)
    }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        orderedRows.forEachIndexed { index, row ->
            var dragOffset by remember(row.category.id) { mutableStateOf(0f) }
            Box(
                modifier = Modifier
                    .offset { IntOffset(0, dragOffset.roundToInt()) }
                    .pointerInput(row.category.id, index, orderedRows.size) {
                        detectDragGesturesAfterLongPress(
                            onDragCancel = { dragOffset = 0f },
                            onDragEnd = { dragOffset = 0f },
                            onDrag = { change, dragAmount ->
                                change.consume()
                                dragOffset += dragAmount.y
                                when {
                                    dragOffset > reorderThresholdPx && index < orderedRows.lastIndex -> {
                                        moveCategory(index, index + 1)
                                        dragOffset = 0f
                                    }
                                    dragOffset < -reorderThresholdPx && index > 0 -> {
                                        moveCategory(index, index - 1)
                                        dragOffset = 0f
                                    }
                                }
                            },
                        )
                    },
            ) {
                AssetCategoryGroupCard(
                    row = row,
                    accounts = accounts.filter { it.status == "active" && it.assetCategoryId == row.category.id },
                    onUpdateCategory = onUpdateCategory,
                    onArchiveCategory = onArchiveCategory,
                    onUpdateAccount = onUpdateAccount,
                    onArchiveAccount = onArchiveAccount,
                    onAddAccount = { onAddAccountToCategory(row.category) },
                )
            }
        }
    }
}

@Composable
private fun AssetCategoryGroupCard(
    row: AssetCategoryUiRow,
    accounts: List<AccountSummary>,
    onUpdateCategory: (AssetCategory) -> Unit,
    onArchiveCategory: (String) -> Unit,
    onUpdateAccount: (AccountSummary) -> Unit,
    onArchiveAccount: (String) -> Unit,
    onAddAccount: () -> Unit,
) {
    val category = row.category
    var isExpanded by rememberSaveable(category.id) { mutableStateOf(false) }
    var isEditing by rememberSaveable(category.id) { mutableStateOf(false) }
    var editName by rememberSaveable(category.id, category.name) { mutableStateOf(category.name) }
    var editInvestment by rememberSaveable(category.id, category.isInvestment) { mutableStateOf(category.isInvestment) }
    var editManualAmount by rememberSaveable(category.id, row.manualAmount) { mutableStateOf(row.manualAmount) }
    var editError by rememberSaveable(category.id) { mutableStateOf<String?>(null) }
    var confirmArchiveCategory by rememberSaveable(category.id) { mutableStateOf(false) }
    val isManualOnlyCategory = shouldEditAssetCategoryManualAmount(row, accounts)
    val iconOption = assetCategoryIcon(category.iconKey, category.assetType)
    val subtitle = if (accounts.isNotEmpty()) {
        "${accounts.size} ${pluralItems(accounts.size)}"
    } else {
        "Ручная ${row.manualAmount.toMoney().formatMoney(row.currency)}"
    }

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { isExpanded = !isExpanded },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box {
                    IconBubble(iconOption.icon, iconOption.tint)
                    if (category.isInvestment) {
                        Box(
                            modifier = Modifier
                                .align(Alignment.BottomEnd)
                                .size(18.dp)
                                .clip(CircleShape)
                                .background(Color(0xFF227C9D)),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(
                                painter = painterResource(R.drawable.ic_trending_up_24),
                                contentDescription = "Инвестиция",
                                tint = MaterialTheme.colorScheme.onPrimary,
                                modifier = Modifier.size(12.dp),
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(category.name, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Text(row.totalAmount.toMoney().formatMoney(row.currency), fontWeight = FontWeight.SemiBold)
                IconButton(
                    onClick = {
                        editName = category.name
                        editInvestment = category.isInvestment
                        editManualAmount = row.manualAmount
                        editError = null
                        isEditing = true
                    },
                    modifier = Modifier.size(32.dp),
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_edit_24),
                        contentDescription = "Изменить",
                        modifier = Modifier.size(18.dp),
                    )
                }
                IconButton(onClick = { confirmArchiveCategory = true }, modifier = Modifier.size(32.dp)) {
                    Icon(
                        painter = painterResource(R.drawable.ic_delete_24),
                        contentDescription = "Удалить категорию активов",
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }

            if (isExpanded && !isEditing) {
                if (accounts.isEmpty()) {
                    Text("Счетов в этой категории нет", style = MaterialTheme.typography.bodySmall)
                } else {
                    accounts.forEach { account ->
                        AccountRow(
                            account = account,
                            onUpdate = onUpdateAccount,
                            onArchive = onArchiveAccount,
                        )
                        if (account != accounts.last()) {
                            Spacer(modifier = Modifier.height(6.dp))
                        }
                    }
                }
                OutlinedButton(onClick = onAddAccount, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить счет в категорию")
                }
            }
        }
    }

    if (isEditing) {
        AlertDialog(
            onDismissRequest = { isEditing = false },
            title = { Text("Название группы") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = editName,
                        onValueChange = {
                            editName = it
                            editError = null
                        },
                        label = { Text("Название") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (isManualOnlyCategory) {
                        OutlinedTextField(
                            value = editManualAmount,
                            onValueChange = {
                                editManualAmount = it.filter { char -> char.isDigit() || char == '.' || char == ',' || char == '-' }
                                editError = null
                            },
                            label = { Text("Ручная сумма") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = editInvestment,
                            onCheckedChange = {
                                editInvestment = it
                                editError = null
                            },
                        )
                        Text("Инвестиция")
                    }
                    editError?.let { message ->
                        Text(
                            text = message,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val updated = updatedAssetCategoryFromGroupEdit(
                            category = category,
                            nameDraft = editName,
                            isInvestmentChecked = editInvestment,
                            manualAmountDraft = editManualAmount,
                            canEditManualAmount = isManualOnlyCategory,
                        )
                        if (updated == null) {
                            editError = assetCategoryGroupEditError(
                                nameDraft = editName,
                                manualAmountDraft = editManualAmount,
                                canEditManualAmount = isManualOnlyCategory,
                            )
                        } else {
                            onUpdateCategory(updated)
                            isEditing = false
                        }
                    },
                    enabled = editName.isNotBlank(),
                ) {
                    Text("Сохранить")
                }
            },
            dismissButton = {
                TextButton(onClick = { isEditing = false }) {
                    Text("Отмена")
                }
            },
        )
    }

    if (confirmArchiveCategory) {
        val activeAccountCount = accounts.size
        AlertDialog(
            onDismissRequest = { confirmArchiveCategory = false },
            title = {
                Text(if (activeAccountCount == 0) "Удалить категорию активов?" else "Категория не пуста")
            },
            text = {
                if (activeAccountCount == 0) {
                    Text("Категория «${category.name}» будет архивирована.")
                } else {
                    Text("В категории «${category.name}» есть активные счета: $activeAccountCount. Сначала переместите или удалите счета категории.")
                }
            },
            confirmButton = {
                if (activeAccountCount == 0) {
                    TextButton(
                        onClick = {
                            confirmArchiveCategory = false
                            isEditing = false
                            onArchiveCategory(category.id)
                        },
                    ) {
                        Text("Удалить")
                    }
                } else {
                    TextButton(onClick = { confirmArchiveCategory = false }) {
                        Text("Понятно")
                    }
                }
            },
            dismissButton = {
                if (activeAccountCount == 0) {
                    TextButton(onClick = { confirmArchiveCategory = false }) {
                        Text("Отмена")
                    }
                }
            },
        )
    }
}

@Composable
private fun AssetCategoryCard(
    summary: AssetSummary,
    accounts: List<AccountSummary>,
    displayName: String,
    onRenameGroup: (String) -> Unit,
    onCreateManualCategory: (String, String, Boolean, (LegacyGroupMigrationResult) -> Unit) -> Unit,
    onMigrateGroupToInvestment: (String, (LegacyGroupMigrationResult) -> Unit) -> Unit,
    onUpdate: (AccountSummary) -> Unit,
    onArchive: (String) -> Unit,
    onAdd: () -> Unit,
) {
    var isExpanded by rememberSaveable { mutableStateOf(false) }
    var isEditingGroup by rememberSaveable { mutableStateOf(false) }
    var groupNameDraft by rememberSaveable(displayName) { mutableStateOf(displayName) }
    var groupInvestmentDraft by rememberSaveable(displayName) { mutableStateOf(false) }
    var groupManualAmountDraft by rememberSaveable(displayName, summary.kind.apiValue) {
        mutableStateOf(summary.balance.toPlainString())
    }
    var groupSaveInProgress by rememberSaveable { mutableStateOf(false) }
    var groupSaveError by rememberSaveable { mutableStateOf<String?>(null) }
    val canEditManualAmount = shouldEditLegacyAssetGroupManualAmount(summary, accounts)

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .tapOrLongPress(
                            onTap = { isExpanded = !isExpanded },
                            onLongPress = {},
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconBubble(summary.kind.icon, summary.kind.tint)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(displayName, fontWeight = FontWeight.SemiBold)
                        Text(
                            text = when {
                                canEditManualAmount -> "Ручная ${summary.balance.formatMoney(summary.currency)}"
                                accounts.isEmpty() -> "Нажмите чтобы добавить"
                                else -> "${accounts.size} ${pluralItems(accounts.size)}"
                            },
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Text(
                        text = summary.balance.formatMoney(summary.currency),
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                Spacer(modifier = Modifier.width(4.dp))
                IconButton(
                    onClick = {
                        groupNameDraft = displayName
                        groupInvestmentDraft = false
                        groupManualAmountDraft = summary.balance.toPlainString()
                        groupSaveInProgress = false
                        groupSaveError = null
                        isEditingGroup = true
                    },
                    modifier = Modifier.size(32.dp),
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_edit_24),
                        contentDescription = "Изменить название группы",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
            if (isExpanded) {
                Spacer(modifier = Modifier.height(8.dp))
                if (accounts.isEmpty()) {
                    Text("Нет счетов в этой категории", style = MaterialTheme.typography.bodySmall)
                } else {
                    accounts.forEach { account ->
                        AccountRow(
                            account = account,
                            onUpdate = onUpdate,
                            onArchive = onArchive,
                        )
                        if (account != accounts.last()) {
                            Spacer(modifier = Modifier.height(6.dp))
                        }
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = onAdd,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("Добавить счёт")
                    }
                }
            }
        }
    }

    if (isEditingGroup) {
        AlertDialog(
            onDismissRequest = {
                if (!groupSaveInProgress) {
                    isEditingGroup = false
                }
            },
            title = { Text("Название группы") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = groupNameDraft,
                        onValueChange = {
                            groupNameDraft = it
                            groupSaveError = null
                        },
                        label = { Text("Название") },
                        singleLine = true,
                        enabled = !groupSaveInProgress,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (canEditManualAmount) {
                        OutlinedTextField(
                            value = groupManualAmountDraft,
                            onValueChange = {
                                groupManualAmountDraft = it.filter { char -> char.isDigit() || char == '.' || char == ',' || char == '-' }
                                groupSaveError = null
                            },
                            label = { Text("Ручная сумма") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                            enabled = !groupSaveInProgress,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = groupInvestmentDraft,
                            onCheckedChange = {
                                groupInvestmentDraft = it
                                groupSaveError = null
                            },
                            enabled = !groupSaveInProgress,
                        )
                        Text("Инвестиция")
                    }
                    groupSaveError?.let { message ->
                        Text(
                            text = message,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (canEditManualAmount) {
                            val cleanName = groupNameDraft.trim()
                            if (cleanName.isBlank()) {
                                groupSaveError = "Введите название группы"
                                return@TextButton
                            }
                            if (groupManualAmountDraft.normalizedBalanceAmount() == null) {
                                groupSaveError = "Введите корректную ручную сумму"
                                return@TextButton
                            }
                            groupSaveInProgress = true
                            groupSaveError = null
                            onCreateManualCategory(cleanName, groupManualAmountDraft, groupInvestmentDraft) { result ->
                                groupSaveInProgress = false
                                when (result) {
                                    LegacyGroupMigrationResult.Success -> isEditingGroup = false
                                    is LegacyGroupMigrationResult.Failure -> groupSaveError = result.message
                                }
                            }
                        } else {
                            when (val action = legacyGroupSaveAction(groupNameDraft, groupInvestmentDraft)) {
                                is LegacyGroupSaveAction.Invalid -> groupSaveError = action.message
                                is LegacyGroupSaveAction.Rename -> {
                                    groupSaveError = null
                                    onRenameGroup(action.name)
                                    isEditingGroup = false
                                }
                                is LegacyGroupSaveAction.MigrateToInvestment -> {
                                    groupSaveInProgress = true
                                    groupSaveError = null
                                    onMigrateGroupToInvestment(action.name) { result ->
                                        groupSaveInProgress = false
                                        when (result) {
                                            LegacyGroupMigrationResult.Success -> isEditingGroup = false
                                            is LegacyGroupMigrationResult.Failure -> groupSaveError = result.message
                                        }
                                    }
                                }
                            }
                        }
                    },
                    enabled = !groupSaveInProgress &&
                        groupNameDraft.isNotBlank() &&
                        (!canEditManualAmount || groupManualAmountDraft.normalizedBalanceAmount() != null),
                ) {
                    Text(if (groupSaveInProgress) "Сохраняем..." else "Сохранить")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { isEditingGroup = false },
                    enabled = !groupSaveInProgress,
                ) {
                    Text("Отмена")
                }
            },
        )
    }

}

private val CURRENCIES = listOf("RUB", "USD", "EUR", "XAU")

private fun String.currencyLabel(): String = when (this) {
    "RUB" -> "₽ RUB"
    "USD" -> "$ USD"
    "EUR" -> "€ EUR"
    "XAU" -> "граммы"
    else -> this
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AssetCategorySheet(
    mode: FinanceMode,
    householdId: String?,
    onDismiss: () -> Unit,
    onCreate: (AssetCategoryCreateRequest) -> Unit,
) {
    var name by rememberSaveable { mutableStateOf("") }
    var currency by rememberSaveable { mutableStateOf("RUB") }
    var manualAmount by rememberSaveable { mutableStateOf("0") }
    var isInvestment by rememberSaveable { mutableStateOf(false) }
    var assetKind by rememberSaveable { mutableStateOf(AssetKind.Bank) }
    var iconKey by rememberSaveable { mutableStateOf(defaultAssetCategoryIconKey(AssetKind.Bank.apiValue)) }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Новая категория активов", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Название") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Text("Тип актива", style = MaterialTheme.typography.labelLarge)
            ChipRow(AssetKind.entries.toList(), assetKind, {
                assetKind = it
                iconKey = defaultAssetCategoryIconKey(it.apiValue)
            }, { it.title }, { it.icon })
            AssetCategoryIconPicker(selectedKey = iconKey, onSelected = { iconKey = it })
            Text("Валюта", style = MaterialTheme.typography.labelLarge)
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(CURRENCIES) { cur ->
                    FilterChip(
                        selected = currency == cur,
                        onClick = { currency = cur },
                        label = { Text(cur.currencyLabel()) },
                    )
                }
            }
            OutlinedTextField(
                value = manualAmount,
                onValueChange = { manualAmount = it.filter { char -> char.isDigit() || char == '.' || char == ',' || char == '-' } },
                label = { Text("Ручная сумма") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = isInvestment, onCheckedChange = { isInvestment = it })
                Text("Инвестиционная категория")
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier
                        .weight(1f)
                        .height(40.dp),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                ) {
                    Text("Отмена", maxLines = 1)
                }
                Button(
                    onClick = {
                        onCreate(
                            AssetCategoryCreateRequest(
                                name = name.trim(),
                                scopeType = "personal",
                                householdId = null,
                                currency = currency,
                                manualAmount = manualAmount.normalizedBalanceAmount() ?: "0",
                                isInvestment = isInvestment,
                                assetType = assetKind.apiValue,
                                iconKey = iconKey.ifBlank { defaultAssetCategoryIconKey(assetKind.apiValue) },
                            ),
                        )
                    },
                    enabled = name.isNotBlank() && manualAmount.normalizedBalanceAmount() != null,
                    modifier = Modifier
                        .weight(1f)
                        .height(40.dp),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                ) {
                    Text("Создать", maxLines = 1)
                }
            }
        }
    }
}

@Composable
private fun AssetCategoryIconPicker(
    selectedKey: String,
    onSelected: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Иконка", style = MaterialTheme.typography.labelLarge)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            items(AssetCategoryIconOptions) { option ->
                val selected = selectedKey == option.key
                IconButton(
                    onClick = { onSelected(option.key) },
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(
                            if (selected) option.tint.copy(alpha = 0.18f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                        ),
                ) {
                    Icon(
                        painter = painterResource(option.icon),
                        contentDescription = option.title,
                        tint = option.tint,
                        modifier = Modifier.size(22.dp),
                    )
                }
            }
        }
    }
}

private fun Modifier.tapOrLongPress(
    onTap: () -> Unit,
    onLongPress: () -> Unit,
    thresholdMillis: Long = 1050L,
): Modifier = pointerInput(onTap, onLongPress, thresholdMillis) {
    detectTapOrLongPress(
        thresholdMillis = thresholdMillis,
        onTap = onTap,
        onLongPress = onLongPress,
    )
}

private suspend fun PointerInputScope.detectTapOrLongPress(
    thresholdMillis: Long,
    onTap: () -> Unit,
    onLongPress: () -> Unit,
) {
    awaitEachGesture {
        awaitFirstDown(requireUnconsumed = false)
        val releasedBeforeThreshold = withTimeoutOrNull(thresholdMillis) {
            waitForUpOrCancellation()
        }
        if (releasedBeforeThreshold != null) {
            onTap()
        } else {
            onLongPress()
            waitForUpOrCancellation()
        }
    }
}

@Composable
private fun AccountRow(
    account: AccountSummary,
    onUpdate: (AccountSummary) -> Unit,
    onArchive: (String) -> Unit,
) {
    var isEditing by rememberSaveable { mutableStateOf(false) }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = account.displayName(),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = account.currentBalance.toMoney().formatMoney(account.currency),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        IconButton(
            onClick = { isEditing = true },
            modifier = Modifier.size(28.dp),
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_edit_24),
                contentDescription = "Изменить",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(16.dp),
            )
        }
        IconButton(
            onClick = { onArchive(account.id) },
            modifier = Modifier.size(28.dp),
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_delete_24),
                contentDescription = "Удалить",
                tint = Color(0xFFE35D4F),
                modifier = Modifier.size(16.dp),
            )
        }
    }

    if (isEditing) {
        AccountEditDialog(
            account = account,
            onDismiss = { isEditing = false },
            onArchive = {
                onArchive(account.id)
                isEditing = false
            },
            onSave = { updatedAccount ->
                onUpdate(updatedAccount)
                isEditing = false
            },
        )
    }
}

@Composable
private fun AccountEditDialog(
    account: AccountSummary,
    onDismiss: () -> Unit,
    onArchive: () -> Unit,
    onSave: (AccountSummary) -> Unit,
) {
    var editName by rememberSaveable(account.id, account.name) { mutableStateOf(account.name) }
    var editBalance by rememberSaveable(account.id, account.currentBalance) { mutableStateOf(account.currentBalance) }
    var editCurrency by rememberSaveable(account.id, account.currency) { mutableStateOf(account.currency) }
    var editIsPaymentAccount by rememberSaveable(account.id, account.isPaymentAccount) {
        mutableStateOf(account.isPaymentAccount)
    }
    val cleanBalance = editBalance.normalizedBalanceAmount()
    val canSave = editName.isNotBlank() && cleanBalance != null

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Редактировать счёт") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = editName,
                    onValueChange = { editName = it },
                    label = { Text("Название") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = editBalance,
                    onValueChange = { editBalance = it },
                    label = { Text("Баланс") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text("Валюта", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(CURRENCIES) { cur ->
                        FilterChip(
                            selected = editCurrency == cur,
                            onClick = { editCurrency = cur },
                            label = { Text(cur.currencyLabel()) },
                            leadingIcon = {
                                if (cur == "XAU") {
                                    Icon(
                                        painter = painterResource(R.drawable.ic_gold_bar_24),
                                        contentDescription = null,
                                        modifier = Modifier.size(16.dp),
                                    )
                                }
                            },
                        )
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked = editIsPaymentAccount,
                        onCheckedChange = { editIsPaymentAccount = it },
                    )
                    Text("Счёт для оплаты")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val cleanName = editName.trim()
                    val normalizedBalance = editBalance.normalizedBalanceAmount()
                    if (cleanName.isNotBlank() && normalizedBalance != null) {
                        onSave(
                            account.copy(
                                name = cleanName,
                                currentBalance = normalizedBalance,
                                currency = editCurrency,
                                isPaymentAccount = editIsPaymentAccount,
                            ),
                        )
                    }
                },
                enabled = canSave,
            ) {
                Text("Сохранить")
            }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = onArchive) {
                    Text("Удалить", color = Color(0xFFE35D4F))
                }
                TextButton(onClick = onDismiss) {
                    Text("Отмена")
                }
            }
        },
    )
}

private fun pluralItems(count: Int): String {
    return when {
        count % 10 == 1 && count % 100 != 11 -> "счёт"
        count % 10 in 2..4 && count % 100 !in 12..14 -> "счёта"
        else -> "счетов"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DatePickerField(
    label: String,
    date: String,
    onDateSelected: (String) -> Unit,
) {
    var showPicker by rememberSaveable { mutableStateOf(false) }
    OutlinedButton(
        onClick = { showPicker = true },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("$label: ${date.displayDateOnly()}")
    }
    if (showPicker) {
        val pickerState = rememberDatePickerState(
            initialSelectedDateMillis = date.dateOnlyMillis() ?: currentDateString().dateOnlyMillis(),
        )
        DatePickerDialog(
            onDismissRequest = { showPicker = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        pickerState.selectedDateMillis?.let { onDateSelected(it.toDateOnlyString()) }
                        showPicker = false
                    },
                ) {
                    Text("OK")
                }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) {
                    Text("Отмена")
                }
            },
        ) {
            DatePicker(state = pickerState)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ReportMonthSwitcher(
    selectedMonth: String,
    onSelected: (String) -> Unit,
) {
    val state = reportMonthSwitcherState(selectedMonth)
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ReportMonthActionButton(
                icon = R.drawable.ic_chevron_left_24,
                contentDescription = "Предыдущий месяц",
                onClick = { onSelected(state.previousMonth) },
            )
            Text(
                text = state.label,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 4.dp)
                    .testTag("report-month-label"),
            )
            ReportMonthActionButton(
                icon = R.drawable.ic_calendar_today_24,
                contentDescription = "Текущий месяц",
                onClick = { onSelected(state.currentMonth) },
            )
            ReportMonthActionButton(
                icon = R.drawable.ic_chevron_right_24,
                contentDescription = "Следующий месяц",
                onClick = { onSelected(state.nextMonth) },
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ReportMonthActionButton(
    @DrawableRes icon: Int,
    contentDescription: String,
    onClick: () -> Unit,
) {
    TooltipBox(
        positionProvider = TooltipDefaults.rememberPlainTooltipPositionProvider(),
        tooltip = { PlainTooltip { Text(contentDescription) } },
        state = rememberTooltipState(),
    ) {
        IconButton(
            onClick = onClick,
            modifier = Modifier
                .size(44.dp)
                .testTag("report-month-action-$contentDescription"),
        ) {
            Icon(
                painter = painterResource(icon),
                contentDescription = contentDescription,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

internal data class ReportMonthSwitcherState(
    val label: String,
    val previousMonth: String,
    val currentMonth: String,
    val nextMonth: String,
)

internal fun reportMonthSwitcherState(
    selectedMonth: String,
    currentMonth: String = currentReportMonth(),
): ReportMonthSwitcherState {
    val month = selectedMonth.toYearMonthOrCurrent()
    return ReportMonthSwitcherState(
        label = month.displayReportMonth(),
        previousMonth = month.minusMonths(1).toString(),
        currentMonth = currentMonth,
        nextMonth = month.plusMonths(1).toString(),
    )
}

@Composable
private fun AnalyticsSummaryCard(view: DashboardView, investmentsTotal: MoneyAmount?) {
    val investmentAmount = investmentsTotal?.amount?.toMoney() ?: BigDecimal.ZERO
    val investmentCurrency = investmentsTotal?.currency ?: view.primaryCurrency
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Аналитика", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            MetricLine("Доходы", view.monthIncome.formatMoney(view.primaryCurrency), Color(0xFF2E7D62))
            MetricLine("Расходы", view.monthExpenses.formatMoney(view.primaryCurrency), Color(0xFFE35D4F))
            MetricLine("Инвестиции", investmentAmount.formatMoney(investmentCurrency), Color(0xFF5B6EE1))
        }
    }
}

@Composable
private fun InvestmentsCard(
    total: MoneyAmount?,
    byCurrency: List<MoneyAmount>,
    fallbackCurrency: String,
) {
    val resolvedTotal = total ?: byCurrency.firstOrNull() ?: MoneyAmount(fallbackCurrency, "0")
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(R.drawable.ic_chart_24, Color(0xFF227C9D), size = 36)
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("Инвестиции", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(resolvedTotal.amount.toMoney().formatMoney(resolvedTotal.currency), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                }
            }
            byCurrency.takeIf { it.isNotEmpty() }?.forEach { item ->
                MetricLine(item.currency, item.amount.toMoney().formatMoney(item.currency), Color(0xFF227C9D))
            }
        }
    }
}

@Composable
private fun CategoryBreakdownCard(categories: List<CategorySpend>) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Категории", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (categories.isEmpty()) {
                Text("Нет расходов для разбивки", style = MaterialTheme.typography.bodySmall)
            } else {
                categories.forEach { category ->
                    CategorySpendRow(category)
                }
            }
        }
    }
}

@Composable
private fun CategoryManagementCard(
    categories: List<CategorySummary>,
    isAuthenticated: Boolean,
    onAddCategory: (String, QuickEntryType, FinanceMode) -> Unit,
    onUpdateCategory: (CategorySummary, String) -> Unit,
    onArchiveCategory: (String) -> Unit,
) {
    var newCategoryName by rememberSaveable { mutableStateOf("") }
    val visibleCategories = categories
        .filter { it.status == "active" && it.type == "expense" && it.scope != "household" }
        .sortedBy { it.displayName() }

    ElevatedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("category-management-card"),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(R.drawable.ic_category_24, Color(0xFF6D5BD0), size = 36)
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("Категории расходов", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("Добавление, список и быстрые правки расходов", style = MaterialTheme.typography.bodySmall)
                }
            }

            OutlinedTextField(
                value = newCategoryName,
                onValueChange = { newCategoryName = it },
                label = { Text("Название категории") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = {
                    onAddCategory(newCategoryName.trim(), QuickEntryType.Expense, FinanceMode.Personal)
                    newCategoryName = ""
                },
                enabled = isAuthenticated && newCategoryName.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Добавить категорию")
            }

            if (visibleCategories.isEmpty()) {
                Text("Категорий расходов пока нет", style = MaterialTheme.typography.bodySmall)
            } else {
                visibleCategories.forEach { category ->
                    CategoryManagementRow(category, onUpdateCategory, onArchiveCategory)
                }
            }
        }
    }
}

@Composable
private fun CategoryManagementRow(
    category: CategorySummary,
    onUpdateCategory: (CategorySummary, String) -> Unit,
    onArchiveCategory: (String) -> Unit,
) {
    var isEditing by rememberSaveable { mutableStateOf(false) }
    var editName by rememberSaveable { mutableStateOf(category.displayName()) }

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBubble(category.icon(), category.colorOrFallback(), size = 34)
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = category.displayName(),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text("Расход", style = MaterialTheme.typography.labelSmall)
            }
            IconButton(onClick = {
                if (isEditing) editName = category.displayName()
                isEditing = !isEditing
            }) {
                Icon(
                    painter = painterResource(if (isEditing) R.drawable.ic_delete_24 else R.drawable.ic_edit_24),
                    contentDescription = if (isEditing) "Отмена" else "Изменить",
                    modifier = Modifier.size(18.dp),
                )
            }
        }
        if (isEditing) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = editName,
                    onValueChange = { editName = it },
                    label = { Text("Название") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = {
                        if (editName.isNotBlank()) {
                            onUpdateCategory(category, editName.trim())
                            isEditing = false
                        }
                    },
                    enabled = editName.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Сохранить")
                }
                IconButton(
                    onClick = {
                        onArchiveCategory(category.id)
                        isEditing = false
                    },
                    modifier = Modifier.size(40.dp),
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_delete_24),
                        contentDescription = "Удалить",
                        tint = Color(0xFFE35D4F),
                    )
                }
            }
        }
    }
}

@Composable
private fun CapitalBreakdownCard(summaries: List<AssetSummary>) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Структура капитала", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            summaries.filter { it.count > 0 }.forEach { summary ->
                MetricLine(summary.kind.title, summary.balance.formatMoney(summary.currency), summary.kind.tint)
            }
        }
    }
}

@Composable
private fun CategorySpendRow(category: CategorySpend) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconBubble(category.icon, category.color, size = 34)
        Spacer(modifier = Modifier.width(10.dp))
        Text(
            text = category.name,
            modifier = Modifier.weight(1f),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(category.amount.formatMoney(category.currency), fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun MetricLine(label: String, value: String, color: Color) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(color),
        )
        Spacer(modifier = Modifier.width(10.dp))
        Text(label, modifier = Modifier.weight(1f))
        Text(value, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun IconBubble(
    @DrawableRes icon: Int,
    color: Color,
    size: Int = 40,
) {
    Box(
        modifier = Modifier
            .size(size.dp)
            .clip(CircleShape)
            .background(color.copy(alpha = 0.14f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            tint = color,
            modifier = Modifier.size((size * 0.55f).dp),
        )
    }
}

@Composable
private fun EmptyState(text: String) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = text,
            modifier = Modifier.padding(18.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
private fun AddAccountSheet(
    kind: AssetKind,
    initialMode: FinanceMode,
    hasHousehold: Boolean,
    onDismiss: () -> Unit,
    onSubmit: (String, String, String, FinanceMode, Boolean) -> Unit,
) {
    var name by rememberSaveable { mutableStateOf("") }
    var balance by rememberSaveable { mutableStateOf("") }
    var currency by rememberSaveable { mutableStateOf("RUB") }
    var isPaymentAccount by rememberSaveable { mutableStateOf(true) }
    val sheetScope = rememberCoroutineScope()
    val scrollState = rememberScrollState()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val nameBringIntoView = remember { BringIntoViewRequester() }
    val balanceBringIntoView = remember { BringIntoViewRequester() }
    val centerNudgePx = with(LocalDensity.current) { 168.dp.roundToPx() }

    fun bringFocusedFieldIntoView(requester: BringIntoViewRequester) {
        sheetScope.launch {
            requester.bringIntoView()
            delay(180)
            requester.bringIntoView()
            delay(220)
            requester.bringIntoView()
            scrollState.animateScrollTo((scrollState.value + centerNudgePx).coerceAtMost(scrollState.maxValue))
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(scrollState)
                .imePadding()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp)
                .padding(bottom = 48.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Spacer(modifier = Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(kind.icon, kind.tint, size = 36)
                Spacer(modifier = Modifier.width(10.dp))
                Text("Новый ${kind.title}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            }
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Название") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .bringIntoViewRequester(nameBringIntoView)
                    .onFocusChanged {
                        if (it.isFocused) {
                            bringFocusedFieldIntoView(nameBringIntoView)
                        }
                    },
            )
            OutlinedTextField(
                value = balance,
                onValueChange = { balance = it },
                label = { Text("Начальный баланс") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .bringIntoViewRequester(balanceBringIntoView)
                    .onFocusChanged {
                        if (it.isFocused) {
                            bringFocusedFieldIntoView(balanceBringIntoView)
                        }
                    },
            )
            Text("Валюта", style = MaterialTheme.typography.labelLarge)
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(CURRENCIES) { cur ->
                    FilterChip(
                        selected = currency == cur,
                        onClick = { currency = cur },
                        label = { Text(cur.currencyLabel()) },
                        leadingIcon = {
                            if (cur == "XAU") {
                                Icon(
                                    painter = painterResource(R.drawable.ic_gold_bar_24),
                                    contentDescription = null,
                                    modifier = Modifier.size(16.dp),
                                )
                            }
                        },
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = isPaymentAccount,
                    onCheckedChange = { isPaymentAccount = it },
                )
                Text("Счёт для оплаты")
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Отмена")
                }
                Button(
                    onClick = {
                        val cleanBalance = balance.trim().ifBlank { "0" }
                        onSubmit(
                            name.trim().ifBlank { kind.title },
                            cleanBalance,
                            currency,
                            FinanceMode.Personal,
                            isPaymentAccount,
                        )
                    },
                    enabled = name.isNotBlank() || balance.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Создать")
                }
            }
            Spacer(modifier = Modifier.height(180.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuickAddSheet(
    sheetKey: Int,
    dashboard: FinanceDashboard?,
    selectedMode: FinanceMode,
    errorMessage: String?,
    onDismiss: () -> Unit,
    onSubmit: (QuickAddDraft) -> Unit,
) {
    var amount by rememberSaveable(sheetKey) { mutableStateOf("") }
    var type by rememberSaveable(sheetKey) { mutableStateOf(QuickEntryType.Expense) }
    var accountId by rememberSaveable(sheetKey) { mutableStateOf("") }
    var destinationAccountId by rememberSaveable(sheetKey) { mutableStateOf("") }
    var categoryId by rememberSaveable(sheetKey) { mutableStateOf("") }
    var assetKind by rememberSaveable(sheetKey) { mutableStateOf(AssetKind.Bank) }
    var transactionDate by rememberSaveable(sheetKey) { mutableStateOf(currentDateString()) }
    val visibility = FinanceMode.Personal
    val accounts = dashboard?.accounts.orEmpty()
    val scopedAccounts = accounts
        .filter { it.status == "active" && it.id.isNotBlank() }
        .filter { it.matchesWritableMode(visibility) }
    val operationAccounts = accounts.writableOperationAccountsFor(type, visibility)
    val categories = dashboard?.categories.orEmpty()
        .filter { it.type == type.apiValue && it.status == "active" }
        .filter { it.matchesWritableMode(visibility) }
    val selectableAccounts = if (type == QuickEntryType.Transfer) scopedAccounts else operationAccounts
    val selectedAccountId = resolvedSelectionId(accountId, selectableAccounts.map { it.id })
    val selectedCategoryId = resolvedSelectionId(categoryId, categories.map { it.id })
    val selectedSource = scopedAccounts.firstOrNull { it.id == selectedAccountId }
    val compatibleDestinations = scopedAccounts.compatibleTransferDestinations(selectedSource)
    val selectedDestinationId = resolvedSelectionId(destinationAccountId, compatibleDestinations.map { it.id })
    val selectedDestination = compatibleDestinations.firstOrNull { it.id == selectedDestinationId }
    LaunchedEffect(type, selectableAccounts.map { it.id }) {
        accountId = selectedAccountId
    }
    LaunchedEffect(type, categories.map { it.id }) {
        categoryId = selectedCategoryId
    }
    LaunchedEffect(type, selectedAccountId, compatibleDestinations.map { it.id }) {
        destinationAccountId = selectedDestinationId
    }
    val transferPreflight = if (type == QuickEntryType.Transfer) {
        transferPairValidationMessage(selectedSource, selectedDestination)
            ?: "Перевод будет сохранён нейтрально: между счетами одного scope и одной валюты."
    } else {
        null
    }
    val submitLabel = when (type) {
        QuickEntryType.Expense -> "Сохранить расход"
        QuickEntryType.Income -> "Сохранить доход"
        QuickEntryType.Transfer -> "Сохранить перевод"
        QuickEntryType.Asset -> "Перейти к активам"
    }
    val disabledReason = quickAddDisabledReason(
        type = type,
        amount = amount,
        visibility = visibility,
        accounts = if (type == QuickEntryType.Transfer) scopedAccounts else operationAccounts,
        categories = categories,
        transferValidation = if (type == QuickEntryType.Transfer) transferPairValidationMessage(selectedSource, selectedDestination) else null,
    )

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp)
                .testTag("quick-add-sheet"),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Быстрое добавление", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = amount,
                onValueChange = { amount = it.filter { char -> char.isDigit() || char == '.' || char == ',' } },
                label = { Text("Сумма") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            ChipRow(quickAddEntryTypes(), type, { nextType ->
                type = nextType
                categoryId = ""
                destinationAccountId = ""
            }, { it.title }, { it.icon() })
            if (!errorMessage.isNullOrBlank()) {
                Text(
                    text = errorMessage,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("quick-add-error"),
                )
            }
            if (type == QuickEntryType.Asset) {
                ChipRow(AssetKind.entries.toList(), assetKind, { assetKind = it }, { it.title }, { it.icon })
            } else {
                AccountPicker(
                    title = if (type == QuickEntryType.Transfer) "Со счета" else "Счет",
                    accounts = if (type == QuickEntryType.Transfer) scopedAccounts else operationAccounts,
                    selectedId = selectedAccountId,
                    onSelected = { accountId = it },
                )
                if (type == QuickEntryType.Transfer) {
                    AccountPicker(
                        title = "На счет",
                        accounts = compatibleDestinations,
                        selectedId = selectedDestinationId,
                        onSelected = { destinationAccountId = it },
                    )
                    transferPreflight?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                if (type != QuickEntryType.Transfer && categories.isNotEmpty()) {
                    CategoryPicker(
                        categories = categories,
                        selectedId = selectedCategoryId,
                        onSelected = { categoryId = it },
                    )
                }
            }
            if (type != QuickEntryType.Asset) {
                DatePickerField(
                    label = "Дата операции",
                    date = transactionDate,
                    onDateSelected = { transactionDate = it },
                )
            }
            disabledReason?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Отмена")
                }
                Button(
                    onClick = {
                        onSubmit(
                            QuickAddDraft(
                                amount = amount,
                                type = type,
                                accountId = selectedAccountId,
                                destinationAccountId = selectedDestinationId,
                                categoryId = selectedCategoryId,
                                assetKind = assetKind,
                                visibility = FinanceMode.Personal,
                                transactionDate = transactionDate,
                            ),
                        )
                    },
                    enabled = disabledReason == null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(submitLabel)
                }
            }
        }
    }
}

@Composable
private fun <T> ChipRow(
    values: List<T>,
    selected: T?,
    onSelected: (T) -> Unit,
    title: (T) -> String,
    icon: (T) -> Int,
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(values) { value ->
            FilterChip(
                selected = selected == value,
                onClick = { onSelected(value) },
                label = { Text(title(value)) },
                leadingIcon = {
                    Icon(
                            painter = painterResource(icon(value)),
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                },
            )
        }
    }
}

internal fun writableFinanceModes(hasHousehold: Boolean): List<FinanceMode> {
    return listOf(FinanceMode.Personal)
}

internal fun quickAddEntryTypes(): List<QuickEntryType> {
    return listOf(QuickEntryType.Expense, QuickEntryType.Income, QuickEntryType.Transfer)
}

internal fun quickAddDisabledReason(
    type: QuickEntryType,
    amount: String,
    visibility: FinanceMode?,
    accounts: List<AccountSummary>,
    categories: List<CategorySummary>,
    transferValidation: String?,
): String? {
    if (amount.normalizedAmount() == null) {
        return "Укажите сумму перед сохранением."
    }
    if (visibility == null || visibility == FinanceMode.Overview) {
        return "Операцию можно сохранить только в личных финансах."
    }
    if (type == QuickEntryType.Asset) {
        return "Актив создаётся в разделе «Активы», где можно выбрать название, валюту и доступ."
    }
    if (accounts.isEmpty()) {
        return "Нет активного личного счёта. Создайте счёт в «Активы»."
    }
    if (type == QuickEntryType.Transfer) {
        return transferValidation
    }
    if (categories.isEmpty()) {
        return "Нет категории для ${type.title.lowercase(Locale("ru", "RU"))}. Создайте её в «Категории расходов»."
    }
    return null
}

private fun List<AccountSummary>.compatibleTransferDestinations(source: AccountSummary?): List<AccountSummary> {
    if (source == null) return emptyList()
    return filter { candidate ->
        candidate.id != source.id &&
            candidate.currency == source.currency &&
            candidate.ownershipType == source.ownershipType &&
            (
                source.ownershipType != "shared" ||
                    candidate.householdId.orEmpty() == source.householdId.orEmpty()
                )
    }
}

internal fun List<AccountSummary>.operationAccountsFor(type: QuickEntryType): List<AccountSummary> {
    val activeAccounts = filter { it.status == "active" && it.id.isNotBlank() }
    return if (type == QuickEntryType.Expense) {
        activeAccounts.filter { it.isPaymentAccount }
    } else {
        activeAccounts
    }
}

internal fun List<AccountSummary>.writableOperationAccountsFor(
    type: QuickEntryType,
    visibility: FinanceMode?,
): List<AccountSummary> {
    if (visibility == null) return emptyList()
    return filter { it.matchesWritableMode(visibility) }
        .operationAccountsFor(type)
}

internal fun currentDateString(): String = LocalDate.now().toString()

internal fun currentReportMonth(): String = YearMonth.now().toString()

internal fun String.reportMonthBoundary(): ReportMonthBoundary {
    val month = toYearMonthOrCurrent()
    return ReportMonthBoundary(
        startDate = month.atDay(1).toString(),
        endDate = month.atEndOfMonth().toString(),
    )
}

internal fun String.isDateOnly(): Boolean {
    return runCatching { LocalDate.parse(this) }.isSuccess
}

private fun String.toYearMonthOrCurrent(): YearMonth {
    return runCatching { YearMonth.parse(this) }.getOrDefault(YearMonth.now())
}

private fun String.dateOnlyMillis(): Long? {
    return runCatching {
        LocalDate.parse(this).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
    }.getOrNull()
}

private fun Long.toDateOnlyString(): String {
    return Instant.ofEpochMilli(this).atZone(ZoneOffset.UTC).toLocalDate().toString()
}

private fun String.displayDateOnly(): String {
    val date = runCatching { LocalDate.parse(this) }.getOrNull() ?: return this
    return date.format(java.time.format.DateTimeFormatter.ofPattern("dd.MM.yyyy", Locale("ru", "RU")))
}

private fun YearMonth.displayReportMonth(): String {
    return atDay(1).format(java.time.format.DateTimeFormatter.ofPattern("LLLL yyyy", Locale("ru", "RU")))
        .replaceFirstChar { it.titlecase(Locale("ru", "RU")) }
}

@Composable
private fun AccountPicker(
    title: String,
    accounts: List<AccountSummary>,
    selectedId: String,
    onSelected: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge)
        if (accounts.isEmpty()) {
            Text("Нет совместимых личных счетов.", style = MaterialTheme.typography.bodySmall)
        } else {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(accounts) { account ->
                    FilterChip(
                        selected = selectedId == account.id,
                        onClick = { onSelected(account.id) },
                        label = { Text(account.displayName()) },
                        leadingIcon = {
                            Icon(
                                painter = painterResource(account.assetKind().icon),
                                contentDescription = null,
                                modifier = Modifier.size(18.dp),
                            )
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun CategoryPicker(
    categories: List<CategorySummary>,
    selectedId: String,
    onSelected: (String) -> Unit,
) {
    var showPicker by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    val selected = categories.firstOrNull { it.id == selectedId }
    val filtered = categories.filterCategories(query)
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Категория", style = MaterialTheme.typography.labelLarge)
        if (categories.isEmpty()) {
            Text("Нет подходящей категории. Создайте её в разделе «Категории расходов».", style = MaterialTheme.typography.bodySmall)
        } else {
            OutlinedButton(
                onClick = { showPicker = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("category-picker-button"),
            ) {
                Icon(
                    painter = painterResource(selected?.icon() ?: R.drawable.ic_category_24),
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(selected?.displayName() ?: "Выбрать категорию")
            }
        }
    }
    if (showPicker) {
        AlertDialog(
            modifier = Modifier.testTag("category-picker-dialog"),
            onDismissRequest = {
                query = ""
                showPicker = false
            },
            title = { Text("Выберите категорию") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it },
                        label = { Text("Поиск") },
                        singleLine = true,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("category-search"),
                    )
                    if (filtered.isEmpty()) {
                        Text("Ничего не найдено", style = MaterialTheme.typography.bodyMedium)
                    } else {
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 360.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            items(filtered, key = { it.id }) { category ->
                                OutlinedButton(
                                    onClick = {
                                        onSelected(category.id)
                                        query = ""
                                        showPicker = false
                                    },
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .testTag("category-option-${category.id}"),
                                ) {
                                    Icon(
                                        painter = painterResource(category.icon()),
                                        contentDescription = null,
                                        modifier = Modifier.size(18.dp),
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(category.displayName(), modifier = Modifier.weight(1f))
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    query = ""
                    showPicker = false
                }) {
                    Text("Закрыть")
                }
            },
        )
    }
}

internal fun resolvedSelectionId(selectedId: String, availableIds: List<String>): String =
    selectedId.takeIf { it in availableIds } ?: availableIds.firstOrNull().orEmpty()

internal fun List<CategorySummary>.filterCategories(query: String): List<CategorySummary> {
    val normalizedQuery = query.trim().lowercase(Locale.getDefault())
    return asSequence()
        .filter {
            normalizedQuery.isBlank() ||
                it.displayName().lowercase(Locale.getDefault()).contains(normalizedQuery)
        }
        .sortedBy { it.displayName().lowercase(Locale.getDefault()) }
        .toList()
}

data class SyncUiState(
    val pendingCount: Int = 0,
    val failedCount: Int = 0,
    val isSyncing: Boolean = false,
    val savedOffline: Boolean = false,
)

enum class SyncAttentionType {
    Pending,
    Offline,
    Syncing,
    Failed,
}

data class SyncAttention(
    val type: SyncAttentionType,
    val label: String,
    val actionDescription: String,
)

internal fun syncAttention(state: SyncUiState): SyncAttention? {
    return when {
        state.isSyncing -> SyncAttention(
            type = SyncAttentionType.Syncing,
            label = "Синхронизируем",
            actionDescription = "Синхронизация выполняется",
        )
        state.failedCount > 0 -> SyncAttention(
            type = SyncAttentionType.Failed,
            label = "Синхронизация требует внимания",
            actionDescription = "Повторить синхронизацию",
        )
        state.pendingCount > 0 && state.savedOffline -> SyncAttention(
            type = SyncAttentionType.Offline,
            label = "Сохранено на устройстве: ${state.pendingCount}",
            actionDescription = "Синхронизировать сохраненное на устройстве",
        )
        state.pendingCount > 0 -> SyncAttention(
            type = SyncAttentionType.Pending,
            label = "Ожидает синхронизации: ${state.pendingCount}",
            actionDescription = "Синхронизировать ожидающие изменения",
        )
        else -> null
    }
}

internal fun syncIssueEntityLabel(entityType: String): String = when (entityType) {
    SyncManager.ENTITY_TRANSACTIONS -> "Операция"
    SyncManager.ENTITY_ACCOUNTS -> "Актив"
    SyncManager.ENTITY_CATEGORIES -> "Категория"
    SyncManager.ENTITY_ASSET_CATEGORIES -> "Категория активов"
    SyncManager.ENTITY_PLANNING_PLANS -> "План"
    SyncManager.ENTITY_PLANNING_INCOME_SOURCES -> "Доход плана"
    SyncManager.ENTITY_PLANNING_ALLOCATIONS -> "Распределение плана"
    else -> "Изменение"
}

internal fun syncIssueOperationLabel(operation: String): String = when (operation) {
    SyncManager.OPERATION_CREATE -> "Создание"
    SyncManager.OPERATION_UPDATE -> "Изменение"
    SyncManager.OPERATION_ARCHIVE -> "Архивация"
    SyncManager.OPERATION_RESTORE -> "Восстановление"
    SyncManager.OPERATION_DELETE -> "Удаление"
    else -> "Синхронизация"
}

internal fun syncIssueStatusLabel(status: String): String = when (status) {
    SyncManager.MUTATION_STATUS_FAILED -> "Не удалось отправить"
    SyncManager.MUTATION_STATUS_REJECTED -> "Отклонено сервером"
    else -> "Требует внимания"
}

internal fun syncIssueSafeError(lastError: String?): String {
    val normalized = lastError
        ?.replace(Regex("\\s+"), " ")
        ?.trim()
        .orEmpty()
    if (normalized.isBlank()) return "Причина не указана."
    val lower = normalized.lowercase(Locale.ROOT)
    val looksLikePayload = listOf("{", "}", "[", "]", "payload", "amount", "balance", "note")
        .any { marker -> lower.contains(marker) }
    if (looksLikePayload) {
        return "Подробности скрыты. Проверьте данные изменения и повторите синхронизацию."
    }
    return normalized.take(160)
}

internal fun syncIssueTimestampLabel(updatedAtEpochMillis: Long, createdAtEpochMillis: Long): String {
    val timestamp = updatedAtEpochMillis.takeIf { it > 0 } ?: createdAtEpochMillis
    return "Обновлено: ${Instant.ofEpochMilli(timestamp)}"
}

data class FinanceUiState(
    val session: SessionStatus? = null,
    val dashboard: FinanceDashboard? = null,
    val isLoading: Boolean = false,
    val message: String = "Готово",
)

private data class ScreenshotAggregateDraftUi(
    val candidate: CategoryAggregateCandidate,
    val selectedCategoryId: String,
    val include: Boolean,
) {
    val key: String = candidate.idempotencyKey
}

private fun aggregateMappingContext(session: SessionStatus?): String {
    return listOfNotNull(
        session?.householdId?.takeIf { it.isNotBlank() }?.let { "household:$it" },
        session?.displayName?.takeIf { it.isNotBlank() }?.let { "user:$it" },
    ).joinToString("|").ifBlank { "local" }
}

internal suspend fun restoredFinanceUiState(apiClient: FinanceApiClient): FinanceUiState {
    return when (val sessionResult = apiClient.sessionStatus()) {
        is ApiResult.Success -> {
            if (!sessionResult.value.isAuthenticated) {
                FinanceUiState(
                    session = sessionResult.value,
                    message = "Войдите, чтобы увидеть финансы",
                )
            } else {
                val monthBoundary = currentReportMonth().reportMonthBoundary()
                when (val dashboardResult = apiClient.dashboard(monthBoundary.startDate, monthBoundary.endDate)) {
                    is ApiResult.Success -> FinanceUiState(
                        session = dashboardResult.value.session,
                        dashboard = dashboardResult.value,
                        message = "Данные обновлены",
                    )
                    is ApiResult.Failure -> {
                        if (dashboardResult.isAuthenticationFailure()) {
                            FinanceUiState(message = "Войдите, чтобы увидеть финансы")
                        } else {
                            FinanceUiState(
                                session = sessionResult.value,
                                message = dashboardResult.userFacingMessage(),
                            )
                        }
                    }
                }
            }
        }
        is ApiResult.Failure -> FinanceUiState(message = "Войдите, чтобы увидеть финансы")
    }
}

data class SectionCard(
    val title: String,
    val body: String,
    val status: String,
)

data class DashboardView(
    val scopeTitle: String,
    val primaryCurrency: String,
    val capital: BigDecimal,
    val monthIncome: BigDecimal,
    val monthExpenses: BigDecimal,
    val transferTotal: BigDecimal,
    val accountCount: Int,
    val operationCount: Int,
    val assetSummaries: List<AssetSummary>,
    val topCategories: List<CategorySpend>,
    val recentTransactions: List<TransactionSummary>,
)

data class AssetSummary(
    val kind: AssetKind,
    val balance: BigDecimal,
    val currency: String,
    val count: Int,
)

data class AssetCategoryUiRow(
    val category: AssetCategory,
    val totalAmount: String,
    val manualAmount: String,
    val accountsTotal: String,
    val linkedAccountCount: Int?,
    val currency: String,
    val scopeTitle: String,
)

data class CategorySpend(
    val name: String,
    val amount: BigDecimal,
    val currency: String,
    val color: Color,
    @DrawableRes val icon: Int,
)

data class ReportMonthBoundary(
    val startDate: String,
    val endDate: String,
)

data class QuickAddDraft(
    val amount: String,
    val type: QuickEntryType,
    val accountId: String,
    val destinationAccountId: String,
    val categoryId: String,
    val assetKind: AssetKind,
    val visibility: FinanceMode,
    val transactionDate: String = currentDateString(),
)

private data class ManualTransactionCreate(
    val transactionType: String,
    val amount: String,
    val currency: String,
    val accountId: String,
    val categoryId: String?,
    val counterpartyAccountId: String?,
    val transactionDate: String,
    val note: String?,
)

private sealed interface QuickAddSubmitResult {
    data object Success : QuickAddSubmitResult

    data class Failure(
        val failure: ApiResult.Failure,
        val offlineDraft: ManualTransactionCreate?,
    ) : QuickAddSubmitResult
}

data class AddAccountState(
    val kind: AssetKind,
    val mode: FinanceMode,
    val assetCategoryId: String? = null,
)

enum class FinanceMode(val title: String) {
    Personal("Personal"),
    Shared("Legacy shared"),
    Overview("Legacy overview"),
}

enum class QuickEntryType(
    val title: String,
    val apiValue: String,
) {
    Expense("Расход", "expense"),
    Income("Доход", "income"),
    Transfer("Перевод", "transfer"),
    Asset("Актив", "asset"),
}

enum class AssetKind(
    val title: String,
    val apiValue: String,
    @DrawableRes val icon: Int,
    val tint: Color,
) {
    Card("Карта", "card", R.drawable.ic_card_24, Color(0xFF4267D5)),
    Bank("Банк", "bank", R.drawable.ic_bank_24, Color(0xFF256B5F)),
    Cash("Наличные", "cash", R.drawable.ic_cash_24, Color(0xFF9A6A24)),
    Deposit("Вклад", "deposit", R.drawable.ic_savings_24, Color(0xFF6D5BD0)),
    Brokerage("Брокер", "brokerage", R.drawable.ic_chart_24, Color(0xFF227C9D)),
    Metal("Металл", "metal", R.drawable.ic_gold_bar_24, Color(0xFF8A6A12)),
}

fun sectionCards(section: AppSection, dashboard: FinanceDashboard?): List<SectionCard> {
    val view = dashboard.viewFor(FinanceMode.Personal)
    return when (section) {
        AppSection.Home -> listOf(
            SectionCard("Капитал", view.capital.formatMoney(view.primaryCurrency), "${view.accountCount} активов"),
            SectionCard("Расходы месяца", view.monthExpenses.formatMoney(view.primaryCurrency), "переводы отдельно"),
        )
        AppSection.Operations -> dashboard?.transactions.orEmpty().sortedNewestFirst().map {
            SectionCard(it.displayDescription(), it.signedAmount(), it.displayDate())
        }
        AppSection.Assets -> view.assetSummaries.map {
            SectionCard(it.kind.title, it.balance.formatMoney(it.currency), "${it.count} шт.")
        }
        AppSection.Categories -> dashboard?.categories.orEmpty()
            .filter { it.type == "expense" && it.scope != "household" }
            .map {
            SectionCard(it.displayName(), "Расход", "Категория расходов")
        }.ifEmpty {
            listOf(SectionCard("Категории расходов", "Нет категорий", "пусто"))
        }
        AppSection.Analytics -> listOf(
            SectionCard("План месяца", "Личные финансы", "явный вход Android"),
        ) + view.topCategories.map {
            SectionCard(it.name, it.amount.formatMoney(it.currency), "категория")
        }.ifEmpty {
            listOf(SectionCard("Категории", "Нет расходов", "пусто"))
        }
    }
}

fun FinanceDashboard?.viewFor(mode: FinanceMode): DashboardView {
    val dashboard = this
    val accounts = dashboard?.accounts.orEmpty()
        .filter { it.status == "active" }
        .filterByMode(mode)
    val accountIds = accounts.map { it.id }.toSet()
    val transactions = dashboard.transactionsFor(mode, accountIds)
    val currency = accounts.firstOrNull()?.currency
        ?: transactions.firstOrNull()?.currency
        ?: dashboard?.totals?.firstOrNull()?.currency
        ?: "USD"
    val expenses = transactions
        .filter { it.type == "expense" }
        .sumMoney()
    val income = transactions
        .filter { it.type == "income" }
        .sumMoney()
    val transferTotal = transactions
        .filter { it.type == "transfer" }
        .sumMoney()

    return DashboardView(
        scopeTitle = mode.scopeTitle(),
        primaryCurrency = currency,
        capital = accounts.fold(BigDecimal.ZERO) { total, account -> total + account.currentBalance.toMoney() },
        monthIncome = income,
        monthExpenses = expenses,
        transferTotal = transferTotal,
        accountCount = accounts.size,
        operationCount = transactions.size,
        assetSummaries = assetSummaries(accounts),
        topCategories = topCategories(transactions, dashboard?.categories.orEmpty(), currency),
        recentTransactions = transactions.sortedNewestFirst().take(6),
    )
}

private fun FinanceDashboard?.transactionsFor(
    mode: FinanceMode,
    scopedAccountIds: Set<String>? = null,
): List<TransactionSummary> {
    val dashboard = this ?: return emptyList()
    val accountIds = scopedAccountIds ?: dashboard.accounts
        .filter { it.status == "active" }
        .filterByMode(mode)
        .map { it.id }
        .toSet()
    return dashboard.transactions.filter { tx -> tx.matchesMode(accountIds) }
}

private fun assetSummaries(accounts: List<AccountSummary>): List<AssetSummary> {
    val currency = accounts.firstOrNull()?.currency ?: "USD"
    return AssetKind.entries.toList().map { kind ->
        val matching = accounts.filter { it.assetKind() == kind }
        AssetSummary(
            kind = kind,
            balance = matching.fold(BigDecimal.ZERO) { total, account -> total + account.currentBalance.toMoney() },
            currency = matching.firstOrNull()?.currency ?: currency,
            count = matching.size,
        )
    }
}

private fun FinanceDashboard.withUpdatedAssetCategory(category: AssetCategory): FinanceDashboard {
    val updatedCategories = if (assetCategories.any { it.id == category.id }) {
        assetCategories.map { existing -> if (existing.id == category.id) category else existing }
    } else {
        assetCategories + category
    }
    val updatedGroups = assetCategoryGroups.map { group ->
        if (group.assetCategoryId == category.id) {
            group.copy(
                name = category.name,
                scopeType = category.scopeType,
                householdId = category.householdId,
                currency = category.currency,
                manualAmount = category.manualAmount,
                isInvestment = category.isInvestment,
                assetType = category.assetType,
                iconKey = category.iconKey,
            )
        } else {
            group
        }
    }
    return copy(
        assetCategories = updatedCategories,
        assetCategoryGroups = updatedGroups,
    )
}

private fun FinanceDashboard?.assetCategoryRows(mode: FinanceMode): List<AssetCategoryUiRow> {
    val dashboard = this ?: return emptyList()
    val categories = dashboard.assetCategories
        .filter { it.recordStatus == "active" }
        .filter { it.matchesMode(mode) }
    val byId = categories.associateBy { it.id }
    val rowsFromGroups = dashboard.assetCategoryGroups
        .filter { it.assetCategoryId.isNotBlank() }
        .filter { it.matchesMode(mode) }
        .map { group ->
            val category = byId[group.assetCategoryId] ?: group.toAssetCategory()
            AssetCategoryUiRow(
                category = category,
                totalAmount = group.totalAmount,
                manualAmount = group.manualAmount,
                accountsTotal = group.accountsTotal,
                linkedAccountCount = group.accountCount,
                currency = group.currency,
                scopeTitle = group.scopeType.assetScopeTitle(),
            )
        }
    val groupedIds = rowsFromGroups.map { it.category.id }.toSet()
    val emptyCategoryRows = categories
        .filter { it.id !in groupedIds }
        .map { category ->
            AssetCategoryUiRow(
                category = category,
                totalAmount = category.manualAmount,
                manualAmount = category.manualAmount,
                accountsTotal = "0",
                linkedAccountCount = null,
                currency = category.currency,
                scopeTitle = category.scopeType.assetScopeTitle(),
            )
        }
    return (rowsFromGroups + emptyCategoryRows).sortedWith(compareBy<AssetCategoryUiRow> { it.scopeTitle }.thenBy { it.category.name })
}

private fun List<AssetCategoryUiRow>.applyAssetCategoryOrder(savedOrder: List<String>): List<AssetCategoryUiRow> {
    val activeIds = map { it.category.id }.toSet()
    val savedIndex = savedOrder
        .filter { it in activeIds }
        .distinct()
        .withIndex()
        .associate { it.value to it.index }
    return sortedWith(
        compareBy<AssetCategoryUiRow> { savedIndex[it.category.id] ?: Int.MAX_VALUE }
            .thenBy { it.scopeTitle }
            .thenBy { it.category.name }
            .thenBy { it.category.id },
    )
}

private fun loadAssetCategoryOrder(context: Context, mode: FinanceMode): List<String> {
    return context
        .getSharedPreferences(ASSET_CATEGORY_ORDER_PREFS, Context.MODE_PRIVATE)
        .getString(assetCategoryOrderKey(mode), null)
        ?.split('|')
        ?.map { it.trim() }
        ?.filter { it.isNotBlank() }
        ?: emptyList()
}

private fun saveAssetCategoryOrder(context: Context, mode: FinanceMode, ids: List<String>) {
    context
        .getSharedPreferences(ASSET_CATEGORY_ORDER_PREFS, Context.MODE_PRIVATE)
        .edit()
        .putString(assetCategoryOrderKey(mode), ids.filter { it.isNotBlank() }.distinct().joinToString("|"))
        .apply()
}

private fun assetCategoryOrderKey(mode: FinanceMode): String {
    return "asset_category_order_${mode.name.lowercase(Locale.US)}"
}

private fun topCategories(
    transactions: List<TransactionSummary>,
    categories: List<CategorySummary>,
    fallbackCurrency: String,
): List<CategorySpend> {
    val byId = categories.associateBy { it.id }
    return transactions
        .filter { it.type == "expense" }
        .groupBy { it.categoryId.orEmpty() }
        .map { (categoryId, items) ->
            val category = byId[categoryId]
            CategorySpend(
                name = category?.displayName() ?: "Без категории",
                amount = items.sumMoney(),
                currency = items.firstOrNull()?.currency ?: fallbackCurrency,
                color = category.colorOrFallback(),
                icon = category?.icon() ?: R.drawable.ic_category_24,
            )
        }
        .sortedByDescending { it.amount }
}

private fun List<AccountSummary>.filterByMode(mode: FinanceMode): List<AccountSummary> {
    return when (mode) {
        FinanceMode.Personal -> filter { it.ownershipType != "shared" }
        FinanceMode.Shared -> filter { it.ownershipType == "shared" }
        FinanceMode.Overview -> this
    }
}

private fun TransactionSummary.matchesMode(accountIds: Set<String>): Boolean {
    if (type == "transfer") {
        return accountId in accountIds && counterpartyAccountId in accountIds
    }
    return accountId in accountIds
}

private fun AccountSummary.matchesWritableMode(mode: FinanceMode): Boolean {
    return when (mode) {
        FinanceMode.Personal -> ownershipType != "shared"
        FinanceMode.Shared -> ownershipType == "shared"
        FinanceMode.Overview -> false
    }
}

internal data class LegacyAssetCategoryMigrationTarget(
    val scopeType: String,
    val householdId: String?,
    val currency: String,
)

internal sealed class LegacyAssetCategoryMigrationTargetSelection {
    data class Ready(val target: LegacyAssetCategoryMigrationTarget) : LegacyAssetCategoryMigrationTargetSelection()
    data class Blocked(val message: String) : LegacyAssetCategoryMigrationTargetSelection()
}

internal sealed class LegacyInvestmentMigrationRequestSelection {
    data class Ready(val request: InvestmentMigrationCreateRequest) : LegacyInvestmentMigrationRequestSelection()
    data class Blocked(val message: String) : LegacyInvestmentMigrationRequestSelection()
}

internal sealed class LegacyGroupMigrationResult {
    data object Success : LegacyGroupMigrationResult()
    data class Failure(val message: String) : LegacyGroupMigrationResult()
}

internal sealed class LegacyGroupSaveAction {
    data class Rename(val name: String) : LegacyGroupSaveAction()
    data class MigrateToInvestment(val name: String) : LegacyGroupSaveAction()
    data class Invalid(val message: String) : LegacyGroupSaveAction()
}

internal fun legacyGroupSaveAction(
    nameDraft: String,
    isInvestmentChecked: Boolean,
): LegacyGroupSaveAction {
    val cleanName = nameDraft.trim()
    if (cleanName.isBlank()) {
        return LegacyGroupSaveAction.Invalid("Введите название группы")
    }
    return if (isInvestmentChecked) {
        LegacyGroupSaveAction.MigrateToInvestment(cleanName)
    } else {
        LegacyGroupSaveAction.Rename(cleanName)
    }
}

internal fun shouldEditLegacyAssetGroupManualAmount(
    summary: AssetSummary,
    linkedAccounts: List<AccountSummary>,
): Boolean {
    return summary.kind == AssetKind.Metal &&
        summary.count == 0 &&
        linkedAccounts.none { it.status == "active" }
}

internal fun legacyManualAssetCategoryCreateRequest(
    kind: AssetKind,
    nameDraft: String,
    manualAmountDraft: String,
    isInvestmentChecked: Boolean,
    target: LegacyAssetCategoryMigrationTarget,
): AssetCategoryCreateRequest? {
    val cleanName = nameDraft.trim()
    if (cleanName.isBlank()) {
        return null
    }
    val manualAmount = manualAmountDraft.normalizedBalanceAmount() ?: return null
    return AssetCategoryCreateRequest(
        name = cleanName,
        scopeType = target.scopeType,
        householdId = target.householdId,
        currency = target.currency,
        manualAmount = manualAmount,
        isInvestment = isInvestmentChecked,
        assetType = kind.apiValue,
        iconKey = defaultAssetCategoryIconKey(kind.apiValue),
    )
}

internal fun legacyInvestmentMigrationCreateRequest(
    kind: AssetKind,
    nameDraft: String,
    target: LegacyAssetCategoryMigrationTarget,
    accounts: List<AccountSummary>,
    assetCategoryId: String,
): LegacyInvestmentMigrationRequestSelection {
    val cleanName = nameDraft.trim()
    if (cleanName.isBlank()) {
        return LegacyInvestmentMigrationRequestSelection.Blocked("Введите название группы")
    }
    val activeAccounts = accounts.filter { it.status == "active" && it.assetCategoryId.isNullOrBlank() }
    if (activeAccounts.isEmpty()) {
        return LegacyInvestmentMigrationRequestSelection.Blocked(
            "В legacy-группе нет активных счетов для переноса.",
        )
    }
    val accountIds = activeAccounts.mapNotNull { it.id.takeIf { id -> id.isNotBlank() } }
    if (accountIds.size != activeAccounts.size) {
        return LegacyInvestmentMigrationRequestSelection.Blocked(
            "Обновите данные: у части счетов нет серверного идентификатора.",
        )
    }
    val accountVersions = activeAccounts.mapNotNull { account ->
        account.version?.takeIf { it > 0 }?.let { account.id to it }
    }.toMap()
    if (accountVersions.size != activeAccounts.size) {
        return LegacyInvestmentMigrationRequestSelection.Blocked(
            "Обновите данные: у части счетов нет версии для безопасной миграции.",
        )
    }
    return LegacyInvestmentMigrationRequestSelection.Ready(
        InvestmentMigrationCreateRequest(
            assetCategoryId = assetCategoryId,
            name = cleanName,
            iconKey = defaultAssetCategoryIconKey(kind.apiValue),
            color = null,
            assetType = kind.apiValue,
            currency = target.currency,
            scope = target.scopeType,
            householdId = target.householdId,
            accountIds = accountIds,
            accountVersions = accountVersions,
        ),
    )
}

internal fun updatedAssetCategoryFromGroupEdit(
    category: AssetCategory,
    nameDraft: String,
    isInvestmentChecked: Boolean,
    manualAmountDraft: String? = null,
    canEditManualAmount: Boolean = false,
): AssetCategory? {
    val cleanName = nameDraft.trim()
    if (cleanName.isBlank()) {
        return null
    }
    val manualAmount = if (canEditManualAmount) {
        manualAmountDraft?.normalizedBalanceAmount() ?: return null
    } else {
        category.manualAmount
    }
    return category.copy(
        name = cleanName,
        manualAmount = manualAmount,
        isInvestment = isInvestmentChecked,
        assetType = category.assetType,
        iconKey = category.iconKey,
    )
}

internal fun shouldEditAssetCategoryManualAmount(
    row: AssetCategoryUiRow,
    linkedAccounts: List<AccountSummary>,
): Boolean {
    row.linkedAccountCount?.let { return it == 0 }
    if (linkedAccounts.isEmpty()) {
        return true
    }
    val manualAmount = row.manualAmount.toMoney()
    if (manualAmount == BigDecimal.ZERO) {
        return false
    }
    return row.accountsTotal.toMoney() == BigDecimal.ZERO &&
        row.totalAmount.toMoney() == manualAmount
}

internal fun assetCategoryGroupEditError(
    nameDraft: String,
    manualAmountDraft: String?,
    canEditManualAmount: Boolean,
): String {
    if (nameDraft.trim().isBlank()) {
        return "Введите название группы"
    }
    if (canEditManualAmount && manualAmountDraft?.normalizedBalanceAmount() == null) {
        return "Введите корректную ручную сумму"
    }
    return "Проверьте данные"
}

internal fun selectLegacyAssetCategoryMigrationTarget(
    selectedMode: FinanceMode,
    accounts: List<AccountSummary>,
    sessionHouseholdId: String?,
    fallbackCurrency: String?,
    groupName: String,
): LegacyAssetCategoryMigrationTargetSelection {
    val activeLegacyAccounts = accounts.filter { it.status == "active" && it.assetCategoryId.isNullOrBlank() }
    val currencies = activeLegacyAccounts
        .map { it.currency.trim().uppercase(Locale.US) }
        .filter { it.isNotBlank() }
        .distinct()
    if (currencies.size > 1) {
        return LegacyAssetCategoryMigrationTargetSelection.Blocked(
            "В legacy-группе «$groupName» счета в разных валютах. Сначала разделите или переместите счета по валютам.",
        )
    }

    val accountScopes = activeLegacyAccounts
        .map { if (it.ownershipType == "shared") "household" else "personal" }
        .distinct()
    if (accountScopes.size > 1) {
        return LegacyAssetCategoryMigrationTargetSelection.Blocked(
            "В legacy-группе «$groupName» есть личные и общие счета. Сначала разделите их по scope.",
        )
    }

    val scopeType = accountScopes.singleOrNull() ?: when (selectedMode) {
        FinanceMode.Personal -> "personal"
        FinanceMode.Shared -> "household"
        FinanceMode.Overview -> "personal"
    }

    val householdIds = activeLegacyAccounts
        .filter { it.ownershipType == "shared" }
        .mapNotNull { it.householdId?.takeIf { id -> id.isNotBlank() } }
        .distinct()
    if (householdIds.size > 1) {
        return LegacyAssetCategoryMigrationTargetSelection.Blocked(
            "В legacy-группе «$groupName» счета из разных общих бюджетов. Сначала разделите их.",
        )
    }
    val householdId = if (scopeType == "household") {
        householdIds.singleOrNull() ?: sessionHouseholdId?.takeIf { it.isNotBlank() }
            ?: return LegacyAssetCategoryMigrationTargetSelection.Blocked(
                "Для общей инвестиционной категории нужна активная семья.",
            )
    } else {
        null
    }

    val currency = currencies.singleOrNull()
        ?: fallbackCurrency?.trim()?.uppercase(Locale.US)?.takeIf { it.isNotBlank() }
        ?: "RUB"
    return LegacyAssetCategoryMigrationTargetSelection.Ready(
        LegacyAssetCategoryMigrationTarget(
            scopeType = scopeType,
            householdId = householdId,
            currency = currency,
        ),
    )
}

private fun CategorySummary.matchesWritableMode(mode: FinanceMode): Boolean {
    return when (mode) {
        FinanceMode.Personal -> scope != "household"
        FinanceMode.Shared -> scope == "household"
        FinanceMode.Overview -> false
    }
}

internal fun transferPairValidationMessage(
    source: AccountSummary?,
    destination: AccountSummary?,
): String? {
    if (source == null || destination == null) {
        return "Для перевода нужны два совместимых счета в одном scope и одной валюте."
    }
    if (source.id == destination.id) {
        return "Выберите два разных счета"
    }
    if (source.currency != destination.currency) {
        return "Перед отправкой выберите счета в одной валюте: конвертация в переводе недоступна."
    }
    if (source.ownershipType != destination.ownershipType) {
        return "Перед отправкой выберите два личных счёта."
    }
    if (
        source.ownershipType == "shared" &&
        source.householdId.orEmpty() != destination.householdId.orEmpty()
    ) {
        return "Перед отправкой выберите счета одного общего бюджета."
    }
    return null
}

private fun List<TransactionSummary>.sumMoney(): BigDecimal {
    return fold(BigDecimal.ZERO) { total, transaction -> total + transaction.amount.toMoney() }
}

private fun String?.toMoney(): BigDecimal {
    return runCatching { BigDecimal(this ?: "0") }.getOrDefault(BigDecimal.ZERO)
}

private fun String.normalizedAmount(): String? {
    val normalized = trim().replace(',', '.')
    val value = runCatching { BigDecimal(normalized) }.getOrNull()
    return value?.takeIf { it > BigDecimal.ZERO }?.setScale(2, RoundingMode.HALF_UP)?.toPlainString()
}

private fun String.normalizedBalanceAmount(): String? {
    val normalized = trim().replace(',', '.')
    if (!Regex("-?\\d+(\\.\\d+)?").matches(normalized)) return null
    return runCatching { BigDecimal(normalized).toPlainString() }.getOrNull()
}

private fun BigDecimal.formatMoney(currency: String): String {
    val formatter = NumberFormat.getNumberInstance(Locale("ru", "RU")).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }
    return "${formatter.format(this)} $currency"
}

private fun TransactionSummary.signedAmount(): String {
    val prefix = when (type) {
        "income" -> "+"
        "expense" -> "-"
        else -> ""
    }
    return "$prefix${amount.toMoney().formatMoney(currency)}"
}

private fun TransactionSummary.displayDate(): String {
    return transactionDate.ifBlank { occurredAt.take(10) }
}

internal fun List<TransactionSummary>.sortedNewestFirst(): List<TransactionSummary> = sortedWith(
    compareByDescending<TransactionSummary> { it.transactionDate.ifBlank { it.occurredAt.take(10) } }
        .thenByDescending { it.occurredAt }
        .thenByDescending { it.createdAt }
        .thenByDescending { it.id },
)

private fun TransactionSummary.localizedType(): String = when (type) {
    "income" -> "Доход"
    "transfer" -> "Перевод"
    "brokerage" -> "Актив"
    "asset_buy" -> "Покупка актива"
    "asset_sell" -> "Продажа актива"
    "interest" -> "Проценты"
    "dividend" -> "Дивиденды"
    "adjustment" -> "Корректировка"
    else -> "Расход"
}

@DrawableRes
private fun TransactionSummary.icon(): Int = when (type) {
    "income" -> R.drawable.ic_coin_24
    "transfer" -> R.drawable.ic_swap_24
    "brokerage", "asset_buy", "asset_sell" -> R.drawable.ic_chart_24
    "interest", "dividend" -> R.drawable.ic_coin_24
    "adjustment" -> R.drawable.ic_receipt_24
    else -> R.drawable.ic_trending_down_24
}

private fun TransactionSummary.tint(): Color = when (type) {
    "income" -> Color(0xFF2E7D62)
    "transfer" -> Color(0xFF6A6F7A)
    "brokerage", "asset_buy", "asset_sell" -> Color(0xFF227C9D)
    "interest", "dividend" -> Color(0xFF2E7D62)
    "adjustment" -> Color(0xFF6D5BD0)
    else -> Color(0xFFE35D4F)
}

private fun AccountSummary.assetKind(): AssetKind {
    val lowerName = name.lowercase(Locale.getDefault())
    return when {
        type == "metal" || "металл" in lowerName || "gold" in lowerName -> AssetKind.Metal
        type == "card" -> AssetKind.Card
        type == "cash" -> AssetKind.Cash
        type == "deposit" -> AssetKind.Deposit
        type == "brokerage" -> AssetKind.Brokerage
        "карта" in lowerName || "card" in lowerName -> AssetKind.Card
        else -> AssetKind.Bank
    }
}

private fun AssetCategory.matchesMode(mode: FinanceMode): Boolean = when (mode) {
    FinanceMode.Personal -> scopeType != "household"
    FinanceMode.Shared -> scopeType == "household"
    FinanceMode.Overview -> true
}

private fun AssetCategoryGroup.matchesMode(mode: FinanceMode): Boolean = when (mode) {
    FinanceMode.Personal -> scopeType != "household"
    FinanceMode.Shared -> scopeType == "household"
    FinanceMode.Overview -> true
}

private fun AssetCategoryGroup.toAssetCategory(): AssetCategory {
    return AssetCategory(
        id = assetCategoryId,
        name = name,
        scopeType = scopeType,
        householdId = householdId,
        currency = currency,
        manualAmount = manualAmount,
        isInvestment = isInvestment,
        assetType = assetType,
        iconKey = iconKey,
    )
}

private fun String.assetKindOrBank(): AssetKind {
    return AssetKind.entries.firstOrNull { it.apiValue == this } ?: AssetKind.Bank
}

private fun String.assetScopeTitle(): String {
    return if (this == "household") "legacy" else "personal"
}

private fun CategorySummary?.colorOrFallback(): Color {
    val fallback = if (this?.type == "income") Color(0xFF2E7D62) else Color(0xFFE35D4F)
    val raw = this?.color?.takeIf { it.startsWith("#") } ?: return fallback
    return runCatching { Color(android.graphics.Color.parseColor(raw)) }.getOrDefault(fallback)
}

@DrawableRes
private fun CategorySummary.icon(): Int {
    val key = iconKey.lowercase(Locale.getDefault())
    val name = name.lowercase(Locale.getDefault())
    return when {
        "food" in key || "продукт" in name || "кафе" in name -> R.drawable.ic_food_24
        "transport" in key || "такси" in name || "транспорт" in name -> R.drawable.ic_car_24
        "shop" in key || "покуп" in name -> R.drawable.ic_shopping_24
        type == "income" -> R.drawable.ic_coin_24
        else -> R.drawable.ic_category_24
    }
}

@DrawableRes
private fun AppSection.icon(): Int = when (this) {
    AppSection.Home -> R.drawable.ic_home_24
    AppSection.Operations -> R.drawable.ic_receipt_24
    AppSection.Assets -> R.drawable.ic_wallet_24
    AppSection.Categories -> R.drawable.ic_category_24
    AppSection.Analytics -> R.drawable.ic_analytics_24
}

@DrawableRes
private fun FinanceMode.icon(): Int = when (this) {
    FinanceMode.Personal -> R.drawable.ic_person_24
    FinanceMode.Shared -> R.drawable.ic_group_24
    FinanceMode.Overview -> R.drawable.ic_analytics_24
}

@DrawableRes
private fun QuickEntryType.icon(): Int = when (this) {
    QuickEntryType.Expense -> R.drawable.ic_trending_down_24
    QuickEntryType.Income -> R.drawable.ic_coin_24
    QuickEntryType.Transfer -> R.drawable.ic_swap_24
    QuickEntryType.Asset -> R.drawable.ic_wallet_24
}

private fun List<AccountSummary>.firstByIdOrFirst(id: String): AccountSummary? {
    return firstOrNull { it.id.isNotBlank() && it.id == id } ?: firstOrNull()
}

private fun List<CategorySummary>.firstByIdOrFirst(id: String): CategorySummary? {
    return firstOrNull { it.id.isNotBlank() && it.id == id } ?: firstOrNull()
}

internal fun List<CategorySummary>.quickAddCategoryFor(
    categoryId: String,
    transactionType: String,
): CategorySummary? {
    val matching = filter { it.type == transactionType && it.status == "active" }
    return matching.firstOrNull { it.id.isNotBlank() && it.id == categoryId } ?: matching.firstOrNull()
}

private fun AccountSummary.displayName(): String = userFacingSeedText(name)

private fun CategorySummary.displayName(): String = userFacingSeedText(name)

private fun CategorySummary.localizedType(): String = if (type == "income") "Доход" else "Расход"

private fun FinanceMode.scopeTitle(): String = when (this) {
    FinanceMode.Personal -> "Личные финансы"
    FinanceMode.Shared -> "Legacy"
    FinanceMode.Overview -> "Legacy"
}

internal fun loggedOutFinanceUiState(result: ApiResult<Unit>): FinanceUiState = FinanceUiState(
    message = when (result) {
        is ApiResult.Success -> "Сессия завершена"
        is ApiResult.Failure -> "Сессия завершена на устройстве. Сервер временно недоступен."
    },
)

internal suspend fun completedLogoutUiState(
    result: ApiResult<Unit>,
    apiClient: FinanceApiClient,
): FinanceUiState = if (result is ApiResult.Failure && result.kind == ApiFailureKind.SESSION_CHANGED) {
    restoredFinanceUiState(apiClient)
} else {
    loggedOutFinanceUiState(result)
}

private fun TransactionSummary.displayDescription(): String {
    return userFacingSeedText(description).ifBlank { localizedType() }
}

private fun String.localizedCaptureSource(): String = when (this) {
    "screenshot_ocr" -> "OCR-черновик со скрина"
    "manual" -> "Черновик вручную"
    else -> "Черновик"
}

private fun ApiResult.Failure.userFacingMessage(): String {
    return when {
        message.isNotBlank() -> message.userFacingFailureText()
        statusCode == 401 -> "Сессия истекла. Войдите снова."
        statusCode == 403 -> "Нет доступа."
        statusCode != null && statusCode >= 500 -> "Ошибка сервера. Попробуйте позже."
        else -> "Не удалось выполнить действие"
    }
}

private fun String.userFacingFailureText(): String {
    return when {
        contains("Cannot open image", ignoreCase = true) -> "Не удалось открыть изображение"
        contains("not supported", ignoreCase = true) -> "Действие пока не поддерживается этим клиентом"
        contains("HTTP 401", ignoreCase = true) -> "Сессия истекла. Войдите снова."
        contains("HTTP 403", ignoreCase = true) -> "Нет доступа."
        else -> this
    }
}

private fun ApiResult.Failure.isAuthenticationFailure(): Boolean {
    if (statusCode == 401 || statusCode == 403) {
        return true
    }
    if (statusCode != null) {
        return false
    }
    return listOf(
        "HTTP 401",
        "HTTP 403",
    ).any { message.contains(it, ignoreCase = true) }
}

internal fun ApiResult.Failure.isRetriableForOfflineQueue(): Boolean {
    val code = statusCode ?: return isNetworkFailure
    return code == 408 || code == 429 || code >= 500
}

private fun SessionStatus.syncUserIdOrNull(): String? {
    return userId?.takeIf { it.isNotBlank() }
}

private fun Int?.orZero(): Int = this ?: 0

@Preview(showBackground = true, widthDp = 390)
@Composable
private fun FinanceAppPreview() {
    FinanceTheme {
        FinanceApp(apiClient = PreviewFinanceApiClient())
    }
}

private class PreviewFinanceApiClient : FinanceApiClient {
    override val config: ApiConfig = ApiConfig(BuildConfig.FINANCE_API_BASE_URL)

    override suspend fun login(email: String, password: String): ApiResult<SessionStatus> {
        return sessionStatus()
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> {
        return ApiResult.Success(SessionStatus(true, "Пользователь", "household"))
    }

    override suspend fun dashboard(startDate: String?, endDate: String?): ApiResult<FinanceDashboard> {
        val session = SessionStatus(true, "Пользователь", "household")
        return ApiResult.Success(previewDashboard(session))
    }

    override suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String,
        accountType: String,
        ownershipType: String,
        isPaymentAccount: Boolean,
    ): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Новый актив", accountType, ownershipType, currency, initialBalance, id = "acc-created", householdId = householdId, version = 1, isPaymentAccount = isPaymentAccount))
    }

    override suspend fun createAccount(
        name: String,
        currency: String,
        initialBalance: String,
        accountType: String,
        householdId: String?,
        assetCategoryId: String?,
        isPaymentAccount: Boolean,
    ): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary(name, accountType, if (householdId.isNullOrBlank()) "personal" else "shared", currency, initialBalance, id = "acc-created", householdId = householdId, assetCategoryId = assetCategoryId, version = 1, isPaymentAccount = isPaymentAccount))
    }

    override suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary> {
        return ApiResult.Success(account.copy(version = (account.version ?: 1) + 1))
    }

    override suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Архивный счет", "cash", "personal", "USD", "0.00", id = accountId, status = "archived", version = 2))
    }

    override suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Восстановленный счет", "cash", "personal", "USD", "0.00", id = accountId, version = 3))
    }

    override suspend fun createDemoCategory(
        householdId: String?,
        categoryType: String,
    ): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary("Дом", categoryType, "personal", id = "cat-created", color = "#5B6EE1", version = 1))
    }

    override suspend fun createCategory(
        name: String,
        householdId: String?,
        categoryType: String,
    ): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary(name, categoryType, "personal", id = "cat-created", color = "#5B6EE1", version = 1))
    }

    override suspend fun updateCategory(category: CategorySummary): ApiResult<CategorySummary> {
        return ApiResult.Success(category.copy(version = (category.version ?: 1) + 1))
    }

    override suspend fun archiveCategory(categoryId: String): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary("Дом", "expense", "personal", id = categoryId, status = "archived", version = 2))
    }

    override suspend fun restoreCategory(categoryId: String): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary("Дом", "expense", "personal", id = categoryId, version = 3))
    }

    override suspend fun createDemoTransaction(
        account: AccountSummary,
        category: CategorySummary?,
        transactionType: String,
        amount: String,
        transactionDate: String,
    ): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary(transactionType, amount, account.currency, "${transactionDate}T00:00:00Z", category?.name ?: "Новая операция", null, null, id = "txn-created", accountId = account.id, categoryId = category?.id, version = 1, transactionDate = transactionDate))
    }

    override suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary> {
        return ApiResult.Success(transaction.copy(version = (transaction.version ?: 1) + 1))
    }

    override suspend fun deleteTransaction(transactionId: String): ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary("expense", "18.00", "USD", "2026-05-18T09:00:00Z", "Восстановленная операция", null, null, id = transactionId, accountId = "acc-cash", categoryId = "cat-food", version = 3))
    }

    override suspend fun createDemoTransfer(
        source: AccountSummary,
        destination: AccountSummary,
        amount: String,
        transactionDate: String,
    ): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary("transfer", amount, source.currency, "${transactionDate}T12:00:00Z", "Между счетами", "personal_same_owner", "posted", id = "txn-transfer-created", accountId = source.id, counterpartyAccountId = destination.id, version = 1, transactionDate = transactionDate))
    }

    override suspend fun logout(): ApiResult<Unit> = ApiResult.Success(Unit)
}

private fun previewDashboard(session: SessionStatus): FinanceDashboard {
    return FinanceDashboard(
        session = session,
        accounts = listOf(
            AccountSummary("Карта Everyday", "bank", "personal", "USD", "925.50", id = "acc-card", version = 1),
            AccountSummary("Наличные", "cash", "personal", "USD", "180.00", id = "acc-cash", version = 1),
            AccountSummary("Вклад", "deposit", "shared", "USD", "5400.00", id = "acc-save", householdId = "household", version = 1),
            AccountSummary("Брокер", "brokerage", "personal", "USD", "2200.00", id = "acc-broker", version = 1),
        ),
        categories = listOf(
            CategorySummary("Продукты", "expense", "personal", id = "cat-food", iconKey = "food", color = "#E35D4F", version = 1),
            CategorySummary("Транспорт", "expense", "personal", id = "cat-transport", iconKey = "transport", color = "#5B6EE1", version = 1),
            CategorySummary("Зарплата", "income", "personal", id = "cat-salary", iconKey = "income", color = "#2E7D62", version = 1),
        ),
        transactions = listOf(
            TransactionSummary("income", "2500.00", "USD", "2026-05-18T08:30:00Z", "Зарплата", null, null, id = "txn-income", accountId = "acc-card", categoryId = "cat-salary", version = 1),
            TransactionSummary("transfer", "150.00", "USD", "2026-05-17T08:30:00Z", "На вклад", "personal_same_owner", "posted", id = "txn-transfer", accountId = "acc-card", counterpartyAccountId = "acc-save", version = 1),
            TransactionSummary("expense", "69.75", "USD", "2026-05-16T12:30:00Z", "Супермаркет", null, null, id = "txn-expense", accountId = "acc-card", categoryId = "cat-food", version = 1),
            TransactionSummary("expense", "18.20", "USD", "2026-05-15T12:30:00Z", "Такси", null, null, id = "txn-taxi", accountId = "acc-card", categoryId = "cat-transport", version = 1),
        ),
        totals = listOf(MoneyTotal("USD", "2500.00", "87.95", "2412.05")),
        reportTransferCount = 1,
    )
}
