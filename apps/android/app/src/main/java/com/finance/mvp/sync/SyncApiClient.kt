package com.finance.mvp.sync

import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.FinanceApiClient
import com.finance.mvp.api.SyncPullRequest
import com.finance.mvp.api.SyncPullResponse
import com.finance.mvp.api.SyncPushRequest
import com.finance.mvp.api.SyncPushResponse

interface SyncApiClient {
    suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse>
    suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse>
}

class FinanceSyncApiClientAdapter(
    private val apiClient: FinanceApiClient,
) : SyncApiClient {
    override suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> {
        return apiClient.syncPush(request)
    }

    override suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> {
        return apiClient.syncPull(request)
    }
}
