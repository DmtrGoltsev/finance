package com.finance.mvp.ui

enum class AppSection(
    val title: String,
    val subtitle: String,
) {
    Home(
        title = "Главная",
        subtitle = "Капитал, расходы месяца и последние движения.",
    ),
    Operations(
        title = "Операции",
        subtitle = "Расходы, доходы и переводы без смешивания с тратами.",
    ),
    Assets(
        title = "Активы",
        subtitle = "Карты, банки, наличные, вклады, брокерские счета и металлы.",
    ),
    Categories(
        title = "Категории расходов",
        subtitle = "Список, добавление и быстрые правки категорий расходов.",
    ),
    Analytics(
        title = "Аналитика",
        subtitle = "Категории, структура капитала и денежный поток.",
    ),
}

fun financeSections(): List<AppSection> = AppSection.entries
