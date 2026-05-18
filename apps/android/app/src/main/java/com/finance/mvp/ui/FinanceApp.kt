package com.finance.mvp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.MoneyTotal
import com.finance.mvp.api.SessionStatus
import com.finance.mvp.api.TransactionSummary
import com.finance.mvp.ui.theme.FinanceTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val DemoEmail = "demo.owner@example.test"
private const val DemoPassword = "demo-password-only"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinanceApp(
    apiClient: FinanceApiClient,
    modifier: Modifier = Modifier,
) {
    var selectedSection by rememberSaveable { mutableStateOf(AppSection.Overview) }
    var uiState by remember { mutableStateOf(FinanceUiState(apiUrl = apiClient.config.normalizedBaseUrl)) }
    var createdAccountId by rememberSaveable { mutableStateOf<String?>(null) }
    var archivedAccountId by rememberSaveable { mutableStateOf<String?>(null) }
    var createdCategoryId by rememberSaveable { mutableStateOf<String?>(null) }
    var archivedCategoryId by rememberSaveable { mutableStateOf<String?>(null) }
    var lifecycleTransactionId by rememberSaveable { mutableStateOf<String?>(null) }
    var deletedTransactionId by rememberSaveable { mutableStateOf<String?>(null) }
    var lifecycleTransferId by rememberSaveable { mutableStateOf<String?>(null) }
    var deletedTransferId by rememberSaveable { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val sections = mvpSections()

    fun loadDashboard(successMessage: String = "Данные загружены из live API") {
        scope.launch {
            uiState = uiState.copy(isLoading = true, message = "Обновляем данные...")
            uiState = when (val result = withContext(Dispatchers.IO) { apiClient.dashboard() }) {
                is ApiResult.Success -> FinanceUiState(
                    apiUrl = apiClient.config.normalizedBaseUrl,
                    session = result.value.session,
                    dashboard = result.value,
                    message = successMessage,
                )
                is ApiResult.Failure -> uiState.copy(
                    isLoading = false,
                    message = result.message,
                )
            }
        }
    }

    fun refresh() {
        loadDashboard()
    }

    fun <T> runLifecycleAction(
        loadingMessage: String,
        successMessage: String,
        action: suspend () -> ApiResult<T>,
        onSuccess: (T) -> Unit = {},
    ) {
        scope.launch {
            uiState = uiState.copy(isLoading = true, message = loadingMessage)
            when (val result = withContext(Dispatchers.IO) { action() }) {
                is ApiResult.Success -> {
                    onSuccess(result.value)
                    when (val dashboard = withContext(Dispatchers.IO) { apiClient.dashboard() }) {
                        is ApiResult.Success -> uiState = FinanceUiState(
                            apiUrl = apiClient.config.normalizedBaseUrl,
                            session = dashboard.value.session,
                            dashboard = dashboard.value,
                            message = successMessage,
                        )
                        is ApiResult.Failure -> uiState = uiState.copy(
                            isLoading = false,
                            message = "$successMessage; обновление списка не удалось: ${dashboard.message}",
                        )
                    }
                }
                is ApiResult.Failure -> uiState = uiState.copy(isLoading = false, message = result.message)
            }
        }
    }

    fun loginDemo() {
        scope.launch {
            uiState = uiState.copy(isLoading = true, message = "Входим в демо-сессию...")
            when (val login = withContext(Dispatchers.IO) { apiClient.login(DemoEmail, DemoPassword) }) {
                is ApiResult.Success -> loadDashboard()
                is ApiResult.Failure -> uiState = uiState.copy(isLoading = false, message = login.message)
            }
        }
    }

    LaunchedEffect(apiClient) {
        when (val result = withContext(Dispatchers.IO) { apiClient.sessionStatus() }) {
            is ApiResult.Success -> uiState = uiState.copy(
                session = result.value,
                message = "Сессия найдена, можно обновить данные",
            )
            is ApiResult.Failure -> uiState = uiState.copy(message = "Нужен вход в демо-сессию")
        }
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Финансы MVP")
                        Text(
                            text = "API: ${uiState.apiUrl}",
                            style = MaterialTheme.typography.labelSmall,
                        )
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
                        icon = { Text(section.title.take(1)) },
                        label = { Text(section.title) },
                    )
                }
            }
        },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                SessionShell(
                    state = uiState,
                    onLogin = ::loginDemo,
                    onRefresh = ::refresh,
                )
            }
            item {
                SectionHeader(selectedSection)
            }
            lifecyclePanel(
                section = selectedSection,
                state = uiState,
                createdAccountId = createdAccountId,
                archivedAccountId = archivedAccountId,
                createdCategoryId = createdCategoryId,
                archivedCategoryId = archivedCategoryId,
                lifecycleTransactionId = lifecycleTransactionId,
                deletedTransactionId = deletedTransactionId,
                lifecycleTransferId = lifecycleTransferId,
                deletedTransferId = deletedTransferId,
                onCreateAccount = {
                    val currency = uiState.dashboard?.accounts?.firstOrNull()?.currency ?: "USD"
                    runLifecycleAction(
                        loadingMessage = "Создаем счет через live API...",
                        successMessage = "Счет создан через native Android control",
                        action = { apiClient.createDemoAccount(uiState.session?.householdId, currency) },
                        onSuccess = { createdAccountId = it.id; archivedAccountId = null },
                    )
                },
                onUpdateAccount = {
                    targetAccountById(uiState.dashboard?.accounts, createdAccountId)
                        ?.let { account ->
                            runLifecycleAction(
                                loadingMessage = "Обновляем счет...",
                                successMessage = "Счет обновлен через PATCH",
                                action = { apiClient.updateAccount(account) },
                                onSuccess = { createdAccountId = it.id },
                            )
                        }
                },
                onArchiveAccount = {
                    targetAccountById(uiState.dashboard?.accounts, createdAccountId)
                        ?.let { account ->
                            runLifecycleAction(
                                loadingMessage = "Архивируем счет...",
                                successMessage = "Счет архивирован",
                                action = { apiClient.archiveAccount(account.id) },
                                onSuccess = { archivedAccountId = it.id; createdAccountId = null },
                            )
                        }
                },
                onRestoreAccount = {
                    archivedAccountId?.let { accountId ->
                        runLifecycleAction(
                            loadingMessage = "Восстанавливаем счет...",
                            successMessage = "Счет восстановлен",
                            action = { apiClient.restoreAccount(accountId) },
                            onSuccess = { createdAccountId = it.id; archivedAccountId = null },
                        )
                    }
                },
                onCreateCategory = {
                    runLifecycleAction(
                        loadingMessage = "Создаем категорию...",
                        successMessage = "Категория создана через native Android control",
                        action = { apiClient.createDemoCategory(uiState.session?.householdId) },
                        onSuccess = { createdCategoryId = it.id; archivedCategoryId = null },
                    )
                },
                onUpdateCategory = {
                    targetCategoryById(uiState.dashboard?.categories, createdCategoryId)
                        ?.let { category ->
                            runLifecycleAction(
                                loadingMessage = "Обновляем категорию...",
                                successMessage = "Категория обновлена через PATCH",
                                action = { apiClient.updateCategory(category) },
                                onSuccess = { createdCategoryId = it.id },
                            )
                        }
                },
                onArchiveCategory = {
                    targetCategoryById(uiState.dashboard?.categories, createdCategoryId)
                        ?.let { category ->
                            runLifecycleAction(
                                loadingMessage = "Архивируем категорию...",
                                successMessage = "Категория архивирована",
                                action = { apiClient.archiveCategory(category.id) },
                                onSuccess = { archivedCategoryId = it.id; createdCategoryId = null },
                            )
                        }
                },
                onRestoreCategory = {
                    archivedCategoryId?.let { categoryId ->
                        runLifecycleAction(
                            loadingMessage = "Восстанавливаем категорию...",
                            successMessage = "Категория восстановлена",
                            action = { apiClient.restoreCategory(categoryId) },
                            onSuccess = { createdCategoryId = it.id; archivedCategoryId = null },
                        )
                    }
                },
                onCreateTransaction = {
                    val account = uiState.dashboard?.accounts?.firstOrNull { it.id.isNotBlank() }
                    val category = account?.let { compatibleExpenseCategory(it, uiState.dashboard?.categories.orEmpty()) }
                    if (account != null) {
                        runLifecycleAction(
                            loadingMessage = "Создаем операцию...",
                            successMessage = "Операция создана через live API",
                            action = { apiClient.createDemoTransaction(account, category) },
                            onSuccess = { lifecycleTransactionId = it.id; deletedTransactionId = null },
                        )
                    }
                },
                onUpdateTransaction = {
                    targetTransaction(uiState.dashboard?.transactions, lifecycleTransactionId, includeTransfers = false)
                        ?.let { transaction ->
                            runLifecycleAction(
                                loadingMessage = "Обновляем операцию...",
                                successMessage = "Операция обновлена через PATCH",
                                action = { apiClient.updateTransaction(transaction) },
                                onSuccess = { lifecycleTransactionId = it.id },
                            )
                        }
                },
                onDeleteTransaction = {
                    targetTransaction(uiState.dashboard?.transactions, lifecycleTransactionId, includeTransfers = false)
                        ?.let { transaction ->
                            runLifecycleAction(
                                loadingMessage = "Удаляем операцию...",
                                successMessage = "Операция удалена soft-delete",
                                action = { apiClient.deleteTransaction(transaction.id) },
                                onSuccess = { deletedTransactionId = transaction.id; lifecycleTransactionId = null },
                            )
                        }
                },
                onRestoreTransaction = {
                    deletedTransactionId?.let { transactionId ->
                        runLifecycleAction(
                            loadingMessage = "Восстанавливаем операцию...",
                            successMessage = "Операция восстановлена",
                            action = { apiClient.restoreTransaction(transactionId) },
                            onSuccess = { lifecycleTransactionId = it.id; deletedTransactionId = null },
                        )
                    }
                },
                onCreateTransfer = {
                    compatibleTransferPair(uiState.dashboard?.accounts.orEmpty())?.let { (source, destination) ->
                        runLifecycleAction(
                            loadingMessage = "Создаем перевод...",
                            successMessage = "Перевод создан через transactionType=transfer",
                            action = { apiClient.createDemoTransfer(source, destination) },
                            onSuccess = { lifecycleTransferId = it.id; deletedTransferId = null },
                        )
                    }
                },
                onUpdateTransfer = {
                    targetTransaction(uiState.dashboard?.transactions, lifecycleTransferId, includeTransfers = true)
                        ?.let { transfer ->
                            runLifecycleAction(
                                loadingMessage = "Обновляем перевод...",
                                successMessage = "Перевод обновлен",
                                action = { apiClient.updateTransaction(transfer) },
                                onSuccess = { lifecycleTransferId = it.id },
                            )
                        }
                },
                onDeleteTransfer = {
                    targetTransaction(uiState.dashboard?.transactions, lifecycleTransferId, includeTransfers = true)
                        ?.let { transfer ->
                            runLifecycleAction(
                                loadingMessage = "Удаляем перевод...",
                                successMessage = "Перевод удален soft-delete",
                                action = { apiClient.deleteTransaction(transfer.id) },
                                onSuccess = { deletedTransferId = transfer.id; lifecycleTransferId = null },
                            )
                        }
                },
                onRestoreTransfer = {
                    deletedTransferId?.let { transactionId ->
                        runLifecycleAction(
                            loadingMessage = "Восстанавливаем перевод...",
                            successMessage = "Перевод восстановлен",
                            action = { apiClient.restoreTransaction(transactionId) },
                            onSuccess = { lifecycleTransferId = it.id; deletedTransferId = null },
                        )
                    }
                },
            )
            items(sectionCards(selectedSection, uiState.dashboard)) { card ->
                MvpCard(card)
            }
        }
    }
}

@Composable
private fun SessionShell(
    state: FinanceUiState,
    onLogin: () -> Unit,
    onRefresh: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Сессия",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(state.session?.displayName ?: "Вход не выполнен")
            Text(state.message)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onLogin,
                    enabled = !state.isLoading,
                ) {
                    Text("Войти демо")
                }
                OutlinedButton(
                    onClick = onRefresh,
                    enabled = !state.isLoading && state.session?.isAuthenticated == true,
                ) {
                    Text("Обновить")
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(section: AppSection) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = section.title,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            text = section.subtitle,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private fun LazyListScope.lifecyclePanel(
    section: AppSection,
    state: FinanceUiState,
    createdAccountId: String?,
    archivedAccountId: String?,
    createdCategoryId: String?,
    archivedCategoryId: String?,
    lifecycleTransactionId: String?,
    deletedTransactionId: String?,
    lifecycleTransferId: String?,
    deletedTransferId: String?,
    onCreateAccount: () -> Unit,
    onUpdateAccount: () -> Unit,
    onArchiveAccount: () -> Unit,
    onRestoreAccount: () -> Unit,
    onCreateCategory: () -> Unit,
    onUpdateCategory: () -> Unit,
    onArchiveCategory: () -> Unit,
    onRestoreCategory: () -> Unit,
    onCreateTransaction: () -> Unit,
    onUpdateTransaction: () -> Unit,
    onDeleteTransaction: () -> Unit,
    onRestoreTransaction: () -> Unit,
    onCreateTransfer: () -> Unit,
    onUpdateTransfer: () -> Unit,
    onDeleteTransfer: () -> Unit,
    onRestoreTransfer: () -> Unit,
) {
    val dashboard = state.dashboard
    val authenticated = state.session?.isAuthenticated == true && dashboard != null
    when (section) {
        AppSection.Accounts -> item {
            val hasCreated = targetAccountById(dashboard?.accounts, createdAccountId) != null
            LifecycleCard(
                title = "Lifecycle счета",
                details = "Create/PATCH/archive/restore через /api/v1/accounts. Цель: ${createdAccountId?.take(8) ?: archivedAccountId?.take(8) ?: "нет"}",
                testTag = "accounts-lifecycle-panel",
                buttons = listOf(
                    LifecycleButton("Создать", "create-account", authenticated, onCreateAccount),
                    LifecycleButton("Обновить", "update-account", authenticated && hasCreated, onUpdateAccount),
                    LifecycleButton("Архивировать", "archive-account", authenticated && hasCreated, onArchiveAccount),
                    LifecycleButton("Восстановить", "restore-account", authenticated && archivedAccountId != null, onRestoreAccount),
                ),
            )
        }
        AppSection.Categories -> item {
            val hasCreated = targetCategoryById(dashboard?.categories, createdCategoryId) != null
            LifecycleCard(
                title = "Lifecycle категории",
                details = "Create/PATCH/archive/restore через /api/v1/categories. Цель: ${createdCategoryId?.take(8) ?: archivedCategoryId?.take(8) ?: "нет"}",
                testTag = "categories-lifecycle-panel",
                buttons = listOf(
                    LifecycleButton("Создать", "create-category", authenticated, onCreateCategory),
                    LifecycleButton("Обновить", "update-category", authenticated && hasCreated, onUpdateCategory),
                    LifecycleButton("Архивировать", "archive-category", authenticated && hasCreated, onArchiveCategory),
                    LifecycleButton("Восстановить", "restore-category", authenticated && archivedCategoryId != null, onRestoreCategory),
                ),
            )
        }
        AppSection.Operations -> item {
            val hasTarget = targetTransaction(dashboard?.transactions, lifecycleTransactionId, includeTransfers = false) != null
            val canCreate = dashboard?.accounts?.any { it.id.isNotBlank() } == true
            LifecycleCard(
                title = "CRUD операции",
                details = "Create/PATCH/delete/restore через /api/v1/transactions. Цель: ${lifecycleTransactionId?.take(8) ?: deletedTransactionId?.take(8) ?: "нет"}",
                testTag = "transactions-lifecycle-panel",
                buttons = listOf(
                    LifecycleButton("Создать", "create-transaction", authenticated && canCreate, onCreateTransaction),
                    LifecycleButton("Обновить", "update-transaction", authenticated && hasTarget, onUpdateTransaction),
                    LifecycleButton("Удалить", "delete-transaction", authenticated && hasTarget, onDeleteTransaction),
                    LifecycleButton("Восстановить", "restore-transaction", authenticated && deletedTransactionId != null, onRestoreTransaction),
                ),
            )
        }
        AppSection.Transfers -> item {
            val hasTarget = targetTransaction(dashboard?.transactions, lifecycleTransferId, includeTransfers = true) != null
            val pair = compatibleTransferPair(dashboard?.accounts.orEmpty())
            LifecycleCard(
                title = "Lifecycle перевода",
                details = "Transfer count: ${dashboard?.transferCount ?: 0}; report count: ${dashboard?.reportTransferCount ?: 0}; цель: ${lifecycleTransferId?.take(8) ?: deletedTransferId?.take(8) ?: "нет"}",
                testTag = "transfer-lifecycle-panel",
                buttons = listOf(
                    LifecycleButton("Создать", "create-transfer", authenticated && pair != null, onCreateTransfer),
                    LifecycleButton("Обновить", "update-transfer", authenticated && hasTarget, onUpdateTransfer),
                    LifecycleButton("Удалить", "delete-transfer", authenticated && hasTarget, onDeleteTransfer),
                    LifecycleButton("Восстановить", "restore-transfer", authenticated && deletedTransferId != null, onRestoreTransfer),
                ),
            )
        }
        else -> Unit
    }
}

private data class LifecycleButton(
    val label: String,
    val tag: String,
    val enabled: Boolean,
    val onClick: () -> Unit,
)

@Composable
private fun LifecycleCard(
    title: String,
    details: String,
    testTag: String,
    buttons: List<LifecycleButton>,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(testTag),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(details)
            buttons.chunked(2).forEach { rowButtons ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    rowButtons.forEach { button ->
                        OutlinedButton(
                            modifier = Modifier.testTag(button.tag),
                            onClick = button.onClick,
                            enabled = button.enabled,
                        ) {
                            Text(button.label)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MvpCard(card: SectionCard) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = card.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(card.body)
            Spacer(modifier = Modifier.height(2.dp))
            AssistChip(
                onClick = {},
                label = { Text(card.status) },
            )
        }
    }
}

data class FinanceUiState(
    val apiUrl: String,
    val session: SessionStatus? = null,
    val dashboard: FinanceDashboard? = null,
    val isLoading: Boolean = false,
    val message: String = "Готово к подключению",
)

data class SectionCard(
    val title: String,
    val body: String,
    val status: String,
)

fun sectionCards(section: AppSection, dashboard: FinanceDashboard?): List<SectionCard> {
    return when (section) {
        AppSection.Overview -> overviewCards(dashboard)
        AppSection.Accounts -> dashboard?.accounts?.map(::accountCard) ?: emptyCards("Счета")
        AppSection.Categories -> dashboard?.categories?.map(::categoryCard) ?: emptyCards("Категории")
        AppSection.Operations -> dashboard?.transactions?.map(::transactionCard) ?: emptyCards("Операции")
        AppSection.Transfers -> dashboard?.let(::transferCards) ?: emptyCards("Переводы")
        AppSection.Reports -> dashboard?.let { it.totals.map(::totalCard) + transferReportCard(it) } ?: emptyCards("Отчеты")
    }
}

private fun overviewCards(dashboard: FinanceDashboard?): List<SectionCard> {
    if (dashboard == null) return emptyCards("Обзор")
    val total = dashboard.totals.firstOrNull()
    return listOf(
        SectionCard(
            title = "Итоги",
            body = total?.let {
                "Доходы ${it.incomeTotal} ${it.currency}, расходы ${it.expenseTotal} ${it.currency}, итог ${it.netTotal} ${it.currency}"
            } ?: "Сводка пока без сумм",
            status = "live API",
        ),
        SectionCard(
            title = "Данные",
            body = "Счетов: ${dashboard.accounts.size}; категорий: ${dashboard.categories.size}; операций: ${dashboard.transactions.size}; переводов: ${dashboard.transferCount}",
            status = "обновлено",
        ),
    )
}

private fun accountCard(account: AccountSummary): SectionCard {
    return SectionCard(
        title = account.name,
        body = "${account.currentBalance} ${account.currency}; ${account.type.localizedAccountType()}, ${account.ownershipType.localizedOwnership()}",
        status = "live API",
    )
}

private fun categoryCard(category: CategorySummary): SectionCard {
    return SectionCard(
        title = category.name,
        body = "${category.type.localizedCategoryType()}, ${category.scope.localizedScope()}",
        status = "live API",
    )
}

private fun transactionCard(transaction: TransactionSummary): SectionCard {
    val transferDetails = if (transaction.type == "transfer") {
        "; статус: ${transaction.transferStatus ?: "не указан"}; контур: ${transaction.transferScope ?: "не указан"}"
    } else {
        ""
    }
    return SectionCard(
        title = transaction.type.localizedTransactionType(),
        body = "${transaction.amount} ${transaction.currency}; ${transaction.occurredAt.take(10)}${transaction.description?.let { "; $it" } ?: ""}$transferDetails",
        status = "manual",
    )
}

private fun transferCards(dashboard: FinanceDashboard): List<SectionCard> {
    val transfers = dashboard.transactions.filter { it.type == "transfer" }
    if (transfers.isEmpty()) {
        return listOf(
            SectionCard(
                title = "Переводы",
                body = "В активном live API списке переводов нет.",
                status = "ожидает lifecycle",
            ),
        )
    }
    return transfers.map { transfer ->
        SectionCard(
            title = "Перевод ${transfer.amount} ${transfer.currency}",
            body = "id ${transfer.id.take(8)}; ${transfer.occurredAt.take(10)}; статус ${transfer.transferStatus ?: "не указан"}; контур ${transfer.transferScope ?: "не указан"}",
            status = "transfer row",
        )
    }
}

private fun totalCard(total: MoneyTotal): SectionCard {
    return SectionCard(
        title = "Сводка ${total.currency}",
        body = "Доходы ${total.incomeTotal}; расходы ${total.expenseTotal}; итог ${total.netTotal}",
        status = "live API",
    )
}

private fun transferReportCard(dashboard: FinanceDashboard): SectionCard {
    return SectionCard(
        title = "Переводы в отчете",
        body = "Report transactions transfer count: ${dashboard.reportTransferCount}; live transactions transfer count: ${dashboard.transferCount}",
        status = "live API",
    )
}

private fun emptyCards(title: String): List<SectionCard> {
    return listOf(
        SectionCard(
            title = title,
            body = "Нажмите «Войти демо», затем «Обновить».",
            status = "ожидает API",
        ),
    )
}

private fun String.localizedAccountType(): String = when (this) {
    "cash" -> "наличные"
    "deposit" -> "вклад"
    else -> "платежный"
}

private fun String.localizedOwnership(): String = when (this) {
    "shared" -> "общий"
    else -> "личный"
}

private fun String.localizedCategoryType(): String = when (this) {
    "income" -> "доход"
    else -> "расход"
}

private fun String.localizedScope(): String = when (this) {
    "household" -> "семейная"
    else -> "личная"
}

private fun String.localizedTransactionType(): String = when (this) {
    "income" -> "Доход"
    "transfer" -> "Перевод"
    else -> "Расход"
}

private val FinanceDashboard.transferCount: Int
    get() = transactions.count { it.type == "transfer" }

private fun targetAccountById(accounts: List<AccountSummary>?, accountId: String?): AccountSummary? {
    return accounts.orEmpty().firstOrNull { it.id.isNotBlank() && it.id == accountId }
}

private fun targetCategoryById(categories: List<CategorySummary>?, categoryId: String?): CategorySummary? {
    return categories.orEmpty().firstOrNull { it.id.isNotBlank() && it.id == categoryId }
}

private fun targetTransaction(
    transactions: List<TransactionSummary>?,
    transactionId: String?,
    includeTransfers: Boolean,
): TransactionSummary? {
    return transactions.orEmpty().firstOrNull {
        it.id.isNotBlank() &&
            it.id == transactionId &&
            (includeTransfers || it.type != "transfer") &&
            (!includeTransfers || it.type == "transfer")
    }
}

private fun compatibleExpenseCategory(
    account: AccountSummary,
    categories: List<CategorySummary>,
): CategorySummary? {
    return categories.firstOrNull { category ->
        category.id.isNotBlank() &&
            category.type == "expense" &&
            if (account.ownershipType == "shared") {
                category.scope == "household" && category.householdId == account.householdId
            } else {
                category.scope != "household"
            }
    }
}

private fun compatibleTransferPair(accounts: List<AccountSummary>): Pair<AccountSummary, AccountSummary>? {
    return accounts
        .filter { it.id.isNotBlank() && it.currency.isNotBlank() }
        .asSequence()
        .flatMap { source -> accounts.asSequence().map { destination -> source to destination } }
        .firstOrNull { (source, destination) ->
            source.id != destination.id &&
                source.currency == destination.currency &&
                source.ownershipType == destination.ownershipType &&
                if (source.ownershipType == "shared") {
                    source.householdId != null && source.householdId == destination.householdId
                } else {
                    true
                }
        }
}

@Preview(showBackground = true, widthDp = 390)
@Composable
private fun FinanceAppPreview() {
    FinanceTheme {
        FinanceApp(
            apiClient = PreviewFinanceApiClient(),
        )
    }
}

private class PreviewFinanceApiClient : FinanceApiClient {
    override val config: ApiConfig = ApiConfig("http://10.0.2.2:8000")

    override suspend fun login(email: String, password: String): ApiResult<SessionStatus> {
        return sessionStatus()
    }

    override suspend fun sessionStatus(): ApiResult<SessionStatus> {
        return ApiResult.Success(SessionStatus(true, "Пользователь demo", "household"))
    }

    override suspend fun dashboard(): ApiResult<FinanceDashboard> {
        val session = SessionStatus(true, "Пользователь demo", "household")
        return ApiResult.Success(
            FinanceDashboard(
                session = session,
                accounts = listOf(
                    AccountSummary("Наличные", "cash", "personal", "USD", "925.50", id = "acc-cash", version = 1),
                    AccountSummary("Накопления", "deposit", "personal", "USD", "100.00", id = "acc-save", version = 1),
                ),
                categories = listOf(CategorySummary("Продукты", "expense", "personal", id = "cat-food", version = 1)),
                transactions = listOf(
                    TransactionSummary("transfer", "25.00", "USD", "2026-05-18T08:30:00Z", "Dev same-household transfer", "household_same_household", "posted", id = "txn-transfer", accountId = "acc-cash", counterpartyAccountId = "acc-save", version = 1),
                    TransactionSummary("expense", "69.75", "USD", "2026-05-17T12:30:00Z", "Ручная операция", null, null, id = "txn-expense", accountId = "acc-cash", categoryId = "cat-food", version = 1),
                ),
                totals = listOf(MoneyTotal("USD", "250.00", "69.75", "180.25")),
                reportTransferCount = 1,
            ),
        )
    }

    override suspend fun createDemoAccount(householdId: String?, currency: String): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Android CRUD счет", "cash", "personal", currency, "12.3400", id = "acc-created", version = 1))
    }

    override suspend fun updateAccount(account: AccountSummary): ApiResult<AccountSummary> {
        return ApiResult.Success(account.copy(name = "${account.name} upd", version = (account.version ?: 1) + 1))
    }

    override suspend fun archiveAccount(accountId: String): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Android CRUD счет", "cash", "personal", "USD", "12.3400", id = accountId, status = "archived", version = 2))
    }

    override suspend fun restoreAccount(accountId: String): ApiResult<AccountSummary> {
        return ApiResult.Success(AccountSummary("Android CRUD счет", "cash", "personal", "USD", "12.3400", id = accountId, version = 3))
    }

    override suspend fun createDemoCategory(householdId: String?): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary("Android CRUD категория", "expense", "personal", id = "cat-created", version = 1))
    }

    override suspend fun updateCategory(category: CategorySummary): ApiResult<CategorySummary> {
        return ApiResult.Success(category.copy(name = "${category.name} upd", version = (category.version ?: 1) + 1))
    }

    override suspend fun archiveCategory(categoryId: String): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary("Android CRUD категория", "expense", "personal", id = categoryId, status = "archived", version = 2))
    }

    override suspend fun restoreCategory(categoryId: String): ApiResult<CategorySummary> {
        return ApiResult.Success(CategorySummary("Android CRUD категория", "expense", "personal", id = categoryId, version = 3))
    }

    override suspend fun createDemoTransaction(
        account: AccountSummary,
        category: CategorySummary?,
    ): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary("expense", "17.0000", account.currency, "2026-05-18T09:00:00Z", "Android lifecycle: создано", null, null, id = "txn-created", accountId = account.id, categoryId = category?.id, version = 1))
    }

    override suspend fun updateTransaction(transaction: TransactionSummary): ApiResult<TransactionSummary> {
        return ApiResult.Success(transaction.copy(amount = "18.0000", description = "Android lifecycle: обновлено", version = (transaction.version ?: 1) + 1))
    }

    override suspend fun deleteTransaction(transactionId: String): ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun restoreTransaction(transactionId: String): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary("expense", "18.0000", "USD", "2026-05-18T09:00:00Z", "Android lifecycle: восстановлено", null, null, id = transactionId, accountId = "acc-cash", categoryId = "cat-food", version = 3))
    }

    override suspend fun createDemoTransfer(
        source: AccountSummary,
        destination: AccountSummary,
    ): ApiResult<TransactionSummary> {
        return ApiResult.Success(TransactionSummary("transfer", "1.0000", source.currency, "2026-05-18T09:00:00Z", "Android transfer lifecycle", "personal_same_owner", "posted", id = "txn-transfer-created", accountId = source.id, counterpartyAccountId = destination.id, version = 1))
    }

    override suspend fun logout(): ApiResult<Unit> = ApiResult.Success(Unit)
}
