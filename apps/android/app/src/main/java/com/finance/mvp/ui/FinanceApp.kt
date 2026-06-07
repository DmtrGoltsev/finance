package com.finance.mvp.ui

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.annotation.DrawableRes
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ElevatedCard
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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.PointerInputScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.password
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.finance.mvp.R
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.AssetCategory
import com.finance.mvp.api.AssetCategoryCreateRequest
import com.finance.mvp.api.AssetCategoryGroup
import com.finance.mvp.api.CaptureDraft
import com.finance.mvp.api.CaptureDraftUpdateRequest
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.MoneyAmount
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.RegistrationResult
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import com.finance.mvp.api.userFacingSeedText
import com.finance.mvp.capture.AndroidCategoryAggregateMappingStore
import com.finance.mvp.capture.CategoryAggregateCandidate
import com.finance.mvp.notifications.PlanningReminderNotifications
import com.finance.mvp.ui.theme.FinanceTheme
import java.math.BigDecimal
import java.math.RoundingMode
import java.text.NumberFormat
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinanceApp(
    apiClient: FinanceApiClient,
    modifier: Modifier = Modifier,
    initialOpenPlanning: Boolean = false,
    openPlanningRequestKey: Int = if (initialOpenPlanning) 1 else 0,
) {
    val context = LocalContext.current
    val categoryAggregateMappingStore = remember(context) { AndroidCategoryAggregateMappingStore(context) }
    var selectedSection by rememberSaveable {
        mutableStateOf(if (initialOpenPlanning) AppSection.Analytics else AppSection.Home)
    }
    var selectedMode by rememberSaveable { mutableStateOf(FinanceMode.Personal) }
    var selectedAnalyticsSubsection by rememberSaveable {
        mutableStateOf(if (initialOpenPlanning) AnalyticsSubsection.Planning else AnalyticsSubsection.Summary)
    }
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
    var addAccountState by rememberSaveable { mutableStateOf<AddAccountState?>(null) }
    var showAssetCategorySheet by rememberSaveable { mutableStateOf(false) }
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
            screenshotOcrStatus = "Отправляем скриншот на распознавание"
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
                        householdId = uiState.session?.householdId,
                    )
                }
            }
            val result = ocrResult.getOrNull()
            if (ocrResult.isFailure || result == null) {
                val errorMsg = (result as? ApiResult.Failure)?.message
                    ?: ocrResult.exceptionOrNull()?.message
                    ?: "Неизвестная ошибка"
                screenshotOcrStatus = "Не удалось распознать платёж на скриншоте"
                captureMessage = "$errorMsg. Выберите другой скриншот или добавьте операцию вручную"
                captureIsLoading = false
                return@launch
            }

            when (result) {
                is ApiResult.Success -> {
                    val items = result.value.items
                    if (items.isEmpty()) {
                        screenshotOcrStatus = "Не удалось распознать платёж на скриншоте"
                        captureMessage = "Выберите другой скриншот или добавьте операцию вручную"
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
                    screenshotOcrStatus = "Найдено ${drafts.size} категорий. Проверьте перед созданием."
                    captureMessage = "Выберите категории и подтвердите черновики"
                    captureIsLoading = false
                }
                is ApiResult.Failure -> {
                    screenshotOcrStatus = "Не удалось распознать платёж на скриншоте"
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
            captureMessage = "Выберите хотя бы одну категорию"
            return
        }
        scope.launch {
            captureIsLoading = true
            screenshotOcrStatus = "Создаём ${selectedDrafts.size} черновиков"
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
                    screenshotOcrStatus = "Черновики созданы: ${selectedDrafts.size}"
                    captureMessage = "Проверьте и подтвердите созданные черновики"
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

    fun loadDashboard(successMessage: String = "Данные обновлены") {
        scope.launch {
            uiState = uiState.copy(isLoading = true, message = "Обновляем данные")
            uiState = when (val result = withContext(Dispatchers.IO) { apiClient.dashboard() }) {
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
        }
    }

    fun confirmCaptureDraft(draft: CaptureDraft, accountId: String, categoryId: String) {
        val selectedAccountId = accountId.takeIf { it.isNotBlank() }
        val selectedCategoryId = categoryId.takeIf { it.isNotBlank() }
        if (selectedAccountId == null || selectedCategoryId == null) {
            captureMessage = "Выберите счёт и категорию перед подтверждением"
            return
        }
        scope.launch {
            captureIsLoading = true
            val result = withContext(Dispatchers.IO) {
                val draftToConfirm = if (draft.accountId != selectedAccountId || draft.categoryId != selectedCategoryId) {
                    when (
                        val updateResult = apiClient.updateCaptureDraft(
                            draft.id,
                            CaptureDraftUpdateRequest(
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
            uiState = uiState.copy(isLoading = true, message = "Выходим")
            when (val result = withContext(Dispatchers.IO) { apiClient.logout() }) {
                is ApiResult.Success -> uiState = FinanceUiState(message = "Сессия завершена")
                is ApiResult.Failure -> uiState = uiState.copy(
                    isLoading = false,
                    message = result.userFacingMessage(),
                )
            }
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
                        val account = dashboard.accounts.firstByIdOrFirst(draft.accountId)
                            ?: when (
                                val created = apiClient.createDemoAccount(
                                    householdId = if (draft.visibility == FinanceMode.Shared) uiState.session?.householdId else null,
                                    currency = dashboard.accounts.firstOrNull()?.currency ?: "RUB",
                                )
                            ) {
                                is ApiResult.Success -> created.value
                                is ApiResult.Failure -> return@withContext created
                            }
                        val category = dashboard.categories.quickAddCategoryFor(
                            categoryId = draft.categoryId,
                            transactionType = draft.type.apiValue,
                        )
                        val resolvedCategory = category ?: when (
                            val createdCategory = apiClient.createDemoCategory(
                                householdId = if (draft.visibility == FinanceMode.Shared) uiState.session?.householdId else null,
                                categoryType = draft.type.apiValue,
                            )
                        ) {
                            is ApiResult.Success -> createdCategory.value
                            is ApiResult.Failure -> return@withContext createdCategory
                        }
                        apiClient.createDemoTransaction(
                            account = account,
                            category = resolvedCategory,
                            transactionType = draft.type.apiValue,
                            amount = amount,
                        )
                    }
                    QuickEntryType.Transfer -> {
                        val source = dashboard.accounts.firstByIdOrFirst(draft.accountId)
                        val destination = dashboard.accounts
                            .filter { it.id != source?.id }
                            .firstByIdOrFirst(draft.destinationAccountId)
                        val validationMessage = transferPairValidationMessage(source, destination)
                        if (validationMessage != null) {
                            ApiResult.Failure(validationMessage)
                        } else {
                            apiClient.createDemoTransfer(source!!, destination!!, amount)
                        }
                    }
                    QuickEntryType.Asset -> {
                        val currency = dashboard.accounts.firstOrNull()?.currency ?: "RUB"
                        val ownershipType = if (draft.visibility == FinanceMode.Shared) "shared" else "personal"
                        apiClient.createDemoAccount(
                            householdId = if (ownershipType == "shared") uiState.session?.householdId else null,
                            currency = currency,
                            initialBalance = amount,
                            accountType = draft.assetKind.apiValue,
                            ownershipType = ownershipType,
                        )
                    }
                }
            }

            when (result) {
                is ApiResult.Success -> {
                    quickAddError = null
                    showQuickAdd = false
                    quickAddOpenKey += 1
                    loadDashboard("Сохранено")
                }
                is ApiResult.Failure -> {
                    val message = result.userFacingMessage()
                    quickAddError = message
                    uiState = uiState.copy(
                        isLoading = false,
                        message = message,
                    )
                }
            }
        }
    }

    LaunchedEffect(apiClient) {
        uiState = withContext(Dispatchers.IO) { restoredFinanceUiState(apiClient) }
    }

    LaunchedEffect(apiClient, uiState.session?.isAuthenticated) {
        if (uiState.session?.isAuthenticated == true) {
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
                    IconButton(
                        onClick = { loadDashboard() },
                        enabled = !uiState.isLoading && uiState.session?.isAuthenticated == true,
                    ) {
                        Icon(painterResource(R.drawable.ic_refresh_24), contentDescription = "Обновить")
                    }
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
                        icon = { Icon(painterResource(section.icon()), contentDescription = null) },
                        label = { Text(section.title) },
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
                AppSection.Home -> homeContent(dashboard, selectedMode) { selectedMode = it }
                AppSection.Operations -> operationsContent(
                    dashboard = dashboard,
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
                                    householdId = uiState.session?.householdId,
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
                    onModeSelected = { selectedMode = it },
                    groupNames = assetGroupNames,
                    onRenameGroup = { kind, newName ->
                        assetGroupNames = assetGroupNames + (kind.apiValue to newName)
                    },
                    onCreateAssetCategory = { showAssetCategorySheet = true },
                    onUpdateAssetCategory = { category ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Обновляем категорию активов")
                            val result = withContext(Dispatchers.IO) { apiClient.updateAssetCategory(category) }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория активов обновлена")
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
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                    onArchiveGroup = { accountIds ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Удаляем группу активов")
                            val failure = withContext(Dispatchers.IO) {
                                accountIds.firstNotNullOfOrNull { accountId ->
                                    when (val result = apiClient.archiveAccount(accountId)) {
                                        is ApiResult.Success -> null
                                        is ApiResult.Failure -> result
                                    }
                                }
                            }
                            if (failure == null) {
                                loadDashboard("Группа активов удалена")
                            } else {
                                uiState = uiState.copy(
                                    isLoading = false,
                                    message = failure.userFacingMessage(),
                                )
                            }
                        }
                    },
                    onAddAccount = { kind ->
                        addAccountState = AddAccountState(kind, selectedMode)
                    },
                    onAddAccountToCategory = { category ->
                        val categoryMode = if (category.scopeType == "household") FinanceMode.Shared else FinanceMode.Personal
                        addAccountState = AddAccountState(category.assetType.assetKindOrBank(), categoryMode, category.id)
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
                                    householdId = if (mode == FinanceMode.Shared) uiState.session?.householdId else null,
                                    categoryType = type.apiValue,
                                )
                            }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория добавлена")
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
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
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                    onArchiveCategory = { categoryId ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Удаляем категорию")
                            val result = withContext(Dispatchers.IO) { apiClient.archiveCategory(categoryId) }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория удалена")
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                )
                AppSection.Analytics -> analyticsContent(
                    apiClient = apiClient,
                    dashboard = dashboard,
                    selectedMode = selectedMode,
                    selectedSubsection = selectedAnalyticsSubsection,
                    onModeSelected = { selectedMode = it },
                    onSubsectionSelected = { selectedAnalyticsSubsection = it },
                    onCreatePlanningCategory = { name, mode ->
                        val result = withContext(Dispatchers.IO) {
                            apiClient.createCategory(
                                name = name,
                                householdId = if (mode == FinanceMode.Shared) uiState.session?.householdId else null,
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
                                householdId = if (mode == FinanceMode.Shared) uiState.session?.householdId else null,
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
                )
            }

            item { Spacer(modifier = Modifier.height(72.dp)) }
        }
    }

    if (showQuickAdd) {
        QuickAddSheet(
            sheetKey = quickAddOpenKey,
            dashboard = uiState.dashboard,
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
            onDismiss = { addAccountState = null },
            onSubmit = { name, balance, currency ->
                scope.launch {
                    uiState = uiState.copy(isLoading = true, message = "Добавляем актив")
                    val result = withContext(Dispatchers.IO) {
                        apiClient.createAccount(
                            name = name,
                            currency = currency,
                            initialBalance = balance,
                            accountType = kind.apiValue,
                            householdId = if (state.mode == FinanceMode.Shared) uiState.session?.householdId else null,
                            assetCategoryId = state.assetCategoryId,
                        )
                    }
                    when (result) {
                        is ApiResult.Success -> {
                            addAccountState = null
                            loadDashboard("Актив добавлен")
                        }
                        is ApiResult.Failure -> uiState = uiState.copy(
                            isLoading = false,
                            message = result.userFacingMessage(),
                        )
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
                        is ApiResult.Failure -> uiState = uiState.copy(
                            isLoading = false,
                            message = result.userFacingMessage(),
                        )
                    }
                }
            },
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
    onModeSelected: (FinanceMode) -> Unit,
) {
    val view = dashboard.viewFor(selectedMode)
    item {
        ModeChips(
            selectedMode = selectedMode,
            onModeSelected = onModeSelected,
        )
    }
    item { CapitalCard(view) }
    item { AssetChips(view.assetSummaries) }
    item { MonthExpenseCard(view) }
    item { TopCategoriesCard(view.topCategories) }
    item { RecentOperationsCard(view.recentTransactions) }
}

private fun LazyListScope.operationsContent(
    dashboard: FinanceDashboard?,
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
    onConfirmCaptureDraft: (CaptureDraft, String, String) -> Unit,
    onDiscardCaptureDraft: (CaptureDraft) -> Unit,
    onDeleteTransaction: (String) -> Unit,
) {
    val items = dashboard?.transactions.orEmpty()
    item {
        CaptureDraftReviewCard(
            isAuthenticated = dashboard?.session?.isAuthenticated == true,
            drafts = captureDrafts,
            screenshotAggregateDrafts = screenshotAggregateDrafts,
            accounts = dashboard?.accounts.orEmpty(),
            categories = dashboard?.categories.orEmpty(),
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
        item { EmptyState("Операций пока нет") }
    }
    item { Text("Операции", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
    items(items.sortedByDescending { it.occurredAt }) { transaction ->
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
    onConfirm: (CaptureDraft, String, String) -> Unit,
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
            } else if (drafts.isEmpty() && screenshotAggregateDrafts.isEmpty()) {
                Text("Нет ожидающих черновиков.", style = MaterialTheme.typography.bodySmall)
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
    onConfirm: (CaptureDraft, String, String) -> Unit,
    onDiscard: (CaptureDraft) -> Unit,
) {
    var selectedAccountId by rememberSaveable(draft.id, draft.accountId) { mutableStateOf(draft.accountId.orEmpty()) }
    var selectedCategoryId by rememberSaveable(draft.id, draft.categoryId) { mutableStateOf(draft.categoryId.orEmpty()) }
    val activeAccounts = accounts
        .filter { it.status == "active" && it.id.isNotBlank() }
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
                    text = "${draft.captureSource.localizedCaptureSource()} ${draft.occurredAt.take(10)}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text(
                text = "-${draft.amount} ${draft.currency}",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFFE35D4F),
            )
        }
        Text(
            text = "Точность ${(draft.confidence * 100).toInt()}% | След ${draft.evidenceHash.take(12)}",
            style = MaterialTheme.typography.bodySmall,
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
                onClick = { onConfirm(draft, selectedAccountId, selectedCategoryId) },
                enabled = !isLoading && draft.id.isNotBlank() && selectedAccountId.isNotBlank() && selectedCategoryId.isNotBlank(),
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
    onCreateAssetCategory: () -> Unit,
    onUpdateAssetCategory: (AssetCategory) -> Unit,
    onUpdateAccount: (AccountSummary) -> Unit,
    onArchiveAccount: (String) -> Unit,
    onArchiveGroup: (List<String>) -> Unit,
    onAddAccount: (AssetKind) -> Unit,
    onAddAccountToCategory: (AssetCategory) -> Unit,
) {
    val allAccounts = dashboard?.accounts.orEmpty()
    val categoryRows = dashboard.assetCategoryRows(selectedMode)
    val modeAccounts = allAccounts.filterByMode(selectedMode)
    val legacyAccounts = modeAccounts.filter { it.status == "active" && it.assetCategoryId.isNullOrBlank() }
    val summaries = assetSummaries(legacyAccounts).filter { categoryRows.isEmpty() || it.count > 0 }
    item {
        ModeChips(
            selectedMode = selectedMode,
            onModeSelected = onModeSelected,
        )
    }
    item { Text("Активы", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
    item {
        OutlinedButton(onClick = onCreateAssetCategory, modifier = Modifier.fillMaxWidth()) {
            Text("Добавить категорию активов")
        }
    }
    if (categoryRows.isNotEmpty()) {
        items(categoryRows) { row ->
            AssetCategoryGroupCard(
                row = row,
                accounts = modeAccounts.filter { it.status == "active" && it.assetCategoryId == row.category.id },
                onUpdateCategory = onUpdateAssetCategory,
                onUpdateAccount = onUpdateAccount,
                onArchiveAccount = onArchiveAccount,
                onAddAccount = { onAddAccountToCategory(row.category) },
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
            onRenameGroup = { onRenameGroup(summary.kind, it) },
            onUpdate = onUpdateAccount,
            onArchive = onArchiveAccount,
            onArchiveGroup = onArchiveGroup,
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
            hasHousehold = !dashboard?.session?.householdId.isNullOrBlank(),
            onAddCategory = onAddCategory,
            onUpdateCategory = onUpdateCategory,
            onArchiveCategory = onArchiveCategory,
        )
    }
}

private fun LazyListScope.analyticsContent(
    apiClient: FinanceApiClient,
    dashboard: FinanceDashboard?,
    selectedMode: FinanceMode,
    selectedSubsection: AnalyticsSubsection,
    onModeSelected: (FinanceMode) -> Unit,
    onSubsectionSelected: (AnalyticsSubsection) -> Unit,
    onCreatePlanningCategory: suspend (String, FinanceMode) -> ApiResult<CategorySummary>,
    onCreatePlanningAccount: suspend (String, String, String, FinanceMode) -> ApiResult<AccountSummary>,
    onPlanningNotificationCandidate: (PlanningNotificationCandidate) -> Unit,
) {
    val view = dashboard.viewFor(selectedMode)
    item {
        ModeChips(
            selectedMode = selectedMode,
            onModeSelected = onModeSelected,
        )
    }
    item {
        AnalyticsSubsectionTabs(
            selected = selectedSubsection,
            onSelected = onSubsectionSelected,
        )
    }
    when (selectedSubsection) {
        AnalyticsSubsection.Summary -> {
            item { AnalyticsSummaryCard(view) }
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
                )
            }
        }
    }
}

@Composable
private fun ModeChips(
    selectedMode: FinanceMode,
    onModeSelected: (FinanceMode) -> Unit,
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(FinanceMode.entries.toList()) { mode ->
            FilterChip(
                selected = selectedMode == mode,
                onClick = { onModeSelected(mode) },
                label = { Text(mode.title) },
                leadingIcon = {
                    Icon(
                        painter = painterResource(mode.icon()),
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                },
            )
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
                Text("Расходов пока нет", style = MaterialTheme.typography.bodySmall)
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
                Text("Движений пока нет", style = MaterialTheme.typography.bodySmall)
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
                    text = "${transaction.occurredAt.take(10)} • ${transaction.displayDescription()}",
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
            Text(transaction.occurredAt.take(10), style = MaterialTheme.typography.labelSmall)
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
private fun AssetCategoryGroupCard(
    row: AssetCategoryUiRow,
    accounts: List<AccountSummary>,
    onUpdateCategory: (AssetCategory) -> Unit,
    onUpdateAccount: (AccountSummary) -> Unit,
    onArchiveAccount: (String) -> Unit,
    onAddAccount: () -> Unit,
) {
    val category = row.category
    val kind = category.assetType.assetKindOrBank()
    var isExpanded by rememberSaveable(category.id) { mutableStateOf(false) }
    var isEditing by rememberSaveable(category.id) { mutableStateOf(false) }
    var editName by rememberSaveable(category.id, category.name) { mutableStateOf(category.name) }
    var editManual by rememberSaveable(category.id, category.manualAmount) { mutableStateOf(category.manualAmount) }
    var editInvestment by rememberSaveable(category.id, category.isInvestment) { mutableStateOf(category.isInvestment) }
    var editAssetType by rememberSaveable(category.id, category.assetType) { mutableStateOf(category.assetType) }

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .tapOrLongPress(onTap = { isExpanded = !isExpanded }, onLongPress = { isEditing = true }),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconBubble(kind.icon, if (category.isInvestment) Color(0xFF227C9D) else kind.tint)
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(category.name, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        if (category.isInvestment) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Инвестиция",
                                color = Color(0xFF227C9D),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier
                                    .background(Color(0xFF227C9D).copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                                    .padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                    Text(
                        text = "${row.scopeTitle} • ${accounts.size} ${pluralItems(accounts.size)} • Ручная ${row.manualAmount.toMoney().formatMoney(row.currency)}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Text(row.totalAmount.toMoney().formatMoney(row.currency), fontWeight = FontWeight.SemiBold)
                IconButton(onClick = { isEditing = !isEditing }, modifier = Modifier.size(32.dp)) {
                    Icon(
                        painter = painterResource(R.drawable.ic_edit_24),
                        contentDescription = "Изменить",
                        modifier = Modifier.size(18.dp),
                    )
                }
            }

            if (isEditing) {
                OutlinedTextField(
                    value = editName,
                    onValueChange = { editName = it },
                    label = { Text("Название") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = editManual,
                    onValueChange = { editManual = it.filter { char -> char.isDigit() || char == '.' || char == ',' || char == '-' } },
                    label = { Text("Ручная сумма") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(AssetKind.entries.toList()) { option ->
                        FilterChip(
                            selected = editAssetType == option.apiValue,
                            onClick = { editAssetType = option.apiValue },
                            label = { Text(option.title) },
                        )
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = editInvestment, onCheckedChange = { editInvestment = it })
                    Text("Инвестиционная категория")
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { isEditing = false }, modifier = Modifier.weight(1f)) {
                        Text("Отмена")
                    }
                    Button(
                        onClick = {
                            onUpdateCategory(
                                category.copy(
                                    name = editName.trim().ifBlank { category.name },
                                    manualAmount = editManual.normalizedBalanceAmount() ?: "0",
                                    isInvestment = editInvestment,
                                    assetType = editAssetType,
                                ),
                            )
                            isEditing = false
                        },
                        enabled = editManual.normalizedBalanceAmount() != null,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("Сохранить")
                    }
                }
            }

            if (isExpanded) {
                if (accounts.isEmpty()) {
                    Text("Счетов в этой категории нет", style = MaterialTheme.typography.bodySmall)
                } else {
                    accounts.forEach { account ->
                        AccountRow(account = account, onUpdate = onUpdateAccount, onArchive = onArchiveAccount)
                    }
                }
                OutlinedButton(onClick = onAddAccount, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить счет в категорию")
                }
            }
        }
    }
}

@Composable
private fun AssetCategoryCard(
    summary: AssetSummary,
    accounts: List<AccountSummary>,
    displayName: String,
    onRenameGroup: (String) -> Unit,
    onUpdate: (AccountSummary) -> Unit,
    onArchive: (String) -> Unit,
    onArchiveGroup: (List<String>) -> Unit,
    onAdd: () -> Unit,
) {
    var isExpanded by rememberSaveable { mutableStateOf(false) }
    var isEditingGroup by rememberSaveable { mutableStateOf(false) }
    var groupNameDraft by rememberSaveable(displayName) { mutableStateOf(displayName) }
    var confirmArchiveGroup by rememberSaveable { mutableStateOf(false) }
    val activeAccountIds = remember(accounts) { accounts.map { it.id }.filter { it.isNotBlank() } }

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
                            onLongPress = {
                                if (activeAccountIds.isNotEmpty()) {
                                    confirmArchiveGroup = true
                                }
                            },
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconBubble(summary.kind.icon, summary.kind.tint)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(displayName, fontWeight = FontWeight.SemiBold)
                        Text(
                            text = if (accounts.isEmpty()) "Нажмите чтобы добавить" else "${accounts.size} ${pluralItems(accounts.size)}",
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
            onDismissRequest = { isEditingGroup = false },
            title = { Text("Название группы") },
            text = {
                OutlinedTextField(
                    value = groupNameDraft,
                    onValueChange = { groupNameDraft = it },
                    label = { Text("Название") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val cleanName = groupNameDraft.trim()
                        if (cleanName.isNotBlank()) {
                            onRenameGroup(cleanName)
                            isEditingGroup = false
                        }
                    },
                    enabled = groupNameDraft.isNotBlank(),
                ) {
                    Text("Сохранить")
                }
            },
            dismissButton = {
                TextButton(onClick = { isEditingGroup = false }) {
                    Text("Отмена")
                }
            },
        )
    }

    if (confirmArchiveGroup) {
        AlertDialog(
            onDismissRequest = { confirmArchiveGroup = false },
            title = { Text("Удалить группу?") },
            text = {
                Text("Будут архивированы все активные счета группы «$displayName»: ${activeAccountIds.size} ${pluralItems(activeAccountIds.size)}.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmArchiveGroup = false
                        onArchiveGroup(activeAccountIds)
                    },
                ) {
                    Text("Удалить")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmArchiveGroup = false }) {
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
    var selectedMode by rememberSaveable(mode, householdId) {
        mutableStateOf(if (mode == FinanceMode.Shared && !householdId.isNullOrBlank()) FinanceMode.Shared else FinanceMode.Personal)
    }
    var currency by rememberSaveable { mutableStateOf("RUB") }
    var manualAmount by rememberSaveable { mutableStateOf("0") }
    var isInvestment by rememberSaveable { mutableStateOf(false) }
    var assetKind by rememberSaveable { mutableStateOf(AssetKind.Bank) }
    val modeOptions = if (householdId.isNullOrBlank()) {
        listOf(FinanceMode.Personal)
    } else {
        listOf(FinanceMode.Personal, FinanceMode.Shared)
    }

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
            Text("Доступ", style = MaterialTheme.typography.labelLarge)
            ChipRow(modeOptions, selectedMode, { selectedMode = it }, { it.title }, { it.icon() })
            Text("Тип актива", style = MaterialTheme.typography.labelLarge)
            ChipRow(AssetKind.entries.toList(), assetKind, { assetKind = it }, { it.title }, { it.icon })
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
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Отмена")
                }
                Button(
                    onClick = {
                        onCreate(
                            AssetCategoryCreateRequest(
                                name = name.trim(),
                                scopeType = if (selectedMode == FinanceMode.Shared) "household" else "personal",
                                householdId = if (selectedMode == FinanceMode.Shared) householdId else null,
                                currency = currency,
                                manualAmount = manualAmount.normalizedBalanceAmount() ?: "0",
                                isInvestment = isInvestment,
                                assetType = assetKind.apiValue,
                            ),
                        )
                    },
                    enabled = name.isNotBlank() && manualAmount.normalizedBalanceAmount() != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Создать")
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

@Composable
private fun AnalyticsSummaryCard(view: DashboardView) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Аналитика", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            MetricLine("Доходы", view.monthIncome.formatMoney(view.primaryCurrency), Color(0xFF2E7D62))
            MetricLine("Расходы", view.monthExpenses.formatMoney(view.primaryCurrency), Color(0xFFE35D4F))
            MetricLine("Переводы", view.transferTotal.formatMoney(view.primaryCurrency), Color(0xFF5B6EE1))
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
                categories.take(5).forEach { category ->
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
    hasHousehold: Boolean,
    onAddCategory: (String, QuickEntryType, FinanceMode) -> Unit,
    onUpdateCategory: (CategorySummary, String) -> Unit,
    onArchiveCategory: (String) -> Unit,
) {
    var type by rememberSaveable { mutableStateOf(QuickEntryType.Expense) }
    var mode by rememberSaveable { mutableStateOf(FinanceMode.Personal) }
    var newCategoryName by rememberSaveable { mutableStateOf("") }
    val categoryTypes = listOf(QuickEntryType.Expense, QuickEntryType.Income)
    val modeOptions = if (hasHousehold) listOf(FinanceMode.Personal, FinanceMode.Shared) else listOf(FinanceMode.Personal)
    val visibleCategories = categories
        .filter { it.status == "active" }
        .sortedWith(compareBy<CategorySummary> { it.type }.thenBy { it.displayName() })

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
                    Text("Категории", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("Добавление, список и быстрые правки", style = MaterialTheme.typography.bodySmall)
                }
            }

            Text("Тип", style = MaterialTheme.typography.labelLarge)
            ChipRow(categoryTypes, type, { type = it }, { it.title }, { it.icon() })
            Text("Режим", style = MaterialTheme.typography.labelLarge)
            ChipRow(modeOptions, mode, { mode = it }, { it.title }, { it.icon() })

            OutlinedTextField(
                value = newCategoryName,
                onValueChange = { newCategoryName = it },
                label = { Text("Название категории") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = {
                    onAddCategory(newCategoryName.trim(), type, mode)
                    newCategoryName = ""
                },
                enabled = isAuthenticated && newCategoryName.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Добавить категорию")
            }

            if (visibleCategories.isEmpty()) {
                Text("Категорий пока нет", style = MaterialTheme.typography.bodySmall)
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
                Text(
                    text = "${category.localizedType()} • ${category.localizedScope()}",
                    style = MaterialTheme.typography.labelSmall,
                )
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
            Text(
                text = "Доступ: ${category.localizedScope()}. Изменяется только при создании категории.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(8.dp))
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddAccountSheet(
    kind: AssetKind,
    onDismiss: () -> Unit,
    onSubmit: (String, String, String) -> Unit,
) {
    var name by rememberSaveable { mutableStateOf("") }
    var balance by rememberSaveable { mutableStateOf("") }
    var currency by rememberSaveable { mutableStateOf("RUB") }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
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
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = balance,
                onValueChange = { balance = it },
                label = { Text("Начальный баланс") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
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
                        onSubmit(name.trim().ifBlank { kind.title }, cleanBalance, currency)
                    },
                    enabled = name.isNotBlank() || balance.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Создать")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuickAddSheet(
    sheetKey: Int,
    dashboard: FinanceDashboard?,
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
    var visibility by rememberSaveable(sheetKey) { mutableStateOf(FinanceMode.Personal) }
    val accounts = dashboard?.accounts.orEmpty().filter { it.status == "active" }
    val categories = dashboard?.categories.orEmpty().filter { it.type == type.apiValue && it.status == "active" }
    val firstAccountId = accounts.firstOrNull()?.id.orEmpty()
    val firstCategoryId = categories.firstOrNull()?.id.orEmpty()

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp)
                .testTag("quick-add-sheet"),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Добавить", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = amount,
                onValueChange = { amount = it.filter { char -> char.isDigit() || char == '.' || char == ',' } },
                label = { Text("Сумма") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            ChipRow(QuickEntryType.entries.toList(), type, { type = it }, { it.title }, { it.icon() })
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
                    accounts = accounts,
                    selectedId = accountId.ifBlank { firstAccountId },
                    onSelected = { accountId = it },
                )
                if (type == QuickEntryType.Transfer) {
                    AccountPicker(
                        title = "На счет",
                        accounts = accounts.filter { it.id != accountId.ifBlank { firstAccountId } },
                        selectedId = destinationAccountId,
                        onSelected = { destinationAccountId = it },
                    )
                }
                if (type != QuickEntryType.Transfer && categories.isNotEmpty()) {
                    CategoryPicker(
                        categories = categories,
                        selectedId = categoryId.ifBlank { firstCategoryId },
                        onSelected = { categoryId = it },
                    )
                }
            }
            ChipRow(FinanceMode.entries.toList(), visibility, { visibility = it }, { it.title }, { it.icon() })
            Text("Сегодня", style = MaterialTheme.typography.bodySmall)
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
                                accountId = accountId.ifBlank { firstAccountId },
                                destinationAccountId = destinationAccountId,
                                categoryId = categoryId.ifBlank { firstCategoryId },
                                assetKind = assetKind,
                                visibility = visibility,
                            ),
                        )
                    },
                    enabled = amount.normalizedAmount() != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Сохранить")
                }
            }
        }
    }
}

@Composable
private fun <T> ChipRow(
    values: List<T>,
    selected: T,
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

@Composable
private fun AccountPicker(
    title: String,
    accounts: List<AccountSummary>,
    selectedId: String,
    onSelected: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge)
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

@Composable
private fun CategoryPicker(
    categories: List<CategorySummary>,
    selectedId: String,
    onSelected: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Категория", style = MaterialTheme.typography.labelLarge)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(categories) { category ->
                FilterChip(
                    selected = selectedId == category.id,
                    onClick = { onSelected(category.id) },
                    label = { Text(category.displayName()) },
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
                when (val dashboardResult = apiClient.dashboard()) {
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

data class QuickAddDraft(
    val amount: String,
    val type: QuickEntryType,
    val accountId: String,
    val destinationAccountId: String,
    val categoryId: String,
    val assetKind: AssetKind,
    val visibility: FinanceMode,
)

data class AddAccountState(
    val kind: AssetKind,
    val mode: FinanceMode,
    val assetCategoryId: String? = null,
)

enum class FinanceMode(val title: String) {
    Personal("Личное"),
    Shared("Общее"),
    Overview("Обзор"),
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
    val view = dashboard.viewFor(FinanceMode.Overview)
    return when (section) {
        AppSection.Home -> listOf(
            SectionCard("Капитал", view.capital.formatMoney(view.primaryCurrency), "${view.accountCount} активов"),
            SectionCard("Расходы месяца", view.monthExpenses.formatMoney(view.primaryCurrency), "переводы отдельно"),
        )
        AppSection.Operations -> dashboard?.transactions.orEmpty().map {
            SectionCard(it.displayDescription(), it.signedAmount(), it.occurredAt.take(10))
        }
        AppSection.Assets -> view.assetSummaries.map {
            SectionCard(it.kind.title, it.balance.formatMoney(it.currency), "${it.count} шт.")
        }
        AppSection.Categories -> dashboard?.categories.orEmpty().map {
            SectionCard(it.displayName(), it.localizedType(), it.localizedScope())
        }.ifEmpty {
            listOf(SectionCard("Категории", "Нет категорий", "пусто"))
        }
        AppSection.Analytics -> view.topCategories.map {
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
    val transactions = dashboard?.transactions.orEmpty()
        .filter { tx -> tx.matchesMode(mode, accountIds) }
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
        primaryCurrency = currency,
        capital = accounts.fold(BigDecimal.ZERO) { total, account -> total + account.currentBalance.toMoney() },
        monthIncome = income,
        monthExpenses = expenses,
        transferTotal = transferTotal,
        accountCount = accounts.size,
        operationCount = transactions.size,
        assetSummaries = assetSummaries(accounts),
        topCategories = topCategories(transactions, dashboard?.categories.orEmpty(), currency),
        recentTransactions = transactions.sortedByDescending { it.occurredAt }.take(6),
    )
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
                currency = category.currency,
                scopeTitle = category.scopeType.assetScopeTitle(),
            )
        }
    return (rowsFromGroups + emptyCategoryRows).sortedWith(compareBy<AssetCategoryUiRow> { it.scopeTitle }.thenBy { it.category.name })
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

private fun TransactionSummary.matchesMode(mode: FinanceMode, accountIds: Set<String>): Boolean {
    if (mode == FinanceMode.Overview) {
        return accountId in accountIds || counterpartyAccountId in accountIds
    }
    if (type == "transfer") {
        return accountId in accountIds && counterpartyAccountId in accountIds
    }
    return accountId in accountIds
}

internal fun transferPairValidationMessage(
    source: AccountSummary?,
    destination: AccountSummary?,
): String? {
    if (source == null || destination == null) {
        return "Нужны два счета для перевода"
    }
    if (source.id == destination.id) {
        return "Выберите два разных счета"
    }
    if (source.currency != destination.currency) {
        return "Перевод между разными валютами недоступен"
    }
    if (source.ownershipType != destination.ownershipType) {
        return "Перевод между личным и общим недоступен. Выберите счета одного режима."
    }
    if (
        source.ownershipType == "shared" &&
        source.householdId.orEmpty() != destination.householdId.orEmpty()
    ) {
        return "Перевод между разными общими бюджетами недоступен"
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
    "transfer" -> Color(0xFF5B6EE1)
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
    )
}

private fun String.assetKindOrBank(): AssetKind {
    return AssetKind.entries.firstOrNull { it.apiValue == this } ?: AssetKind.Bank
}

private fun String.assetScopeTitle(): String {
    return if (this == "household") "Общее" else "Личное"
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

private fun CategorySummary.localizedScope(): String = if (scope == "household") "Общее" else "Личное"

private fun TransactionSummary.displayDescription(): String {
    return userFacingSeedText(description).ifBlank { localizedType() }
}

private fun String.localizedCaptureSource(): String = when (this) {
    "screenshot_ocr" -> "Скриншот"
    "manual" -> "Ручной ввод"
    else -> "Импорт"
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

@Preview(showBackground = true, widthDp = 390)
@Composable
private fun FinanceAppPreview() {
    FinanceTheme {
        FinanceApp(apiClient = PreviewFinanceApiClient())
    }
}

private class PreviewFinanceApiClient : FinanceApiClient {
    override val config: ApiConfig = ApiConfig("http://10.0.2.2:8000")

    override suspend fun login(email: String, password: String): ApiResult<SessionStatus> {
        return sessionStatus()
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> {
        return ApiResult.Success(SessionStatus(true, "Пользователь", "household"))
    }

    override suspend fun dashboard(): ApiResult<FinanceDashboard> {
        val session = SessionStatus(true, "Пользователь", "household")
        return ApiResult.Success(previewDashboard(session))
    }

    override suspend fun createDemoAccount(
        householdId: String?,
        currency: String,
        initialBalance: String,
        accountType: String,
        ownershipType: String,
    ): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Новый актив", accountType, ownershipType, currency, initialBalance, id = "acc-created", householdId = householdId, version = 1))
    }

    override suspend fun createAccount(
        name: String,
        currency: String,
        initialBalance: String,
        accountType: String,
        householdId: String?,
        assetCategoryId: String?,
    ): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary(name, accountType, if (householdId.isNullOrBlank()) "personal" else "shared", currency, initialBalance, id = "acc-created", householdId = householdId, assetCategoryId = assetCategoryId, version = 1))
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
    ): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary(transactionType, amount, account.currency, "2026-05-18T09:00:00Z", category?.name ?: "Новая операция", null, null, id = "txn-created", accountId = account.id, categoryId = category?.id, version = 1))
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
    ): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary("transfer", amount, source.currency, "2026-05-18T09:00:00Z", "Между счетами", "personal_same_owner", "posted", id = "txn-transfer-created", accountId = source.id, counterpartyAccountId = destination.id, version = 1))
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
