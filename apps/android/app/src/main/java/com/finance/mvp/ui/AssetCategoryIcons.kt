package com.finance.mvp.ui

import androidx.annotation.DrawableRes
import androidx.compose.ui.graphics.Color
import com.finance.mvp.R
import java.util.Locale

data class AssetCategoryIconOption(
    val key: String,
    val title: String,
    @DrawableRes val icon: Int,
    val tint: Color,
)

internal val AssetCategoryIconOptions = listOf(
    AssetCategoryIconOption("card", "Карта", R.drawable.ic_card_24, Color(0xFF4267D5)),
    AssetCategoryIconOption("bank", "Банк", R.drawable.ic_bank_24, Color(0xFF256B5F)),
    AssetCategoryIconOption("cash", "Наличные", R.drawable.ic_cash_24, Color(0xFF9A6A24)),
    AssetCategoryIconOption("deposit", "Вклад", R.drawable.ic_savings_24, Color(0xFF6D5BD0)),
    AssetCategoryIconOption("brokerage", "Брокер", R.drawable.ic_chart_24, Color(0xFF227C9D)),
    AssetCategoryIconOption("metal", "Металл", R.drawable.ic_gold_bar_24, Color(0xFF8A6A12)),
    AssetCategoryIconOption("wallet", "Кошелек", R.drawable.ic_wallet_24, Color(0xFF6A6F7A)),
    AssetCategoryIconOption("coin", "Монеты", R.drawable.ic_coin_24, Color(0xFFB4871F)),
)

internal fun assetCategoryIcon(iconKey: String?, assetType: String): AssetCategoryIconOption {
    val normalized = iconKey?.trim()?.lowercase(Locale.US).orEmpty()
    return AssetCategoryIconOptions.firstOrNull { it.key == normalized }
        ?: AssetCategoryIconOptions.firstOrNull { it.key == defaultAssetCategoryIconKey(assetType) }
        ?: AssetCategoryIconOptions.first()
}

internal fun defaultAssetCategoryIconKey(assetType: String): String {
    return when (assetType.trim().lowercase(Locale.US)) {
        "card" -> "card"
        "cash" -> "cash"
        "deposit" -> "deposit"
        "brokerage" -> "brokerage"
        "metal" -> "metal"
        "bank" -> "bank"
        else -> "bank"
    }
}
