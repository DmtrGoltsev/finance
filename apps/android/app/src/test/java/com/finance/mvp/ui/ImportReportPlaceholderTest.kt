package com.finance.mvp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImportReportPlaceholderTest {
    @Test
    fun exposesContractReportTypes() {
        val values = ImportReportType.entries.map { it.title to it.apiValue }

        assertEquals(
            listOf(
                "Общий" to "generic_finance_report",
                "Банк" to "bank_statement",
                "Брокер" to "brokerage_report",
                "Вклад" to "deposit_report",
                "Металлы" to "metals_report",
            ),
            values,
        )
    }

    @Test
    fun placeholderNeverConfirmsOrChangesData() {
        val preview = importReportPlaceholderPreview(
            ImportReportDraft(
                reportType = ImportReportType.Bank,
                fileName = "statement.pdf",
                targetScope = ImportTargetScope.Personal,
            ),
        )

        assertFalse(preview.canConfirm)
        assertFalse(preview.willChangeData)
        assertEquals("Импорт пока не выполняется", preview.statusText)
        assertEquals("Файл не разобран", preview.fileStatusText)
        assertTrue(preview.warnings.any { it == "Данные не изменятся без подтверждения." })
        assertTrue(preview.warnings.any { it == "Содержимое файла не сохраняется и не разбирается." })
    }

    @Test
    fun recognitionSectionsStayFixedAndUnrecognized() {
        val sections = importRecognitionSections()

        assertEquals(
            listOf("accounts_assets", "transactions", "categories", "transfers", "brokerage_deposits_metals"),
            sections.map { it.key },
        )
        assertTrue(sections.all { it.status == "not_recognized_yet" })
    }

    @Test
    fun copyDoesNotPromiseFinishedImport() {
        val preview = importReportPlaceholderPreview(ImportReportDraft())
        val allText = buildString {
            append(preview.title)
            append(' ')
            append(preview.statusText)
            append(' ')
            append(preview.fileStatusText)
            append(' ')
            append(preview.summaryText)
            append(' ')
            append(preview.scopeText)
            append(' ')
            append(preview.sections.joinToString(" ") { "${it.title} ${it.text}" })
            append(' ')
            append(preview.warnings.joinToString(" "))
        }

        listOf(
            "Импортировать",
            "Импорт выполнен",
            "Мы распознали операции",
            "Операции будут добавлены",
            "Счета будут созданы",
            "Категории будут назначены автоматически",
            "Подключить банк/брокера",
            "Загрузить и обработать файл",
        ).forEach { forbidden ->
            assertFalse(allText.contains(forbidden, ignoreCase = true))
        }
    }
}
