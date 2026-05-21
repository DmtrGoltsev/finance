package com.finance.mvp.ui

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.annotation.DrawableRes
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
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
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.ImportReportPreviewRequest
import com.finance.mvp.api.ImportReportPreviewResponse
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import com.finance.mvp.api.userFacingSeedText
import com.finance.mvp.ui.theme.FinanceTheme
import java.math.BigDecimal
import java.math.RoundingMode
import java.text.NumberFormat
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinanceApp(
    apiClient: FinanceApiClient,
    modifier: Modifier = Modifier,
) {
    var selectedSection by rememberSaveable { mutableStateOf(AppSection.Home) }
    var selectedMode by rememberSaveable { mutableStateOf(FinanceMode.Personal) }
    var showQuickAdd by rememberSaveable { mutableStateOf(false) }
    var quickAddOpenKey by rememberSaveable { mutableStateOf(0) }
    var quickAddError by rememberSaveable { mutableStateOf<String?>(null) }
    var loginEmail by rememberSaveable { mutableStateOf("") }
    var loginPassword by rememberSaveable { mutableStateOf("") }
    var uiState by remember { mutableStateOf(FinanceUiState()) }
    val scope = rememberCoroutineScope()
    val sections = financeSections()

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
                        FinanceUiState(message = "Войдите, чтобы увидеть финансы")
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
                        val category = dashboard.categories.quickAddCategoryFor(
                            categoryId = draft.categoryId,
                            transactionType = draft.type.apiValue,
                        )
                        if (account == null) {
                            ApiResult.Failure("Нужен счет")
                        } else {
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
                        val currency = dashboard.accounts.firstOrNull()?.currency ?: "USD"
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
            if (uiState.session?.isAuthenticated != true || dashboard == null) {
                item {
                    SignInCard(
                        state = uiState,
                        email = loginEmail,
                        password = loginPassword,
                        onEmailChange = { loginEmail = it },
                        onPasswordChange = { loginPassword = it },
                        onLogin = { login(loginEmail, loginPassword) },
                    )
                }
            }

            when (selectedSection) {
                AppSection.Home -> homeContent(dashboard, selectedMode) { selectedMode = it }
                AppSection.Operations -> operationsContent(dashboard)
                AppSection.Assets -> assetsContent(dashboard)
                AppSection.Categories -> categoriesContent(
                    dashboard = dashboard,
                    onAddCategory = { type, mode ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Добавляем категорию")
                            val result = withContext(Dispatchers.IO) {
                                apiClient.createDemoCategory(
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
                    onEditCategory = { category ->
                        scope.launch {
                            uiState = uiState.copy(isLoading = true, message = "Обновляем категорию")
                            val result = withContext(Dispatchers.IO) { apiClient.updateCategory(category) }
                            when (result) {
                                is ApiResult.Success -> loadDashboard("Категория обновлена")
                                is ApiResult.Failure -> uiState = uiState.copy(
                                    isLoading = false,
                                    message = result.userFacingMessage(),
                                )
                            }
                        }
                    },
                )
                AppSection.Analytics -> analyticsContent(dashboard, selectedMode) { selectedMode = it }
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
}

internal data class LoginCredentials(
    val email: String,
    val password: String,
)

internal fun loginCredentialsOrNull(email: String, password: String): LoginCredentials? {
    val normalizedEmail = email.trim()
    return LoginCredentials(normalizedEmail, password)
        .takeIf { it.email.isNotBlank() && it.password.isNotBlank() }
}

@Composable
private fun SignInCard(
    state: FinanceUiState,
    email: String,
    password: String,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onLogin: () -> Unit,
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
            OutlinedTextField(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("login-email-field"),
                value = email,
                onValueChange = onEmailChange,
                label = { Text("Email") },
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                Button(
                    modifier = Modifier.testTag("login-submit-button"),
                    onClick = onLogin,
                    enabled = !state.isLoading,
                ) {
                    Text("Войти")
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

private fun LazyListScope.operationsContent(dashboard: FinanceDashboard?) {
    val items = dashboard?.transactions.orEmpty()
    if (items.isEmpty()) {
        item { EmptyState("Операций пока нет") }
        return
    }
    item { Text("Операции", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
    items(items.sortedByDescending { it.occurredAt }) { transaction ->
        TransactionRow(transaction, dashboard?.categories.orEmpty())
    }
}

private fun LazyListScope.assetsContent(dashboard: FinanceDashboard?) {
    val summaries = assetSummaries(dashboard?.accounts.orEmpty())
    item { Text("Активы", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
    items(summaries) { summary ->
        AssetKindRow(summary)
    }
    if (dashboard?.accounts.isNullOrEmpty()) {
        item { EmptyState("Активов пока нет") }
    }
}

private fun LazyListScope.categoriesContent(
    dashboard: FinanceDashboard?,
    onAddCategory: (QuickEntryType, FinanceMode) -> Unit,
    onEditCategory: (CategorySummary) -> Unit,
) {
    item {
        CategoryManagementCard(
            categories = dashboard?.categories.orEmpty(),
            isAuthenticated = dashboard?.session?.isAuthenticated == true,
            onAddCategory = onAddCategory,
            onEditCategory = onEditCategory,
        )
    }
}

private fun LazyListScope.analyticsContent(
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
    item { AnalyticsSummaryCard(view) }
    item { ImportReportPlaceholderCard() }
    item { CategoryBreakdownCard(view.topCategories) }
    item { CapitalBreakdownCard(view.assetSummaries) }
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
private fun AssetKindRow(summary: AssetSummary) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBubble(summary.kind.icon, summary.kind.tint)
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(summary.kind.title, fontWeight = FontWeight.SemiBold)
                Text("${summary.count} шт.", style = MaterialTheme.typography.bodySmall)
            }
            Text(summary.balance.formatMoney(summary.currency), fontWeight = FontWeight.SemiBold)
        }
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
private fun ImportReportPlaceholderCard() {
    var reportType by rememberSaveable { mutableStateOf(ImportReportType.Generic) }
    var fileName by rememberSaveable { mutableStateOf("report.pdf") }
    var targetScope by rememberSaveable { mutableStateOf(ImportTargetScope.Personal) }
    var showPreview by rememberSaveable { mutableStateOf(true) }
    val draft = ImportReportDraft(
        reportType = reportType,
        fileName = fileName.ifBlank { "report.pdf" },
        targetScope = targetScope,
    )
    val preview = importReportPlaceholderPreview(draft)

    ElevatedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("import-report-placeholder"),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(R.drawable.ic_receipt_24, Color(0xFF227C9D), size = 36)
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("Импорт отчета", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("Показана только предварительная сводка", style = MaterialTheme.typography.bodySmall)
                }
            }

            Text("Тип отчета", style = MaterialTheme.typography.labelLarge)
            ChipRow(
                values = ImportReportType.entries.toList(),
                selected = reportType,
                onSelected = { reportType = it },
                title = { it.title },
                icon = { it.icon() },
            )

            OutlinedTextField(
                value = fileName,
                onValueChange = { fileName = it.take(255) },
                label = { Text("Имя файла-заглушка") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Text("Режим видимости", style = MaterialTheme.typography.labelLarge)
            ChipRow(
                values = ImportTargetScope.entries.toList(),
                selected = targetScope,
                onSelected = { targetScope = it },
                title = { it.title },
                icon = { it.icon() },
            )

            Button(
                onClick = { showPreview = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Показать сводку")
            }

            if (showPreview) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(preview.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    AssistChip(
                        onClick = {},
                        label = { Text(preview.statusText) },
                        leadingIcon = {
                            Icon(
                                painter = painterResource(R.drawable.ic_receipt_24),
                                contentDescription = null,
                                modifier = Modifier.size(18.dp),
                            )
                        },
                    )
                    Text(preview.fileStatusText, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                    Text(preview.summaryText, style = MaterialTheme.typography.bodySmall)
                    Text(preview.scopeText, style = MaterialTheme.typography.bodySmall)
                    Text("Что сможет распознать импорт", style = MaterialTheme.typography.labelLarge)
                    preview.sections.forEach { section ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(section.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                            Text(section.text, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    Text("Перед импортом", style = MaterialTheme.typography.labelLarge)
                    preview.warnings.forEach { warning ->
                        MetricLine(warning, " ", Color(0xFF8A6A12))
                    }
                    OutlinedButton(
                        onClick = {},
                        enabled = preview.canConfirm,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Подтверждение пока недоступно")
                    }
                }
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
    onAddCategory: (QuickEntryType, FinanceMode) -> Unit,
    onEditCategory: (CategorySummary) -> Unit,
) {
    var type by rememberSaveable { mutableStateOf(QuickEntryType.Expense) }
    var mode by rememberSaveable { mutableStateOf(FinanceMode.Personal) }
    val categoryTypes = listOf(QuickEntryType.Expense, QuickEntryType.Income)
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
            ChipRow(listOf(FinanceMode.Personal, FinanceMode.Shared), mode, { mode = it }, { it.title }, { it.icon() })

            Button(
                onClick = { onAddCategory(type, mode) },
                enabled = isAuthenticated,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Добавить категорию")
            }

            if (visibleCategories.isEmpty()) {
                Text("Категорий пока нет", style = MaterialTheme.typography.bodySmall)
            } else {
                visibleCategories.forEach { category ->
                    CategoryManagementRow(category, onEditCategory)
                }
            }
        }
    }
}

@Composable
private fun CategoryManagementRow(
    category: CategorySummary,
    onEditCategory: (CategorySummary) -> Unit,
) {
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
        TextButton(onClick = { onEditCategory(category) }) {
            Text("Изменить")
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
    val accounts = dashboard?.accounts.orEmpty()
    val categories = dashboard?.categories.orEmpty().filter { it.type == type.apiValue }
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
                    enabled = amount.normalizedAmount() != null && (type == QuickEntryType.Asset || accounts.isNotEmpty()),
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
    Metal("Металл", "metal", R.drawable.ic_coin_24, Color(0xFF8A6A12)),
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
    val accounts = dashboard?.accounts.orEmpty().filterByMode(mode)
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
        return true
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

@DrawableRes
private fun ImportReportType.icon(): Int = when (this) {
    ImportReportType.Generic -> R.drawable.ic_receipt_24
    ImportReportType.Bank -> R.drawable.ic_bank_24
    ImportReportType.Broker -> R.drawable.ic_chart_24
    ImportReportType.Deposit -> R.drawable.ic_savings_24
    ImportReportType.Metals -> R.drawable.ic_coin_24
}

@DrawableRes
private fun ImportTargetScope.icon(): Int = when (this) {
    ImportTargetScope.Personal -> R.drawable.ic_person_24
    ImportTargetScope.Shared -> R.drawable.ic_group_24
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

private fun ApiResult.Failure.userFacingMessage(): String {
    return when {
        message.contains("счет", ignoreCase = true) -> message
        message.contains("сумм", ignoreCase = true) -> message
        message.contains("перевод", ignoreCase = true) -> message
        message.contains("валют", ignoreCase = true) -> message
        message.contains("режим", ignoreCase = true) -> message
        else -> "Не удалось выполнить действие"
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

    override suspend fun previewImportReport(request: ImportReportPreviewRequest): ApiResult<ImportReportPreviewResponse> {
        return ApiResult.Success(
            ImportReportPreviewResponse(
                status = "preview_placeholder",
                canConfirm = false,
                willChangeData = false,
                message = "Файл не импортирован. Сейчас показана только предварительная сводка.",
            ),
        )
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
