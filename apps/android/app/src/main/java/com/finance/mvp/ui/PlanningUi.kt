package com.finance.mvp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.finance.mvp.R
import com.finance.mvp.api.AccountSummary
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.AssetCategory
import com.finance.mvp.api.CategorySummary
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.FinanceDashboard
import com.finance.mvp.api.PlanningAllocation
import com.finance.mvp.api.PlanningAllocationCreateRequest
import com.finance.mvp.api.PlanningAllocationUpdateRequest
import com.finance.mvp.api.PlanningIncomeSource
import com.finance.mvp.api.PlanningIncomeSourceCreateRequest
import com.finance.mvp.api.PlanningIncomeSourceUpdateRequest
import com.finance.mvp.api.PlanningPlan
import com.finance.mvp.api.PlanningPlanCopyRequest
import com.finance.mvp.api.PlanningPlanCreateRequest
import com.finance.mvp.api.userFacingSeedText
import java.math.BigDecimal
import java.math.RoundingMode
import java.text.NumberFormat
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class AnalyticsSubsection(val title: String) {
    Summary("Сводка"),
    Planning("План месяца"),
}

enum class PlanningNotificationCandidateAction {
    PlanStatusChanged,
    ScheduleIncomeSource,
    CancelIncomeSource,
}

data class PlanningNotificationCandidate(
    val action: PlanningNotificationCandidateAction = PlanningNotificationCandidateAction.PlanStatusChanged,
    val planId: String,
    val scope: String,
    val month: String,
    val isUnderallocated: Boolean,
    val isOverallocated: Boolean,
    val remainingAmount: String,
    val overallocatedAmount: String,
    val incomeSourceId: String? = null,
    val incomeSourceName: String? = null,
    val incomeSourceAmount: String? = null,
    val currency: String? = null,
    val dayOfMonth: Int? = null,
)

private fun PlanningIncomeSource.toPlanningNotificationCandidate(
    plan: PlanningPlan,
    action: PlanningNotificationCandidateAction,
): PlanningNotificationCandidate = PlanningNotificationCandidate(
    action = action,
    planId = plan.id,
    scope = plan.scope,
    month = plan.month,
    isUnderallocated = plan.isUnderallocated,
    isOverallocated = plan.isOverallocated,
    remainingAmount = plan.remainingAmount,
    overallocatedAmount = plan.overallocatedAmount,
    incomeSourceId = id,
    incomeSourceName = source,
    incomeSourceAmount = amount,
    currency = plan.currency,
    dayOfMonth = dayOfMonth,
)

@Composable
fun AnalyticsSubsectionTabs(
    selected: AnalyticsSubsection,
    onSelected: (AnalyticsSubsection) -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyRow(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(AnalyticsSubsection.entries.toList()) { tab ->
            FilterChip(
                selected = selected == tab,
                onClick = { onSelected(tab) },
                label = { Text(tab.title) },
            )
        }
    }
}

@Composable
fun PlanningUi(
    apiClient: FinanceApiClient,
    dashboard: FinanceDashboard?,
    selectedMode: FinanceMode,
    onModeSelected: (FinanceMode) -> Unit,
    onCreateCategory: suspend (String, FinanceMode) -> ApiResult<CategorySummary>,
    onCreateAccount: suspend (String, String, String, FinanceMode) -> ApiResult<AccountSummary>,
    onPlanningNotificationCandidate: (PlanningNotificationCandidate) -> Unit,
    modifier: Modifier = Modifier,
) {
    val coroutineScope = rememberCoroutineScope()
    var month by rememberSaveable { mutableStateOf(nextPlanningMonth()) }
    val resolvedScope = selectedMode.toPlanningScope(dashboard?.session?.householdId)
    val currency = remember(dashboard, selectedMode) { dashboard.planningCurrency(selectedMode) }
    var plan by remember { mutableStateOf<PlanningPlan?>(null) }
    var history by remember { mutableStateOf<List<PlanningPlan>>(emptyList()) }
    var isLoading by rememberSaveable { mutableStateOf(false) }
    var message by rememberSaveable { mutableStateOf<String?>(null) }
    var showCategorySheet by rememberSaveable { mutableStateOf(false) }
    var showAccountSheet by rememberSaveable { mutableStateOf(false) }
    var createAccountTargetType by rememberSaveable { mutableStateOf(TARGET_INVESTMENT_ASSET_CATEGORY) }

    fun loadPlanningState(successMessage: String? = null) {
        val scopeInfo = resolvedScope ?: return
        coroutineScope.launch {
            isLoading = true
            message = null
            val result = withContext(Dispatchers.IO) {
                when (val currentResult = apiClient.listPlanningPlans(scopeInfo.apiScope, month, scopeInfo.householdId)) {
                    is ApiResult.Success -> {
                        val current = currentResult.value
                        if (current == null) {
                            ApiResult.Success(null)
                        } else {
                            when (val full = apiClient.getPlanningPlan(current.id)) {
                                is ApiResult.Success -> ApiResult.Success(full.value)
                                is ApiResult.Failure -> full
                            }
                        }
                    }
                    is ApiResult.Failure -> currentResult
                }
            }
            when (result) {
                is ApiResult.Success -> {
                    plan = result.value
                    message = successMessage
                }
                is ApiResult.Failure -> message = result.planningMessage()
            }
            history = when (val historyResult = withContext(Dispatchers.IO) {
                apiClient.listPlanningPlanHistory(scopeInfo.apiScope, scopeInfo.householdId)
            }) {
                is ApiResult.Success -> historyResult.value
                is ApiResult.Failure -> {
                    message = message ?: historyResult.planningMessage()
                    emptyList()
                }
            }
            isLoading = false
        }
    }

    LaunchedEffect(apiClient, resolvedScope, month) {
        plan = null
        history = emptyList()
        message = null
        if (resolvedScope != null) {
            loadPlanningState()
        }
    }

    LaunchedEffect(plan?.id, plan?.isUnderallocated, plan?.isOverallocated) {
        val current = plan ?: return@LaunchedEffect
        if (current.isUnderallocated || current.isOverallocated) {
            onPlanningNotificationCandidate(
                PlanningNotificationCandidate(
                    planId = current.id,
                    scope = current.scope,
                    month = current.month,
                    isUnderallocated = current.isUnderallocated,
                    isOverallocated = current.isOverallocated,
                    remainingAmount = current.remainingAmount,
                    overallocatedAmount = current.overallocatedAmount,
                ),
            )
        }
    }

    LaunchedEffect(plan?.id, plan?.incomeSources) {
        val current = plan ?: return@LaunchedEffect
        current.incomeSources.forEach { source ->
            onPlanningNotificationCandidate(
                source.toPlanningNotificationCandidate(
                    plan = current,
                    action = if (source.confirmed) {
                        PlanningNotificationCandidateAction.CancelIncomeSource
                    } else {
                        PlanningNotificationCandidateAction.ScheduleIncomeSource
                    },
                ),
            )
        }
    }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        PlanningScopeCard(
            selectedMode = selectedMode,
            hasHousehold = !dashboard?.session?.householdId.isNullOrBlank(),
            month = month,
            currency = currency,
            onModeSelected = onModeSelected,
            onMonthSelected = { month = it },
        )

        if (selectedMode == FinanceMode.Overview) {
            PlanningOverviewGate(onModeSelected)
            return@Column
        }

        if (resolvedScope == null) {
            PlanningMessageCard("Общее планирование недоступно без активного общего бюджета. Выберите Личное или подключите общий бюджет.")
            return@Column
        }

        if (!message.isNullOrBlank()) {
            PlanningMessageCard(message.orEmpty())
        }

        PlanningPlanCard(
            plan = plan,
            month = month,
            currency = currency,
            isLoading = isLoading,
            onRefresh = { loadPlanningState("План обновлён") },
            onCreatePlan = {
                coroutineScope.launch {
                    isLoading = true
                    val result = withContext(Dispatchers.IO) {
                        apiClient.createPlanningPlan(
                            PlanningPlanCreateRequest(
                                scope = resolvedScope.apiScope,
                                month = month,
                                currency = currency,
                                householdId = resolvedScope.householdId,
                            ),
                        )
                    }
                    when (result) {
                        is ApiResult.Success -> {
                            plan = result.value
                            message = "План создан"
                            loadPlanningState("План создан")
                        }
                        is ApiResult.Failure -> {
                            message = result.planningMessage()
                            isLoading = false
                        }
                    }
                }
            },
        )

        val currentPlan = plan
        if (currentPlan != null) {
            IncomeSourcesCard(
                plan = currentPlan,
                isLoading = isLoading,
                onCreate = { request ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.createPlanningIncomeSource(currentPlan.id, request)
                        }) {
                            is ApiResult.Success -> {
                                onPlanningNotificationCandidate(
                                    result.value.toPlanningNotificationCandidate(
                                        plan = currentPlan,
                                        action = PlanningNotificationCandidateAction.ScheduleIncomeSource,
                                    ),
                                )
                                loadPlanningState("Источник дохода добавлен")
                            }
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
                onUpdate = { source, request ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.updatePlanningIncomeSource(source.id, request)
                        }) {
                            is ApiResult.Success -> {
                                onPlanningNotificationCandidate(
                                    result.value.toPlanningNotificationCandidate(
                                        plan = currentPlan,
                                        action = if (result.value.confirmed) {
                                            PlanningNotificationCandidateAction.CancelIncomeSource
                                        } else {
                                            PlanningNotificationCandidateAction.ScheduleIncomeSource
                                        },
                                    ),
                                )
                                loadPlanningState("Источник дохода обновлён")
                            }
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
                onConfirm = { source ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.confirmPlanningIncomeSource(source.id)
                        }) {
                            is ApiResult.Success -> {
                                onPlanningNotificationCandidate(
                                    result.value.toPlanningNotificationCandidate(
                                        plan = currentPlan,
                                        action = PlanningNotificationCandidateAction.CancelIncomeSource,
                                    ),
                                )
                                loadPlanningState("Доход подтверждён")
                            }
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
                onDelete = { source ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.deletePlanningIncomeSource(source.id)
                        }) {
                            is ApiResult.Success -> {
                                onPlanningNotificationCandidate(
                                    source.toPlanningNotificationCandidate(
                                        plan = currentPlan,
                                        action = PlanningNotificationCandidateAction.CancelIncomeSource,
                                    ),
                                )
                                loadPlanningState("Источник дохода удалён")
                            }
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
            )

            AllocationsCard(
                plan = currentPlan,
                dashboard = dashboard,
                planMode = resolvedScope.mode,
                isLoading = isLoading,
                onShowCreateCategory = { showCategorySheet = true },
                onShowCreateAccount = { targetType ->
                    createAccountTargetType = targetType
                    showAccountSheet = true
                },
                onCreate = { request ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.createPlanningAllocation(currentPlan.id, request)
                        }) {
                            is ApiResult.Success -> loadPlanningState("Распределение добавлено")
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
                onUpdate = { allocation, request ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.updatePlanningAllocation(allocation.id, request)
                        }) {
                            is ApiResult.Success -> loadPlanningState("Распределение обновлено")
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
                onDelete = { allocation ->
                    coroutineScope.launch {
                        isLoading = true
                        when (val result = withContext(Dispatchers.IO) {
                            apiClient.deletePlanningAllocation(allocation.id)
                        }) {
                            is ApiResult.Success -> loadPlanningState("Распределение удалено")
                            is ApiResult.Failure -> {
                                message = result.planningMessage()
                                isLoading = false
                            }
                        }
                    }
                },
            )
        }

        PlanningHistoryCard(
            history = history,
            currentMonth = month,
            isLoading = isLoading,
            onCopy = { historyPlan ->
                coroutineScope.launch {
                    isLoading = true
                    when (val result = withContext(Dispatchers.IO) {
                        apiClient.copyPlanningPlan(
                            historyPlan.id,
                            PlanningPlanCopyRequest(targetMonth = month),
                        )
                    }) {
                        is ApiResult.Success -> {
                            plan = result.value
                            loadPlanningState("План ${historyPlan.month.localizedPlanningMonth()} скопирован на ${month.localizedPlanningMonth()}")
                        }
                        is ApiResult.Failure -> {
                            message = result.planningMessage()
                            isLoading = false
                        }
                    }
                }
            },
        )
    }

    if (showCategorySheet && resolvedScope != null) {
        PlanningCreateCategorySheet(
            mode = resolvedScope.mode,
            onDismiss = { showCategorySheet = false },
            onCreate = { name ->
                coroutineScope.launch {
                    isLoading = true
                    when (val result = onCreateCategory(name, resolvedScope.mode)) {
                        is ApiResult.Success -> {
                            showCategorySheet = false
                            message = "Категория «${result.value.planningDisplayName()}» создана. Выберите её в целях после обновления."
                            isLoading = false
                        }
                        is ApiResult.Failure -> {
                            message = result.planningMessage()
                            isLoading = false
                        }
                    }
                }
            },
        )
    }

    if (showAccountSheet && resolvedScope != null) {
        PlanningCreateAccountSheet(
            mode = resolvedScope.mode,
            currency = currency,
            targetType = createAccountTargetType,
            onDismiss = { showAccountSheet = false },
            onCreate = { name, accountCurrency, accountType ->
                coroutineScope.launch {
                    isLoading = true
                    when (val result = onCreateAccount(name, accountCurrency, accountType, resolvedScope.mode)) {
                        is ApiResult.Success -> {
                            showAccountSheet = false
                            message = "${createAccountTargetType.localizedCreatedTargetLabel()} «${result.value.planningDisplayName()}» создан. Выберите его в целях после обновления."
                            isLoading = false
                        }
                        is ApiResult.Failure -> {
                            message = result.planningMessage()
                            isLoading = false
                        }
                    }
                }
            },
        )
    }
}

@Composable
private fun PlanningScopeCard(
    selectedMode: FinanceMode,
    hasHousehold: Boolean,
    month: String,
    currency: String,
    onModeSelected: (FinanceMode) -> Unit,
    onMonthSelected: (String) -> Unit,
) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PlanningIcon(R.drawable.ic_analytics_24, Color(0xFF4267D5))
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("План месяца", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("План на ${month.localizedPlanningMonth()}", style = MaterialTheme.typography.bodySmall)
                }
                Text(currency, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            }
            Text("Месяц плана", style = MaterialTheme.typography.labelLarge)
            PlanningMonthPicker(selectedMonth = month, onSelected = onMonthSelected)
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(writableFinanceModes(hasHousehold)) { mode ->
                    FilterChip(
                        selected = selectedMode == mode,
                        onClick = { onModeSelected(mode) },
                        label = { Text(mode.title) },
                    )
                }
            }
        }
    }
}

@Composable
private fun PlanningMonthPicker(
    selectedMonth: String,
    onSelected: (String) -> Unit,
    choices: List<PlanningMonthChoice> = planningMonthChoices(),
) {
    val rememberedChoices = remember(choices) { choices }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(rememberedChoices) { choice ->
            FilterChip(
                selected = selectedMonth == choice.month,
                onClick = { onSelected(choice.month) },
                label = { Text(choice.title) },
            )
        }
    }
}

@Composable
private fun PlanningOverviewGate(onModeSelected: (FinanceMode) -> Unit) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Обзор не создаёт единый план", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(
                "Планирование работает в одном режиме. Выберите личный или общий план, чтобы не смешивать бюджеты небезопасным агрегатом.",
                style = MaterialTheme.typography.bodySmall,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onModeSelected(FinanceMode.Personal) }, modifier = Modifier.weight(1f)) {
                    Text("Личное")
                }
                OutlinedButton(onClick = { onModeSelected(FinanceMode.Shared) }, modifier = Modifier.weight(1f)) {
                    Text("Общее")
                }
            }
        }
    }
}

@Composable
private fun PlanningPlanCard(
    plan: PlanningPlan?,
    month: String,
    currency: String,
    isLoading: Boolean,
    onRefresh: () -> Unit,
    onCreatePlan: () -> Unit,
) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Текущий план", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(plan?.let { "${it.scope.localizedPlanningScope()} • ${it.month.localizedPlanningMonth()} • ${it.currency}" } ?: "План на ${month.localizedPlanningMonth()} ещё не создан", style = MaterialTheme.typography.bodySmall)
                }
                IconButton(onClick = onRefresh, enabled = !isLoading) {
                    Icon(painterResource(R.drawable.ic_refresh_24), contentDescription = "Обновить")
                }
            }
            if (plan == null) {
                Button(onClick = onCreatePlan, enabled = !isLoading, modifier = Modifier.fillMaxWidth()) {
                    Text("Создать план на ${month.localizedPlanningMonth()}")
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PlanningMetric("Доход", plan.totalPlannedIncome.planningMoney(currency), Modifier.weight(1f))
                    PlanningMetric("Распределено", plan.allocatedTotal.planningMoney(currency), Modifier.weight(1f))
                }
                plan.previousMonthSurplus.takeIf { it.isPositivePlanningAmount() }?.let { surplus ->
                    Text("Предложение к учету из прошлого месяца: ${surplus.planningMoney(currency)}. Это подсказка, не перенос денег.", style = MaterialTheme.typography.bodySmall)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PlanningMetric("Осталось", plan.remainingAmount.planningMoney(currency), Modifier.weight(1f))
                    PlanningMetric("Сверх", plan.overallocatedAmount.planningMoney(currency), Modifier.weight(1f))
                }
                if (plan.isUnderallocated) {
                    PlanningBanner("Есть доход без распределений. Добавьте allocation или уменьшите плановый доход.", Color(0xFF8A6A12))
                }
                if (plan.isOverallocated) {
                    PlanningBanner("Распределения выше планового дохода. Исправьте allocations, чтобы снять предупреждение.", Color(0xFFE35D4F))
                }
                PlanningHighlights(plan)
            }
        }
    }
}

@Composable
private fun PlanningHighlights(plan: PlanningPlan) {
    val allocationHighlights = plan.allocations.mapNotNull { allocation ->
        when {
            allocation.targetType == TARGET_INVESTMENT_ASSET_CATEGORY &&
                (allocation.progressStatus == "under_plan" || allocation.requiresAttention) ->
                "Инвестиции ниже плана: ${allocation.targetSnapshot?.planningSnapshotTitle() ?: allocation.targetType.localizedTargetType()}"
            allocation.targetType == TARGET_EXPENSE_CATEGORY &&
                (allocation.progressStatus == "over_plan" || allocation.requiresAttention) ->
                "Расходы выше плана: ${allocation.targetSnapshot?.planningSnapshotTitle() ?: allocation.targetType.localizedTargetType()}"
            !allocation.progressStatus.isNullOrBlank() ->
                "${allocation.targetType.localizedTargetType()}: ${allocation.progressStatus.localizedPlanningStatus()}"
            else -> null
        }
    }
    if (allocationHighlights.isEmpty()) {
        PlanningBanner("Статусы появятся в строках распределений после расчета по allocation.", Color(0xFF6D5BD0))
    }
    allocationHighlights.take(3).forEach { highlight ->
        val color = if (highlight.startsWith("Расходы")) Color(0xFFE35D4F) else Color(0xFF8A6A12)
        PlanningBanner(highlight, color)
    }
}

@Composable
private fun IncomeSourcesCard(
    plan: PlanningPlan,
    isLoading: Boolean,
    onCreate: (PlanningIncomeSourceCreateRequest) -> Unit,
    onUpdate: (PlanningIncomeSource, PlanningIncomeSourceUpdateRequest) -> Unit,
    onConfirm: (PlanningIncomeSource) -> Unit,
    onDelete: (PlanningIncomeSource) -> Unit,
) {
    var source by rememberSaveable(plan.id) { mutableStateOf("") }
    var amount by rememberSaveable(plan.id) { mutableStateOf("") }
    var day by rememberSaveable(plan.id) { mutableStateOf("") }
    var showAddForm by rememberSaveable(plan.id) { mutableStateOf(false) }
    val normalizedAmount = amount.trim().normalizedPlanningAmount()
    val planningDay = day.toPlanningDay()

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Источники дохода", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (!showAddForm) {
                OutlinedButton(
                    onClick = { showAddForm = true },
                    enabled = !isLoading,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Добавить источник")
                }
            } else {
            OutlinedTextField(
                value = source,
                onValueChange = { source = it },
                label = { Text("Источник") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it.planningDecimalInput() },
                    label = { Text("Сумма") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                OutlinedTextField(
                    value = day,
                    onValueChange = { day = it.filter(Char::isDigit).take(2) },
                    label = { Text("День месяца") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.weight(0.7f),
                )
            }
            Button(
                onClick = {
                    onCreate(
                        PlanningIncomeSourceCreateRequest(
                            amount = normalizedAmount.orEmpty(),
                            source = source.trim(),
                            dayOfMonth = planningDay ?: return@Button,
                        ),
                    )
                    source = ""
                    amount = ""
                    day = ""
                    showAddForm = false
                },
                enabled = !isLoading && source.isNotBlank() && normalizedAmount != null && planningDay != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Добавить источник")
            }
            }

            if (plan.incomeSources.isEmpty()) {
                Text("Источников дохода пока нет", style = MaterialTheme.typography.bodySmall)
            } else {
                plan.incomeSources.forEach { item ->
                    IncomeSourceRow(
                        source = item,
                        currency = plan.currency,
                        isLoading = isLoading,
                        onUpdate = onUpdate,
                        onConfirm = onConfirm,
                        onDelete = onDelete,
                    )
                }
            }
        }
    }
}

@Composable
private fun IncomeSourceRow(
    source: PlanningIncomeSource,
    currency: String,
    isLoading: Boolean,
    onUpdate: (PlanningIncomeSource, PlanningIncomeSourceUpdateRequest) -> Unit,
    onConfirm: (PlanningIncomeSource) -> Unit,
    onDelete: (PlanningIncomeSource) -> Unit,
) {
    var isEditing by rememberSaveable(source.id) { mutableStateOf(false) }
    var editSource by rememberSaveable(source.id) { mutableStateOf(source.source) }
    var editAmount by rememberSaveable(source.id) { mutableStateOf(source.amount) }
    var editDay by rememberSaveable(source.id) { mutableStateOf(source.dayOfMonth?.toString().orEmpty()) }
    val normalizedEditAmount = editAmount.trim().normalizedPlanningAmount()
    val editPlanningDay = editDay.toPlanningDay()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f), RoundedCornerShape(8.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(source.source, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                Text(
                    "${source.amount.planningMoney(currency)} • день ${source.dayOfMonth ?: "не задан"} • ${if (source.confirmed) "подтверждён" else "ожидает"}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            TextButton(onClick = { isEditing = !isEditing }) {
                Text(if (isEditing) "Закрыть" else "Править")
            }
        }
        if (isEditing) {
            OutlinedTextField(
                value = editSource,
                onValueChange = { editSource = it },
                label = { Text("Источник") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = editAmount,
                    onValueChange = { editAmount = it.planningDecimalInput() },
                    label = { Text("Сумма") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                OutlinedTextField(
                    value = editDay,
                    onValueChange = { editDay = it.filter(Char::isDigit).take(2) },
                    label = { Text("День месяца") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.weight(0.7f),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { onDelete(source) },
                    enabled = !isLoading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Удалить")
                }
                Button(
                    onClick = {
                        onUpdate(
                            source,
                            PlanningIncomeSourceUpdateRequest(
                                source = editSource.trim(),
                                amount = normalizedEditAmount,
                                dayOfMonth = editPlanningDay,
                                version = source.version,
                            ),
                        )
                        isEditing = false
                    },
                    enabled = !isLoading && editSource.isNotBlank() && normalizedEditAmount != null && editPlanningDay != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Сохранить")
                }
            }
        }
        if (!source.confirmed) {
            OutlinedButton(onClick = { onConfirm(source) }, enabled = !isLoading, modifier = Modifier.fillMaxWidth()) {
                Text("Подтвердить доход")
            }
        }
    }
}

@Composable
private fun AllocationsCard(
    plan: PlanningPlan,
    dashboard: FinanceDashboard?,
    planMode: FinanceMode,
    isLoading: Boolean,
    onShowCreateCategory: () -> Unit,
    onShowCreateAccount: (String) -> Unit,
    onCreate: (PlanningAllocationCreateRequest) -> Unit,
    onUpdate: (PlanningAllocation, PlanningAllocationUpdateRequest) -> Unit,
    onDelete: (PlanningAllocation) -> Unit,
) {
    var draft by remember(plan.id) { mutableStateOf(PlanningAllocationDraft()) }
    val categories = dashboard.planningCategories(planMode)
    val investments = dashboard.planningInvestmentAssetCategories(planMode)
    val targetOptions = remember(draft.targetType, categories, investments) {
        planningTargetOptions(draft.targetType, categories, investments)
    }
    LaunchedEffect(draft.targetType, targetOptions) {
        if (draft.targetId.isBlank() && targetOptions.isNotEmpty()) {
            draft = draft.copy(targetId = targetOptions.first().id)
        }
    }
    val canCreateAllocation = !isLoading &&
        draft.targetId.isNotBlank() &&
        draft.allocationValue.trim().normalizedPlanningAmount() != null &&
        draft.hasValidSavingsGoalState()

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Распределения", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            PlanningAllocationEditor(
                draft = draft,
                currency = plan.currency,
                targetOptions = targetOptions,
                onDraftChange = { draft = it },
                onShowCreateCategory = onShowCreateCategory,
                onShowCreateAccount = onShowCreateAccount,
            )
            Button(
                onClick = {
                    onCreate(draft.toCreateRequest())
                    draft = PlanningAllocationDraft()
                },
                enabled = canCreateAllocation,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Добавить распределение")
            }
            if (!canCreateAllocation) {
                Text(
                    "Чтобы добавить allocation, выберите цель этого scope и укажите сумму или процент.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (plan.allocations.isEmpty()) {
                Text("В плане ${plan.scope.localizedPlanningScope()} пока нет распределений. Добавьте расходную или инвестиционную цель.", style = MaterialTheme.typography.bodySmall)
            } else {
                plan.allocations.forEach { allocation ->
                    AllocationRow(
                        allocation = allocation,
                        currency = plan.currency,
                        categories = categories,
                        investments = investments,
                        isLoading = isLoading,
                        onUpdate = onUpdate,
                        onDelete = onDelete,
                    )
                }
            }
        }
    }
}

@Composable
private fun PlanningAllocationEditor(
    draft: PlanningAllocationDraft,
    currency: String,
    targetOptions: List<PlanningTargetOption>,
    onDraftChange: (PlanningAllocationDraft) -> Unit,
    onShowCreateCategory: () -> Unit,
    onShowCreateAccount: (String) -> Unit,
    showCreateButtons: Boolean = true,
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(listOf(TARGET_EXPENSE_CATEGORY, TARGET_INVESTMENT_ASSET_CATEGORY)) { targetType ->
                FilterChip(
                    selected = draft.targetType == targetType,
                    onClick = {
                        val savingsGoalEnabled = draft.isSavingsGoal && targetType == TARGET_INVESTMENT_ASSET_CATEGORY
                        onDraftChange(
                            draft.copy(
                                targetType = targetType,
                                targetId = "",
                                isSavingsGoal = savingsGoalEnabled,
                                goalTargetAmount = draft.goalTargetAmount.takeIf { savingsGoalEnabled }.orEmpty(),
                                goalDueMonth = draft.goalDueMonth.takeIf { savingsGoalEnabled } ?: nextPlanningMonth(),
                            ),
                        )
                    },
                    label = { Text(targetType.localizedTargetType()) },
                )
            }
        }
        if (showCreateButtons && draft.targetType == TARGET_EXPENSE_CATEGORY) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        if (draft.targetType == TARGET_EXPENSE_CATEGORY) {
                            onShowCreateCategory()
                        } else {
                            onShowCreateAccount(draft.targetType)
                        }
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text(draft.targetType.localizedCreateButtonLabel())
                }
            }
        }
        if (targetOptions.isEmpty()) {
            Text("Целей этого типа пока нет. Создайте категорию перед сохранением распределения.", style = MaterialTheme.typography.bodySmall)
        } else {
            Text(if (draft.targetType == TARGET_EXPENSE_CATEGORY) "Категория расходов" else "Категория инвестиций", style = MaterialTheme.typography.labelLarge)
            if (draft.targetType == TARGET_EXPENSE_CATEGORY) {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 144.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(targetOptions) { option ->
                        FilterChip(
                            selected = draft.targetId == option.id,
                            onClick = { onDraftChange(draft.copy(targetId = option.id)) },
                            modifier = Modifier.fillMaxWidth(),
                            label = {
                                Text(option.title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            },
                        )
                    }
                }
            } else {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(targetOptions) { option ->
                        FilterChip(
                            selected = draft.targetId == option.id,
                            onClick = { onDraftChange(draft.copy(targetId = option.id)) },
                            modifier = Modifier.width(140.dp),
                            label = {
                                Text(option.title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            },
                        )
                    }
                }
            }
        }
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(listOf(RECURRENCE_REGULAR, RECURRENCE_ONE_OFF)) { recurrence ->
                FilterChip(
                    selected = draft.recurrenceType == recurrence,
                    onClick = { onDraftChange(draft.copy(recurrenceType = recurrence)) },
                    label = { Text(recurrence.localizedRecurrenceType()) },
                )
            }
        }
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(listOf(ALLOCATION_AMOUNT, ALLOCATION_PERCENT)) { mode ->
                FilterChip(
                    selected = draft.allocationMode == mode,
                    onClick = { onDraftChange(draft.copy(allocationMode = mode)) },
                    label = { Text(mode.localizedAllocationMode()) },
                )
            }
        }
        OutlinedTextField(
            value = draft.allocationValue,
            onValueChange = { onDraftChange(draft.copy(allocationValue = it.planningDecimalInput())) },
            label = { Text(if (draft.allocationMode == ALLOCATION_PERCENT) "Процент" else "Сумма") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        if (draft.targetType == TARGET_INVESTMENT_ASSET_CATEGORY) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                FilterChip(
                    selected = draft.isSavingsGoal,
                    onClick = {
                        val savingsGoalEnabled = !draft.isSavingsGoal
                        onDraftChange(
                            draft.copy(
                                isSavingsGoal = savingsGoalEnabled,
                                goalTargetAmount = draft.goalTargetAmount.takeIf { savingsGoalEnabled }.orEmpty(),
                                goalDueMonth = draft.goalDueMonth.takeIf { savingsGoalEnabled } ?: nextPlanningMonth(),
                            ),
                        )
                    },
                    label = { Text("Цель накопления") },
                )
            }
        } else {
            Text(
                "Накопительная цель доступна только для инвестиционных категорий.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (draft.isSavingsGoal && draft.targetType == TARGET_INVESTMENT_ASSET_CATEGORY) {
            OutlinedTextField(
                value = draft.goalTargetAmount,
                onValueChange = { onDraftChange(draft.copy(goalTargetAmount = it.planningDecimalInput())) },
                label = { Text("Целевая сумма") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Text("Срок цели", style = MaterialTheme.typography.labelLarge)
            PlanningMonthPicker(
                selectedMonth = draft.goalDueMonth,
                onSelected = { onDraftChange(draft.copy(goalDueMonth = it)) },
                choices = planningGoalMonthChoices(),
            )
            draft.estimatedMonthlyAmount()?.let { monthly ->
                Text("Ориентир в месяц: ${monthly.planningMoney(currency)}", style = MaterialTheme.typography.bodySmall)
            }
        }
        OutlinedTextField(
            value = draft.comment,
            onValueChange = { onDraftChange(draft.copy(comment = it)) },
            label = { Text("Комментарий") },
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun AllocationRow(
    allocation: PlanningAllocation,
    currency: String,
    categories: List<CategorySummary>,
    investments: List<AssetCategory>,
    isLoading: Boolean,
    onUpdate: (PlanningAllocation, PlanningAllocationUpdateRequest) -> Unit,
    onDelete: (PlanningAllocation) -> Unit,
) {
    var isEditing by rememberSaveable(allocation.id) { mutableStateOf(false) }
    var draft by remember(allocation.id) {
        mutableStateOf(
            PlanningAllocationDraft(
                targetType = allocation.targetType.ifBlank { TARGET_EXPENSE_CATEGORY },
                targetId = allocation.targetId.orEmpty(),
                allocationMode = allocation.allocationMode.ifBlank { ALLOCATION_AMOUNT },
                allocationValue = allocation.allocationValue,
                recurrenceType = allocation.recurrenceType.orEmpty().ifBlank { RECURRENCE_REGULAR },
                isSavingsGoal = allocation.isSavingsGoal && allocation.targetType == TARGET_INVESTMENT_ASSET_CATEGORY,
                goalTargetAmount = allocation.goalTargetAmount.orEmpty(),
                goalDueMonth = allocation.goalDueMonth.orEmpty().ifBlank { nextPlanningMonth() },
                comment = allocation.comment.orEmpty(),
            ),
        )
    }
    val targetOptions = planningTargetOptions(draft.targetType, categories, investments)
    val targetName = allocation.readableTargetName(targetOptions)
    val statusText = allocation.readableStatus()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f), RoundedCornerShape(8.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = targetName,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${allocation.targetType.localizedTargetType()} • ${allocation.recurrenceType.orEmpty().ifBlank { RECURRENCE_REGULAR }.localizedRecurrenceType()} • ${allocation.allocationMode.localizedAllocationMode()}: ${allocation.allocationValue} • план ${allocation.calculatedAmount.planningMoney(currency)} • $statusText",
                    style = MaterialTheme.typography.bodySmall,
                )
                allocation.actualAmount?.takeIf { it.isNotBlank() }?.let {
                    Text("Факт allocation: ${it.planningMoney(currency)}${allocation.progressPercent?.let { percent -> " • $percent%" }.orEmpty()}", style = MaterialTheme.typography.bodySmall)
                } ?: Text("Факт по этому allocation появится после расчета", style = MaterialTheme.typography.bodySmall)
                if (allocation.isSavingsGoal) {
                    val goalText = allocation.goalTargetAmount?.takeIf { it.isNotBlank() }?.planningMoney(currency) ?: "не задана"
                    val dueText = allocation.goalDueMonth?.localizedPlanningMonth() ?: "срок не задан"
                    val monthlyText = allocation.goalMonthlyAmount?.takeIf { it.isNotBlank() }?.planningMoney(currency)
                        ?: draft.estimatedMonthlyAmount()?.planningMoney(currency)
                        ?: "ожидает расчёта"
                    Text("Цель накопления: $goalText к $dueText • в месяц $monthlyText", style = MaterialTheme.typography.bodySmall)
                }
                allocation.comment?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall)
                }
            }
            TextButton(onClick = { isEditing = !isEditing }) {
                Text(if (isEditing) "Закрыть" else "Править")
            }
        }
        if (allocation.requiresAttention) {
            PlanningBanner(
                allocation.attentionReason?.takeIf { it.isNotBlank() } ?: "Эта цель требует внимания",
                Color(0xFF8A6A12),
            )
        }
        if (isEditing) {
            PlanningAllocationEditor(
                draft = draft,
                currency = currency,
                targetOptions = targetOptions,
                onDraftChange = { draft = it },
                onShowCreateCategory = {},
                onShowCreateAccount = { _ -> },
                showCreateButtons = false,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { onDelete(allocation) },
                    enabled = !isLoading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Удалить")
                }
                Button(
                    onClick = {
                        onUpdate(
                            allocation,
                            PlanningAllocationUpdateRequest(
                                targetType = draft.targetType,
                                targetId = draft.targetId.ifBlank { null },
                                comment = draft.comment.trim().ifBlank { null },
                                allocationMode = draft.allocationMode,
                                allocationValue = draft.allocationValue.trim().normalizedPlanningAmount(),
                                recurrenceType = draft.recurrenceType,
                                isSavingsGoal = draft.isSavingsGoal && draft.targetType == TARGET_INVESTMENT_ASSET_CATEGORY,
                                goalTargetAmount = draft.goalTargetAmount.trim().normalizedPlanningAmount().takeIf { draft.isSavingsGoal && draft.targetType == TARGET_INVESTMENT_ASSET_CATEGORY },
                                goalDueMonth = draft.goalDueMonth.takeIf { draft.isSavingsGoal && draft.targetType == TARGET_INVESTMENT_ASSET_CATEGORY },
                                version = allocation.version,
                            ),
                        )
                        isEditing = false
                    },
                    enabled = !isLoading &&
                        draft.allocationValue.trim().normalizedPlanningAmount() != null &&
                        draft.hasValidSavingsGoalState(),
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Сохранить")
                }
            }
        }
    }
}

@Composable
private fun PlanningHistoryCard(
    history: List<PlanningPlan>,
    currentMonth: String,
    isLoading: Boolean,
    onCopy: (PlanningPlan) -> Unit,
) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("История", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (history.isEmpty()) {
                Text("Истории планов пока нет", style = MaterialTheme.typography.bodySmall)
            } else {
                history
                    .filter { it.month != currentMonth }
                    .take(6)
                    .forEach { plan ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(plan.month.localizedPlanningMonth(), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                                Text("${plan.scope.localizedPlanningScope()} • ${plan.currency}", style = MaterialTheme.typography.bodySmall)
                            }
                            TextButton(onClick = { onCopy(plan) }, enabled = !isLoading) {
                                Text("Копировать")
                            }
                        }
                    }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlanningCreateCategorySheet(
    mode: FinanceMode,
    onDismiss: () -> Unit,
    onCreate: (String) -> Unit,
) {
    var name by rememberSaveable { mutableStateOf("") }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Новая категория • ${mode.title}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Название категории") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Отмена")
                }
                Button(onClick = { onCreate(name.trim()) }, enabled = name.isNotBlank(), modifier = Modifier.weight(1f)) {
                    Text("Создать")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlanningCreateAccountSheet(
    mode: FinanceMode,
    currency: String,
    targetType: String,
    onDismiss: () -> Unit,
    onCreate: (String, String, String) -> Unit,
) {
    val accountTypeOptions = remember(targetType) { targetType.planningAccountTypeOptions() }
    var name by rememberSaveable { mutableStateOf("") }
    var accountCurrency by rememberSaveable(currency) { mutableStateOf(currency) }
    var accountType by rememberSaveable(targetType) { mutableStateOf(accountTypeOptions.first().apiValue) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("${targetType.localizedNewTargetTitle()} • ${mode.title}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text(targetType.localizedNameLabel()) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(accountTypeOptions) { option ->
                    FilterChip(
                        selected = accountType == option.apiValue,
                        onClick = { accountType = option.apiValue },
                        label = { Text(option.title) },
                    )
                }
            }
            OutlinedTextField(
                value = accountCurrency,
                onValueChange = { accountCurrency = it.uppercase(Locale.getDefault()).take(3) },
                label = { Text("Валюта") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Отмена")
                }
                Button(
                    onClick = { onCreate(name.trim(), accountCurrency.ifBlank { currency }, accountType) },
                    enabled = name.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Создать")
                }
            }
        }
    }
}

@Composable
private fun PlanningMessageCard(text: String) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Text(text, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun PlanningMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f), RoundedCornerShape(8.dp))
            .padding(10.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun PlanningBanner(text: String, color: Color) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
            .padding(10.dp),
    ) {
        Text(text, color = color, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun PlanningIcon(icon: Int, color: Color) {
    Box(
        modifier = Modifier
            .size(36.dp)
            .background(color.copy(alpha = 0.14f), RoundedCornerShape(18.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            tint = color,
            modifier = Modifier.size(20.dp),
        )
    }
}

private data class PlanningScopeInfo(
    val apiScope: String,
    val householdId: String?,
    val mode: FinanceMode,
)

private data class PlanningMonthChoice(
    val month: String,
    val title: String,
)

private data class PlanningTargetOption(
    val id: String,
    val title: String,
)

private data class PlanningAccountTypeOption(
    val apiValue: String,
    val title: String,
)

private data class PlanningAllocationDraft(
    val targetType: String = TARGET_EXPENSE_CATEGORY,
    val targetId: String = "",
    val allocationMode: String = ALLOCATION_AMOUNT,
    val allocationValue: String = "",
    val recurrenceType: String = RECURRENCE_REGULAR,
    val isSavingsGoal: Boolean = false,
    val goalTargetAmount: String = "",
    val goalDueMonth: String = nextPlanningMonth(),
    val comment: String = "",
) {
    fun toCreateRequest(): PlanningAllocationCreateRequest {
        val savingsGoalEnabled = isSavingsGoal && targetType == TARGET_INVESTMENT_ASSET_CATEGORY
        return PlanningAllocationCreateRequest(
            targetType = targetType,
            targetId = targetId.trim(),
            comment = comment.trim().ifBlank { null },
            allocationMode = allocationMode,
            allocationValue = allocationValue.trim().normalizedPlanningAmount().orEmpty(),
            recurrenceType = recurrenceType,
            isSavingsGoal = savingsGoalEnabled,
            goalTargetAmount = goalTargetAmount.trim().normalizedPlanningAmount().takeIf { savingsGoalEnabled },
            goalDueMonth = goalDueMonth.takeIf { savingsGoalEnabled },
        )
    }
}

private fun PlanningAllocationDraft.hasValidSavingsGoalState(): Boolean {
    if (!isSavingsGoal) return true
    if (targetType != TARGET_INVESTMENT_ASSET_CATEGORY) return false
    return goalTargetAmount.trim().normalizedPlanningAmount() != null
}

private const val TARGET_EXPENSE_CATEGORY = "expense_category"
private const val TARGET_ACCOUNT = "account"
private const val TARGET_ASSET = "asset"
private const val TARGET_INVESTMENT_ASSET_CATEGORY = "investment_asset_category"
private const val ALLOCATION_AMOUNT = "amount"
private const val ALLOCATION_PERCENT = "percent"
private const val RECURRENCE_REGULAR = "regular"
private const val RECURRENCE_ONE_OFF = "one_off"

private fun FinanceMode.toPlanningScope(householdId: String?): PlanningScopeInfo? {
    return when (this) {
        FinanceMode.Personal -> PlanningScopeInfo("personal", null, this)
        FinanceMode.Shared -> householdId
            ?.takeIf { it.isNotBlank() }
            ?.let { PlanningScopeInfo("household", it, this) }
        FinanceMode.Overview -> null
    }
}

private fun FinanceDashboard?.planningCurrency(mode: FinanceMode): String {
    val accounts = planningAccounts(mode)
    return accounts.firstOrNull()?.currency
        ?: this?.totals?.firstOrNull()?.currency
        ?: "RUB"
}

private fun FinanceDashboard?.planningAccounts(mode: FinanceMode): List<AccountSummary> {
    return this?.accounts.orEmpty()
        .filter { it.status == "active" }
        .filter {
            when (mode) {
                FinanceMode.Personal -> it.ownershipType != "shared"
                FinanceMode.Shared -> it.ownershipType == "shared"
                FinanceMode.Overview -> true
            }
        }
}

private fun planningTargetOptions(
    targetType: String,
    categories: List<CategorySummary>,
    investments: List<AssetCategory>,
): List<PlanningTargetOption> {
    return when (targetType) {
        TARGET_EXPENSE_CATEGORY -> categories.map { PlanningTargetOption(it.id, it.planningDisplayName()) }
        TARGET_INVESTMENT_ASSET_CATEGORY -> investments
            .map { PlanningTargetOption(it.id, it.planningDisplayName()) }
        TARGET_ASSET -> investments
            .map { PlanningTargetOption(it.id, it.planningDisplayName()) }
        else -> emptyList()
    }
}

private fun FinanceDashboard?.planningInvestmentAssetCategories(mode: FinanceMode): List<AssetCategory> {
    return this?.assetCategories.orEmpty()
        .filter { it.recordStatus == "active" && it.isInvestment }
        .filter {
            when (mode) {
                FinanceMode.Personal -> it.scopeType != "household"
                FinanceMode.Shared -> it.scopeType == "household"
                FinanceMode.Overview -> true
            }
        }
}

private fun FinanceDashboard?.planningCategories(mode: FinanceMode): List<CategorySummary> {
    return this?.categories.orEmpty()
        .filter { it.status == "active" && it.type == "expense" }
        .filter {
            when (mode) {
                FinanceMode.Personal -> it.scope != "household"
                FinanceMode.Shared -> it.scope == "household"
                FinanceMode.Overview -> true
            }
        }
}

private fun AccountSummary.planningDisplayName(): String = userFacingSeedText(name)

private fun CategorySummary.planningDisplayName(): String = userFacingSeedText(name)

private fun AssetCategory.planningDisplayName(): String = userFacingSeedText(name)

private fun String.localizedPlanningScope(): String = when (this) {
    "personal" -> "Личное"
    "household" -> "Общее"
    "shared" -> "Общее"
    else -> "Личное"
}

private fun String.localizedTargetType(): String = when (this) {
    TARGET_EXPENSE_CATEGORY -> "Расходы"
    TARGET_INVESTMENT_ASSET_CATEGORY -> "Инвестиции"
    TARGET_ACCOUNT -> "Счёт"
    TARGET_ASSET -> "Актив"
    else -> "Цель"
}

private fun String.localizedCreateButtonLabel(): String = when (this) {
    TARGET_EXPENSE_CATEGORY -> "Новая категория"
    TARGET_ASSET -> "Новый актив"
    else -> "Новый счёт"
}

private fun String.localizedCreatedTargetLabel(): String = when (this) {
    TARGET_ASSET -> "Актив"
    else -> "Счёт"
}

private fun String.localizedNewTargetTitle(): String = when (this) {
    TARGET_INVESTMENT_ASSET_CATEGORY -> "Новая инвестиционная категория"
    TARGET_ASSET -> "Новый актив"
    else -> "Новый счёт"
}

private fun String.localizedNameLabel(): String = when (this) {
    TARGET_ASSET -> "Название актива"
    else -> "Название счёта"
}

private fun String.planningAccountTypeOptions(): List<PlanningAccountTypeOption> {
    return if (this == TARGET_ASSET || this == TARGET_INVESTMENT_ASSET_CATEGORY) {
        listOf(
            PlanningAccountTypeOption("brokerage", "Брокер"),
            PlanningAccountTypeOption("deposit", "Вклад"),
            PlanningAccountTypeOption("metal", "Металл"),
            PlanningAccountTypeOption("other", "Другое"),
        )
    } else {
        listOf(
            PlanningAccountTypeOption("bank", "Банк"),
            PlanningAccountTypeOption("card", "Карта"),
            PlanningAccountTypeOption("cash", "Наличные"),
        )
    }
}

private fun String.localizedAllocationMode(): String = when (this) {
    ALLOCATION_PERCENT -> "Процент"
    else -> "Сумма"
}

private fun String.localizedRecurrenceType(): String = when (this) {
    RECURRENCE_ONE_OFF -> "Разовая"
    else -> "Регулярная"
}

private fun String.localizedPlanningStatus(): String = when (this) {
    "active", "planned", "on_track" -> "по плану"
    "confirmed", "completed", "done" -> "выполнено"
    "needs_attention", "target_attention", "warning", "attention" -> "требует внимания"
    "no_actuals" -> "нет фактических данных"
    "not_applicable" -> "не применяется"
    "under_plan", "underplanned", "behind" -> "ниже плана"
    "over_plan", "overplanned", "ahead" -> "выше плана"
    else -> "ожидает данных"
}

private fun PlanningAllocation.readableStatus(): String {
    val progress = progressStatus?.takeIf { it.isNotBlank() } ?: status?.takeIf { it.isNotBlank() }
    val fallback = when {
        targetType == TARGET_INVESTMENT_ASSET_CATEGORY && requiresAttention -> "Инвестиции ниже плана"
        targetType == TARGET_EXPENSE_CATEGORY && requiresAttention -> "Расходы выше плана"
        requiresAttention -> "Нужно внимание"
        else -> "Статус allocation ожидает факта"
    }
    return progress?.localizedPlanningStatus() ?: fallback
}

private fun PlanningAllocation.readableTargetName(options: List<PlanningTargetOption>): String {
    return options.firstOrNull { it.id == targetId }?.title
        ?: targetSnapshot?.planningSnapshotTitle()
        ?: targetType.localizedTargetType()
}

private fun String.planningSnapshotTitle(): String? {
    val trimmed = trim().takeIf { it.isNotBlank() && it != "null" } ?: return null
    if (!trimmed.startsWith("{")) {
        return userFacingSeedText(trimmed)
    }
    val json = runCatching { org.json.JSONObject(trimmed) }.getOrNull() ?: return null
    return listOf("name", "title", "displayName", "label")
        .firstNotNullOfOrNull { key -> json.optString(key).takeIf { it.isNotBlank() && it != "null" } }
        ?.let(::userFacingSeedText)
}

private fun PlanningAllocationDraft.estimatedMonthlyAmount(): String? {
    val target = goalTargetAmount.normalizedPlanningAmount()?.let { BigDecimal(it) } ?: return null
    if (target <= BigDecimal.ZERO) return null
    val currentMonth = YearMonth.now()
    val due = runCatching { YearMonth.parse(goalDueMonth) }.getOrNull() ?: return null
    val months = ((due.year - currentMonth.year) * 12 + due.monthValue - currentMonth.monthValue + 1).coerceAtLeast(1)
    return target.divide(BigDecimal(months), 2, RoundingMode.HALF_UP).toPlainString()
}

private fun String.planningDecimalInput(): String {
    return filter { it.isDigit() || it == '.' || it == ',' }.replace(',', '.')
}

private fun String.normalizedPlanningAmount(): String? {
    val normalized = trim().replace(',', '.')
    if (normalized.isBlank()) return null
    val value = runCatching { BigDecimal(normalized) }.getOrNull() ?: return null
    if (value <= BigDecimal.ZERO) return null
    return value.setScale(2, RoundingMode.HALF_UP).toPlainString()
}

private fun String.isPositivePlanningAmount(): Boolean {
    return runCatching { BigDecimal(trim().replace(',', '.')) > BigDecimal.ZERO }.getOrDefault(false)
}

private fun String.toPlanningDay(): Int? {
    return toIntOrNull()?.takeIf { it in 1..31 }
}

private fun String.planningMoney(currency: String): String {
    val amount = runCatching { BigDecimal(this) }.getOrDefault(BigDecimal.ZERO)
    val formatter = NumberFormat.getNumberInstance(Locale("ru", "RU")).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }
    return "${formatter.format(amount)} $currency"
}

private fun nextPlanningMonth(): String = YearMonth.now().plusMonths(1).toString()

private fun planningMonthChoices(): List<PlanningMonthChoice> {
    val current = YearMonth.now()
    val next = current.plusMonths(1)
    val yearMonths = (1..12).map { month -> YearMonth.of(current.year, month) }
    return (listOf(current, next) + yearMonths)
        .distinct()
        .sorted()
        .map { month ->
            val title = when (month) {
                current -> "Текущий: ${month.localizedPlanningMonth()}"
                next -> "Следующий: ${month.localizedPlanningMonth()}"
                else -> month.localizedPlanningMonth()
            }
            PlanningMonthChoice(month = month.toString(), title = title)
        }
}

private fun planningGoalMonthChoices(): List<PlanningMonthChoice> {
    val current = YearMonth.now()
    return (1..36)
        .map { current.plusMonths(it.toLong()) }
        .map { month ->
            val monthsAhead = ((month.year - current.year) * 12 + month.monthValue - current.monthValue)
            val prefix = when (monthsAhead) {
                1 -> "Следующий"
                6 -> "6 мес."
                12 -> "1 год"
                24 -> "2 года"
                36 -> "3 года"
                else -> null
            }
            PlanningMonthChoice(
                month = month.toString(),
                title = prefix?.let { "$it: ${month.localizedPlanningMonth()}" } ?: month.localizedPlanningMonth(),
            )
        }
}

private fun String.localizedPlanningMonth(): String {
    return runCatching { YearMonth.parse(this).localizedPlanningMonth() }.getOrDefault(this)
}

private fun YearMonth.localizedPlanningMonth(): String {
    val monthName = month.getDisplayName(TextStyle.FULL_STANDALONE, Locale("ru", "RU"))
    return "${monthName.replaceFirstChar { it.uppercase(Locale("ru", "RU")) }} $year"
}

private fun ApiResult.Failure.planningMessage(): String {
    return when {
        message.isNotBlank() -> message.userFacingPlanningFailure()
        statusCode == 401 -> "Сессия истекла. Войдите снова."
        statusCode == 403 -> "Нет доступа к планированию."
        statusCode != null && statusCode >= 500 -> "Ошибка сервера планирования. Попробуйте позже."
        else -> "Не удалось выполнить действие планирования"
    }
}

private fun String.userFacingPlanningFailure(): String {
    return when {
        contains("not supported", ignoreCase = true) -> "Планирование пока не поддерживается этим клиентом"
        contains("recurrenceType", ignoreCase = true) -> "Сервер ещё не принял периодичность распределения"
        contains("goalTargetAmount", ignoreCase = true) || contains("goalDueMonth", ignoreCase = true) -> "Сервер ещё не принял параметры цели накопления"
        contains("HTTP 401", ignoreCase = true) -> "Сессия истекла. Войдите снова."
        contains("HTTP 403", ignoreCase = true) -> "Нет доступа к планированию."
        else -> this
    }
}
