package com.finance.mvp.ui

enum class AppSection(
    val title: String,
    val subtitle: String,
) {
    Overview(
        title = "Обзор",
        subtitle = "Сессия, баланс, расходы и доходы из live API.",
    ),
    Accounts(
        title = "Счета",
        subtitle = "Видимые денежные счета текущего пользователя.",
    ),
    Categories(
        title = "Категории",
        subtitle = "Доходы и расходы для ручной классификации.",
    ),
    Operations(
        title = "Операции",
        subtitle = "Список ручных доходов, расходов и переводов.",
    ),
    Transfers(
        title = "Переводы",
        subtitle = "Жизненный цикл переводов через transactionType=transfer.",
    ),
    Reports(
        title = "Отчеты",
        subtitle = "Сводка по доступным данным за выбранный контур.",
    ),
}

fun mvpSections(): List<AppSection> = AppSection.entries
