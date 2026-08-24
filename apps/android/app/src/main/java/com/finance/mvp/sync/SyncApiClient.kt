package com.finance.mvp.sync

import com.finance.mvp.api.ApiResult
import com.finance.mvp.api.AuthenticatedSessionLease
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.api.SyncPullRequest
import com.finance.mvp.api.SyncPullResponse
import com.finance.mvp.api.SyncPushRequest
import com.finance.mvp.api.SyncPushResponse

interface SyncApiClient {
    suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse>
    suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse>
    suspend fun bindSession(userId: String): ApiResult<SyncApiClient> = ApiResult.Success(this)
    suspend fun <T> withSessionLease(block: suspend () -> T): ApiResult<T> = ApiResult.Success(block())
}

class FinanceSyncApiClientAdapter(
    private val apiClient: LiveFinanceApiClient,
) : SyncApiClient {
    override suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> {
        return apiClient.syncPush(request)
    }

    override suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> {
        return apiClient.syncPull(request)
    }

    override suspend fun bindSession(userId: String): ApiResult<SyncApiClient> {
        return when (val result = apiClient.captureAuthenticatedSessionLease(userId)) {
            is ApiResult.Success -> ApiResult.Success(SessionBoundFinanceSyncApiClient(apiClient, result.value))
            is ApiResult.Failure -> result
        }
    }
}

private class SessionBoundFinanceSyncApiClient(
    private val apiClient: LiveFinanceApiClient,
    private val lease: AuthenticatedSessionLease,
) : SyncApiClient {
    override suspend fun syncPush(request: SyncPushRequest): ApiResult<SyncPushResponse> {
        return apiClient.syncPushWithLease(request, lease)
    }

    override suspend fun syncPull(request: SyncPullRequest): ApiResult<SyncPullResponse> {
        return apiClient.syncPullWithLease(request, lease)
    }

    override suspend fun bindSession(userId: String): ApiResult<SyncApiClient> {
        return if (lease.authenticatedUserId == userId) {
            ApiResult.Success(this)
        } else {
            apiClient.captureAuthenticatedSessionLease(userId).let { result ->
                when (result) {
                    is ApiResult.Success -> ApiResult.Success(SessionBoundFinanceSyncApiClient(apiClient, result.value))
                    is ApiResult.Failure -> result
                }
            }
        }
    }

    override suspend fun <T> withSessionLease(block: suspend () -> T): ApiResult<T> {
        return apiClient.withAuthenticatedSessionLease(lease, block)
    }
}
