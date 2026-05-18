package com.finance.mvp.ui

data class ImportReportDraft(
    val reportType: ImportReportType = ImportReportType.Generic,
    val fileName: String = "report.pdf",
    val targetScope: ImportTargetScope = ImportTargetScope.Personal,
)

data class ImportReportPlaceholderPreview(
    val title: String,
    val statusText: String,
    val fileStatusText: String,
    val summaryText: String,
    val scopeText: String,
    val sections: List<ImportRecognitionSection>,
    val warnings: List<String>,
    val canConfirm: Boolean,
    val willChangeData: Boolean,
)

data class ImportRecognitionSection(
    val key: String,
    val title: String,
    val status: String,
    val text: String,
)

enum class ImportReportType(
    val title: String,
    val apiValue: String,
) {
    Generic("Общий", "generic_finance_report"),
    Bank("Банк", "bank_statement"),
    Broker("Брокер", "brokerage_report"),
    Deposit("Вклад", "deposit_report"),
    Metals("Металлы", "metals_report"),
}

enum class ImportTargetScope(
    val title: String,
    val apiValue: String,
) {
    Personal("Личное", "personal"),
    Shared("Общее", "shared"),
}

fun importReportPlaceholderPreview(draft: ImportReportDraft): ImportReportPlaceholderPreview {
    return ImportReportPlaceholderPreview(
        title = "Предварительный просмотр импорта",
        statusText = "Импорт пока не выполняется",
        fileStatusText = "Файл не разобран",
        summaryText = "Сейчас мы показываем, какие разделы сможет проверить будущий импорт. Файл не сохраняется и не разбирается.",
        scopeText = when (draft.targetScope) {
            ImportTargetScope.Personal -> "Личный импорт будет виден только вам."
            ImportTargetScope.Shared -> "Общий импорт будет доступен только активным участникам семьи после отдельного подтверждения."
        },
        sections = importRecognitionSections(),
        warnings = listOf(
            "Данные не изменятся без подтверждения.",
            "Содержимое файла не сохраняется и не разбирается.",
            "Личные данные видны только владельцу.",
            "Распознавание отчета появится позже.",
        ),
        canConfirm = false,
        willChangeData = false,
    )
}

fun importRecognitionSections(): List<ImportRecognitionSection> = listOf(
    ImportRecognitionSection(
        key = "accounts_assets",
        title = "Счета и активы",
        status = "not_recognized_yet",
        text = "Файл не разобран, распознанных счетов и активов пока нет.",
    ),
    ImportRecognitionSection(
        key = "transactions",
        title = "Операции",
        status = "not_recognized_yet",
        text = "Операции не распознаны и не добавлены.",
    ),
    ImportRecognitionSection(
        key = "categories",
        title = "Категории",
        status = "not_recognized_yet",
        text = "Категории не распознаны и не созданы.",
    ),
    ImportRecognitionSection(
        key = "transfers",
        title = "Переводы",
        status = "not_recognized_yet",
        text = "Переводы не распознаны и не созданы.",
    ),
    ImportRecognitionSection(
        key = "brokerage_deposits_metals",
        title = "Брокеры, вклады и металлы",
        status = "not_recognized_yet",
        text = "Специальные активы пока не обрабатываются.",
    ),
)
