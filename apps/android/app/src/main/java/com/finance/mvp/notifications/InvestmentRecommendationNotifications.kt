package com.finance.mvp.notifications

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.finance.mvp.MainActivity

const val INVESTMENT_RECOMMENDATIONS_DEEP_LINK = "finance://investments/recommendations"

fun investmentRecommendationsIntent(context: Context): Intent =
    Intent(Intent.ACTION_VIEW, Uri.parse(INVESTMENT_RECOMMENDATIONS_DEEP_LINK), context, MainActivity::class.java)
        .putExtra("openInvestmentRecommendations", true)
        .putExtra("openSection", "investment_recommendations")

/** Firebase-free boundary. A later integration may implement this with FCM HTTP v1 registration. */
fun interface InvestmentPushTokenRegistrar {
    suspend fun registerToken(token: String): Result<Unit>
}

object NoOpInvestmentPushTokenRegistrar : InvestmentPushTokenRegistrar {
    override suspend fun registerToken(token: String): Result<Unit> =
        Result.failure(UnsupportedOperationException("FCM не настроен для этой сборки"))
}
