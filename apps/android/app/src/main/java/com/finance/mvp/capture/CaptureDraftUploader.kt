package com.finance.mvp.capture

import android.content.Context
import com.finance.mvp.BuildConfig
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.session.AndroidSecureTokenStore

internal object CaptureDraftUploader {
    suspend fun upload(context: Context, candidate: CaptureCandidate): Boolean {
        val apiClient = LiveFinanceApiClient(
            config = ApiConfig(BuildConfig.FINANCE_API_BASE_URL),
            tokenStore = AndroidSecureTokenStore(context.applicationContext),
        )
        return apiClient.createCaptureDraft(candidate.toCreateRequest()) is ApiResult.Success
    }
}
