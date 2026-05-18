package com.finance.mvp.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val FinanceLightColors: ColorScheme = lightColorScheme(
    primary = Color(0xFF256B5F),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD3F2EA),
    onPrimaryContainer = Color(0xFF06201B),
    secondary = Color(0xFF6E5F1F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF7E7A7),
    onSecondaryContainer = Color(0xFF221B00),
    background = Color(0xFFFBFCFA),
    onBackground = Color(0xFF191C1B),
    surface = Color(0xFFFBFCFA),
    surfaceContainer = Color(0xFFEFF3F0),
    onSurface = Color(0xFF191C1B),
    onSurfaceVariant = Color(0xFF414946),
)

@Composable
fun FinanceTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = FinanceLightColors,
        content = content,
    )
}
