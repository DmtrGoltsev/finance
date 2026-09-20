package com.finance.mvp.ui.investments

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.InvestmentInstrumentType
import com.finance.mvp.api.InvestmentPolicy
import com.finance.mvp.api.InvestmentRiskBucket
import com.finance.mvp.api.PortfolioPosition
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.api.RecommendationAction
import com.finance.mvp.api.RecommendationReport
import com.finance.mvp.api.RecommendationStatus
import com.finance.mvp.api.TaxAccountType
import com.finance.mvp.investments.InvestmentOverview
import com.finance.mvp.investments.InvestmentRepository
import com.finance.mvp.investments.PortfolioOcrParser
import com.finance.mvp.investments.PortfolioScreenshotRecognizer
import com.finance.mvp.investments.newestSnapshotsPerBroker
import com.finance.mvp.investments.recommendationStatus
import com.finance.mvp.local.CachedInvestmentRecommendation
import com.finance.mvp.local.FinanceLocalDatabase
import com.finance.mvp.local.InvestmentStore
import java.math.BigDecimal
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private data class PortfolioDraft(
    val importId: String,
    val brokerage: Brokerage,
    val imageUris: List<Uri>,
    val positions: List<PortfolioPosition>,
    val freeCash: String = "0",
    val monthlyContribution: String = "0",
)

@Composable
fun InvestmentPortfolioPanel(
    apiClient: FinanceApiClient,
    database: FinanceLocalDatabase,
    userId: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val repository = remember(apiClient, database) {
        InvestmentRepository(apiClient, InvestmentStore(database))
    }
    val recognizer = remember(context) { PortfolioScreenshotRecognizer(context.applicationContext) }
    val parser = remember { PortfolioOcrParser() }
    var overview by remember(userId) { mutableStateOf(InvestmentOverview()) }
    var loading by rememberSaveable(userId) { mutableStateOf(true) }
    var message by rememberSaveable(userId) { mutableStateOf<String?>(null) }
    var brokerDialog by rememberSaveable { mutableStateOf(false) }
    var selectedBroker by rememberSaveable { mutableStateOf(Brokerage.Sinara) }
    var draft by remember { mutableStateOf<PortfolioDraft?>(null) }
    var activeJobId by rememberSaveable(userId) { mutableStateOf<String?>(null) }

    suspend fun reload() {
        loading = true
        overview = withContext(Dispatchers.IO) { repository.load(userId) }
        message = overview.message
        activeJobId = overview.recommendations.firstOrNull {
            it.job.status in setOf(RecommendationStatus.Queued, RecommendationStatus.Collecting, RecommendationStatus.Analyzing)
        }?.job?.id
        loading = false
    }

    LaunchedEffect(userId) { reload() }

    LaunchedEffect(activeJobId) {
        val jobId = activeJobId ?: return@LaunchedEffect
        while (true) {
            delay(5_000)
            when (val result = withContext(Dispatchers.IO) { repository.refreshRecommendation(userId, jobId) }) {
                is ApiResult.Success -> {
                    overview = overview.copy(recommendations = repository.cachedRecommendations(userId))
                    if (result.value.job.status in setOf(RecommendationStatus.Ready, RecommendationStatus.Failed)) {
                        activeJobId = null
                        break
                    }
                }
                is ApiResult.Failure -> {
                    message = "Статус не обновился. Повторим при следующем открытии."
                    break
                }
            }
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(20)) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        scope.launch {
            loading = true
            message = "Создаём импорт и распознаём ${uris.size} скриншотов"
            when (
                val importResult = withContext(Dispatchers.IO) {
                    repository.beginImport(selectedBroker, uris.size)
                }
            ) {
                is ApiResult.Failure -> {
                    loading = false
                    message = "Импорт доступен только онлайн: ${importResult.message}"
                }
                is ApiResult.Success -> {
                    val recognized = runCatching {
                        withContext(Dispatchers.IO) { recognizer.recognize(uris) }
                    }
                    val positions = recognized.getOrNull()?.let { parser.parse(selectedBroker, it) }.orEmpty()
                    draft = PortfolioDraft(
                        importId = importResult.value.id,
                        brokerage = selectedBroker,
                        imageUris = uris,
                        positions = positions,
                    )
                    loading = false
                    message = if (positions.isEmpty()) {
                        "Автораспознавание не нашло позиции. Добавьте их вручную перед подтверждением."
                    } else {
                        "Проверьте каждое поле перед подтверждением."
                    }
                }
            }
        }
    }

    InvestmentPortfolioContent(
        overview = overview,
        loading = loading,
        message = message,
        modifier = modifier,
        onRefresh = { scope.launch { reload() } },
        onAddPortfolio = { brokerDialog = true },
        onUpdatePolicy = { policy ->
            scope.launch {
                loading = true
                when (val result = withContext(Dispatchers.IO) { repository.updatePolicy(policy) }) {
                    is ApiResult.Success -> {
                        overview = overview.copy(policy = result.value, isOffline = false)
                        message = "Профиль сохранён"
                    }
                    is ApiResult.Failure -> message = "Профиль не сохранён: ${result.message}"
                }
                loading = false
            }
        },
        onStartRecommendation = {
            val snapshotIds = newestSnapshotsPerBroker(overview.snapshots).map { it.id }
            scope.launch {
                loading = true
                when (val result = withContext(Dispatchers.IO) { repository.startRecommendation(userId, snapshotIds) }) {
                    is ApiResult.Success -> {
                        activeJobId = result.value.id
                        overview = overview.copy(recommendations = repository.cachedRecommendations(userId), isOffline = false)
                        message = "Анализ поставлен в очередь"
                    }
                    is ApiResult.Failure -> message = "Анализ доступен только онлайн: ${result.message}"
                }
                loading = false
            }
        },
    )

    if (brokerDialog) {
        BrokerPickerDialog(
            selected = selectedBroker,
            onSelected = { selectedBroker = it },
            onDismiss = { brokerDialog = false },
            onContinue = {
                brokerDialog = false
                picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
            },
        )
    }

    draft?.let { current ->
        PortfolioDraftSheet(
            draft = current,
            saving = loading,
            onChange = { draft = it },
            onDismiss = {
                draft = null
                message = "Импорт не подтверждён"
            },
            onConfirm = {
                val error = validateDraft(current)
                if (error != null) {
                    message = error
                    return@PortfolioDraftSheet
                }
                scope.launch {
                    loading = true
                    when (
                        val result = withContext(Dispatchers.IO) {
                            repository.confirmImport(
                                userId = userId,
                                importId = current.importId,
                                freeCash = current.freeCash.normalizedMoney(),
                                monthlyContribution = current.monthlyContribution.normalizedMoney(),
                                positions = current.positions,
                            )
                        }
                    ) {
                        is ApiResult.Success -> {
                            draft = null // URI references and OCR-derived draft leave memory here.
                            overview = withContext(Dispatchers.IO) { repository.load(userId) }
                            message = "Портфель ${result.value.brokerage.title} сохранён"
                        }
                        is ApiResult.Failure -> message = "Не удалось подтвердить портфель: ${result.message}"
                    }
                    loading = false
                }
            },
        )
    }
}

@Composable
internal fun InvestmentPortfolioContent(
    overview: InvestmentOverview,
    loading: Boolean,
    message: String?,
    modifier: Modifier = Modifier,
    onRefresh: () -> Unit,
    onAddPortfolio: () -> Unit,
    onUpdatePolicy: (InvestmentPolicy) -> Unit,
    onStartRecommendation: () -> Unit,
) {
    val latest = newestSnapshotsPerBroker(overview.snapshots)
    Column(
        modifier = modifier.fillMaxWidth().testTag("investment-portfolio-panel"),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("Инвестиционные портфели", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("Синара, СберИнвестиции и Финам", style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = onRefresh, enabled = !loading) { Text("Обновить") }
        }
        if (loading) CircularProgressIndicator(modifier = Modifier.testTag("investment-loading"))
        message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (overview.isOffline) {
            AssistChip(onClick = onRefresh, label = { Text("Офлайн: сохранённая копия") })
        }
        CombinedPortfolioCard(latest)
        latest.forEach { PortfolioSnapshotCard(it) }
        OutlinedButton(onClick = onAddPortfolio, enabled = !loading && !overview.isOffline, modifier = Modifier.fillMaxWidth()) {
            Text("Загрузить скриншоты портфеля")
        }
        InvestmentPolicyCard(overview.policy, loading, onUpdatePolicy)
        Button(
            onClick = onStartRecommendation,
            enabled = latest.isNotEmpty() && !loading && !overview.isOffline && overview.recommendations.none {
                it.job.status in setOf(RecommendationStatus.Queued, RecommendationStatus.Collecting, RecommendationStatus.Analyzing)
            },
            modifier = Modifier.fillMaxWidth().testTag("refresh-investment-recommendations"),
        ) { Text("Обновить рекомендации") }
        overview.recommendations.forEach { RecommendationCard(it) }
        if (overview.snapshots.size > latest.size) SnapshotHistoryCard(overview.snapshots)
    }
}

@Composable
private fun CombinedPortfolioCard(snapshots: List<PortfolioSnapshot>) {
    val total = snapshots.fold(BigDecimal.ZERO) { sum, snapshot -> sum + snapshot.totalValue.toDecimal() }
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Объединённый портфель", fontWeight = FontWeight.SemiBold)
            Text("${total.money()} RUB", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text("${snapshots.size} брокерских счетов • ${snapshots.sumOf { it.positions.size }} позиций", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun PortfolioSnapshotCard(snapshot: PortfolioSnapshot) {
    var expanded by rememberSaveable(snapshot.id) { mutableStateOf(false) }
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(snapshot.brokerage.title, fontWeight = FontWeight.SemiBold)
                    Text("${snapshot.positions.size} позиций • ${snapshot.observedAt.displayTimestamp()}", style = MaterialTheme.typography.bodySmall)
                }
                Text("${snapshot.totalValue.toDecimal().money()} ${snapshot.currency}", fontWeight = FontWeight.SemiBold)
            }
            Text("Свободно: ${snapshot.freeCash.toDecimal().money()} • Пополнение: ${snapshot.monthlyContribution.toDecimal().money()}", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Скрыть состав" else "Показать состав") }
            if (expanded) snapshot.positions.forEach { position ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) {
                        Text(position.instrumentName, style = MaterialTheme.typography.bodyMedium)
                        Text(listOfNotNull(position.ticker, position.isin, position.instrumentType.title).joinToString(" • "), style = MaterialTheme.typography.bodySmall)
                    }
                    Text(position.marketValue.toDecimal().money())
                }
            }
        }
    }
}

@Composable
private fun InvestmentPolicyCard(policy: InvestmentPolicy, loading: Boolean, onSave: (InvestmentPolicy) -> Unit) {
    var edit by rememberSaveable { mutableStateOf(false) }
    var conservative by rememberSaveable(policy.conservativePercent) { mutableStateOf(policy.conservativePercent) }
    var moderate by rememberSaveable(policy.moderatePercent) { mutableStateOf(policy.moderatePercent) }
    var aggressive by rememberSaveable(policy.aggressivePercent) { mutableStateOf(policy.aggressivePercent) }
    var tolerance by rememberSaveable(policy.tolerancePercent) { mutableStateOf(policy.tolerancePercent) }
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Профиль риска", fontWeight = FontWeight.SemiBold)
            Text("Консервативный $conservative% • Умеренный $moderate% • Агрессивный $aggressive%")
            Text("Допустимое отклонение ±$tolerance п.п.", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { edit = true }, enabled = !loading) { Text("Настроить") }
        }
    }
    if (edit) {
        AlertDialog(
            onDismissRequest = { edit = false },
            title = { Text("Профиль риска") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    PercentField("Консервативный", conservative) { conservative = it }
                    PercentField("Умеренный", moderate) { moderate = it }
                    PercentField("Агрессивный", aggressive) { aggressive = it }
                    PercentField("Отклонение", tolerance) { tolerance = it }
                    if (listOf(conservative, moderate, aggressive).sumOf { it.toDecimal() } != BigDecimal("100")) {
                        Text("Доли должны составлять 100%", color = MaterialTheme.colorScheme.error)
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        onSave(InvestmentPolicy(conservative, moderate, aggressive, tolerance, policy.id, policy.version))
                        edit = false
                    },
                    enabled = listOf(conservative, moderate, aggressive).sumOf { it.toDecimal() } == BigDecimal("100"),
                ) { Text("Сохранить") }
            },
            dismissButton = { TextButton(onClick = { edit = false }) { Text("Отмена") } },
        )
    }
}

@Composable
private fun PercentField(label: String, value: String, onValue: (String) -> Unit) {
    OutlinedTextField(value, { onValue(it.decimalInput()) }, label = { Text("$label, %") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
}

@Composable
private fun RecommendationCard(cached: CachedInvestmentRecommendation) {
    val status = recommendationStatus(cached.job, cached.report)
    var expanded by rememberSaveable(cached.job.id) { mutableStateOf(status in setOf(RecommendationStatus.Ready, RecommendationStatus.Stale)) }
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(
            containerColor = if (status == RecommendationStatus.Failed) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Рекомендации", fontWeight = FontWeight.SemiBold)
                Text(status.title, color = statusColor(status), fontWeight = FontWeight.SemiBold)
            }
            Text("Создано: ${cached.job.createdAt.displayTimestamp()}", style = MaterialTheme.typography.bodySmall)
            cached.job.cashFirstAdjustments.forEach { adjustment ->
                Text("${adjustment.riskBucket.title}: ${adjustment.currentPercent}% → ${adjustment.projectedPercent}% (цель ${adjustment.targetPercent}%)", style = MaterialTheme.typography.bodySmall)
            }
            cached.report?.let { report ->
                TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Скрыть отчёт" else "Открыть отчёт") }
                if (expanded) RecommendationReportBody(report)
            }
        }
    }
}

@Composable
private fun RecommendationReportBody(report: RecommendationReport) {
    Text(report.summary)
    Text("Данные на ${report.generatedAt.displayTimestamp()} • действуют до ${report.validUntil.displayTimestamp()}", style = MaterialTheme.typography.bodySmall)
    report.actions.sortedBy(RecommendationAction::priority).forEach { action ->
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text("${action.action.actionTitle()}: ${action.instrumentName}", fontWeight = FontWeight.SemiBold)
                Text("${action.currentPercent}% → ${action.targetPercent}% • ${action.amount.toDecimal().money()} RUB")
                Text(action.rationale, style = MaterialTheme.typography.bodySmall)
                Text("Риски: ${action.risks}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
    if (report.sources.isNotEmpty()) {
        Text("Источники", fontWeight = FontWeight.SemiBold)
        report.sources.forEach { source ->
            Text("${source.publisher}: ${source.title}\n${source.url}\nПолучено ${source.fetchedAt.displayTimestamp()}", style = MaterialTheme.typography.bodySmall)
        }
    }
    Text(report.disclaimer, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun SnapshotHistoryCard(snapshots: List<PortfolioSnapshot>) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    ElevatedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("История портфелей", fontWeight = FontWeight.SemiBold)
                TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Скрыть" else "Показать") }
            }
            if (expanded) snapshots.sortedByDescending { it.observedAt }.forEach {
                Text("${it.brokerage.title} • ${it.observedAt.displayTimestamp()} • ${it.totalValue.toDecimal().money()} RUB", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun BrokerPickerDialog(
    selected: Brokerage,
    onSelected: (Brokerage) -> Unit,
    onDismiss: () -> Unit,
    onContinue: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Выберите брокера") },
        text = { Column { Brokerage.entries.forEach { broker -> FilterChip(selected == broker, { onSelected(broker) }, { Text(broker.title) }) } } },
        confirmButton = { TextButton(onClick = onContinue) { Text("Выбрать скриншоты") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PortfolioDraftSheet(
    draft: PortfolioDraft,
    saving: Boolean,
    onChange: (PortfolioDraft) -> Unit,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.fillMaxWidth().heightIn(max = 720.dp).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Проверьте портфель", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("${draft.brokerage.title} • ${draft.imageUris.size} скриншотов", style = MaterialTheme.typography.bodySmall)
            MoneyField("Свободные деньги", draft.freeCash) { onChange(draft.copy(freeCash = it)) }
            MoneyField("Ежемесячное пополнение", draft.monthlyContribution) { onChange(draft.copy(monthlyContribution = it)) }
            draft.positions.forEachIndexed { index, position ->
                PositionEditor(
                    index = index,
                    position = position,
                    onChange = { updated -> onChange(draft.copy(positions = draft.positions.toMutableList().also { it[index] = updated })) },
                    onDelete = { onChange(draft.copy(positions = draft.positions.toMutableList().also { it.removeAt(index) })) },
                )
            }
            OutlinedButton(
                onClick = {
                    onChange(
                        draft.copy(
                            positions = draft.positions + PortfolioPosition(
                                instrumentName = "",
                                instrumentType = InvestmentInstrumentType.Stock,
                                riskBucket = InvestmentRiskBucket.Aggressive,
                                quantity = "0",
                                marketValue = "0",
                            ),
                        ),
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Добавить позицию") }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, enabled = !saving, modifier = Modifier.weight(1f)) { Text("Отмена") }
                Button(onClick = onConfirm, enabled = !saving, modifier = Modifier.weight(1f)) { Text(if (saving) "Сохраняем" else "Подтвердить") }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun PositionEditor(index: Int, position: PortfolioPosition, onChange: (PortfolioPosition) -> Unit, onDelete: () -> Unit) {
    var advanced by rememberSaveable(index) { mutableStateOf(false) }
    ElevatedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Позиция ${index + 1}", fontWeight = FontWeight.SemiBold)
                TextButton(onClick = onDelete) { Text("Удалить", color = MaterialTheme.colorScheme.error) }
            }
            Field("Название", position.instrumentName) { onChange(position.copy(instrumentName = it)) }
            Field("Тикер", position.ticker.orEmpty()) { onChange(position.copy(ticker = it.uppercase().ifBlank { null })) }
            Field("ISIN", position.isin.orEmpty()) { onChange(position.copy(isin = it.uppercase().ifBlank { null })) }
            EnumChips(InvestmentInstrumentType.entries, position.instrumentType, { onChange(position.copy(instrumentType = it)) }) { it.title }
            EnumChips(InvestmentRiskBucket.entries, position.riskBucket, { onChange(position.copy(riskBucket = it)) }) { it.title }
            MoneyField("Количество", position.quantity) { onChange(position.copy(quantity = it)) }
            MoneyField("Текущая цена", position.marketPrice.orEmpty()) { onChange(position.copy(marketPrice = it.ifBlank { null })) }
            MoneyField("Текущая стоимость", position.marketValue) { onChange(position.copy(marketValue = it)) }
            MoneyField("Средняя цена покупки", position.averagePrice.orEmpty()) { onChange(position.copy(averagePrice = it.ifBlank { null })) }
            TextButton(onClick = { advanced = !advanced }) { Text(if (advanced) "Скрыть облигации, налоги и комиссии" else "Облигации, налоги и комиссии") }
            if (advanced) {
                MoneyField("Номинал", position.nominal.orEmpty()) { onChange(position.copy(nominal = it.ifBlank { null })) }
                MoneyField("НКД", position.accruedInterest.orEmpty()) { onChange(position.copy(accruedInterest = it.ifBlank { null })) }
                MoneyField("Купон, %", position.couponRate.orEmpty()) { onChange(position.copy(couponRate = it.ifBlank { null })) }
                Field("Дата погашения ГГГГ-ММ-ДД", position.maturityDate.orEmpty()) { onChange(position.copy(maturityDate = it.ifBlank { null })) }
                EnumChips(TaxAccountType.entries, position.taxAccountType, { onChange(position.copy(taxAccountType = it)) }) { it.title }
                Field("Дата начала владения ГГГГ-ММ-ДД", position.holdingStartedAt.orEmpty()) { onChange(position.copy(holdingStartedAt = it.ifBlank { null })) }
                MoneyField("Комиссия, %", position.estimatedFeeRate.orEmpty()) { onChange(position.copy(estimatedFeeRate = it.ifBlank { null })) }
            }
        }
    }
}

@Composable
private fun Field(label: String, value: String, onValue: (String) -> Unit) {
    OutlinedTextField(value, onValue, label = { Text(label) }, singleLine = true, modifier = Modifier.fillMaxWidth())
}

@Composable
private fun MoneyField(label: String, value: String, onValue: (String) -> Unit) {
    OutlinedTextField(value, { onValue(it.decimalInput()) }, label = { Text(label) }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth())
}

@Composable
private fun <T> EnumChips(values: List<T>, selected: T, onSelected: (T) -> Unit, title: (T) -> String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        values.forEach { value -> FilterChip(value == selected, { onSelected(value) }, { Text(title(value)) }) }
    }
}

private fun validateDraft(draft: PortfolioDraft): String? {
    if (draft.positions.isEmpty()) return "Добавьте хотя бы одну позицию"
    if (draft.freeCash.toDecimalOrNull() == null || draft.monthlyContribution.toDecimalOrNull() == null) return "Проверьте свободные деньги и пополнение"
    draft.positions.forEachIndexed { index, position ->
        if (position.instrumentName.isBlank()) return "Позиция ${index + 1}: укажите название"
        if (position.ticker.isNullOrBlank() && position.isin.isNullOrBlank()) return "Позиция ${index + 1}: укажите тикер или ISIN"
        if (position.quantity.toDecimalOrNull() == null || position.marketValue.toDecimalOrNull() == null) return "Позиция ${index + 1}: проверьте количество и стоимость"
    }
    return null
}

private fun String.decimalInput(): String = filter { it.isDigit() || it == ',' || it == '.' || it == '-' }.replace(',', '.')
private fun String.normalizedMoney(): String = toDecimal().max(BigDecimal.ZERO).stripTrailingZeros().toPlainString()
private fun String.toDecimal(): BigDecimal = toDecimalOrNull() ?: BigDecimal.ZERO
private fun String.toDecimalOrNull(): BigDecimal? = runCatching { BigDecimal(trim().replace(',', '.')) }.getOrNull()?.takeIf { it >= BigDecimal.ZERO }
private fun BigDecimal.money(): String = setScale(2, java.math.RoundingMode.HALF_UP).toPlainString()
private fun String.displayTimestamp(): String = replace('T', ' ').removeSuffix("Z").take(16)
private fun String.actionTitle(): String = when (this) { "keep" -> "Оставить"; "reduce" -> "Сократить"; "increase" -> "Увеличить"; "add" -> "Добавить"; else -> this }
private fun statusColor(status: RecommendationStatus): Color = when (status) {
    RecommendationStatus.Failed -> Color(0xFFC62828)
    RecommendationStatus.Ready -> Color(0xFF2E7D32)
    RecommendationStatus.Stale -> Color(0xFF8D6E00)
    else -> Color(0xFF1565C0)
}
