package com.finance.mvp

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.finance.mvp.api.ApiConfig
import com.finance.mvp.api.LiveFinanceApiClient
import com.finance.mvp.session.AndroidSecureTokenStore
import com.finance.mvp.ui.FinanceApp
import com.finance.mvp.ui.theme.FinanceTheme

class MainActivity : ComponentActivity() {
    private var openPlanningRequestKey by mutableStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()

        val apiConfig = ApiConfig(baseUrl = BuildConfig.FINANCE_API_BASE_URL)
        val tokenStore = AndroidSecureTokenStore(applicationContext)
        val apiClient = LiveFinanceApiClient(apiConfig, tokenStore)
        if (shouldOpenPlanning(intent)) {
            openPlanningRequestKey += 1
        }

        setContent {
            FinanceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    FinanceApp(
                        apiClient = apiClient,
                        initialOpenPlanning = openPlanningRequestKey > 0,
                        openPlanningRequestKey = openPlanningRequestKey,
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (shouldOpenPlanning(intent)) {
            openPlanningRequestKey += 1
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), POST_NOTIFICATIONS_REQUEST_CODE)
    }

    private fun shouldOpenPlanning(intent: android.content.Intent?): Boolean =
        intent?.getBooleanExtra("openPlanning", false) == true ||
            intent?.getStringExtra("openSection") == "analytics"

    private companion object {
        const val POST_NOTIFICATIONS_REQUEST_CODE = 1301
    }
}
