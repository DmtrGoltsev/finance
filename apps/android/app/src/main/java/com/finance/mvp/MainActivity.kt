package com.finance.mvp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.session.AndroidSecureTokenStore
import com.finance.mvp.ui.FinanceApp
import com.finance.mvp.ui.theme.FinanceTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val apiConfig = ApiConfig(baseUrl = BuildConfig.FINANCE_API_BASE_URL)
        val tokenStore = AndroidSecureTokenStore(applicationContext)
        val apiClient = LiveFinanceApiClient(apiConfig, tokenStore)

        setContent {
            FinanceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    FinanceApp(apiClient = apiClient)
                }
            }
        }
    }
}
