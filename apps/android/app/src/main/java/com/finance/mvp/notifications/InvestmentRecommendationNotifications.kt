package com.finance.mvp.notifications

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.finance.mvp.MainActivity
import androidx.compose.runtime.compositionLocalOf

val LocalInvestmentJobId = compositionLocalOf<String?> { null }

const val INVESTMENT_RECOMMENDATIONS_DEEP_LINK = "finance://investments/recommendations"

fun investmentRecommendationsIntent(context: Context, jobId: String? = null): Intent =
    Intent(Intent.ACTION_VIEW, Uri.parse(INVESTMENT_RECOMMENDATIONS_DEEP_LINK).buildUpon()
        .apply { jobId?.let { appendQueryParameter("jobId", it) } }.build(), context, MainActivity::class.java)
        .putExtra("openInvestmentRecommendations", true)
        .putExtra("openSection", "investment_recommendations")

/** Registration is routed through the authenticated Finance API, never directly to n8n. */
fun interface InvestmentPushTokenRegistrar {
    suspend fun registerToken(token: String): Result<Unit>
}

object NoOpInvestmentPushTokenRegistrar : InvestmentPushTokenRegistrar {
    override suspend fun registerToken(token: String): Result<Unit> =
        Result.failure(UnsupportedOperationException("FCM не настроен для этой сборки"))
}
