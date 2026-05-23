package com.finance.mvp.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class SmsCaptureReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) {
            return
        }
        val appContext = context.applicationContext
        if (!CaptureOptInStore(appContext).isSmsCaptureEnabled()) {
            return
        }

        val pendingResult = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val receivedAtMillis = System.currentTimeMillis()
                Telephony.Sms.Intents.getMessagesFromIntent(intent)
                    .groupBy { it.originatingAddress.orEmpty() to it.timestampMillis }
                    .values
                    .mapNotNull { messages ->
                        val body = messages.joinToString(separator = "") { it.messageBody.orEmpty() }
                        val sender = messages.firstOrNull()?.originatingAddress
                        CaptureParser.parseSms(
                            body = body,
                            sender = sender,
                            receivedAtMillis = messages.firstOrNull()?.timestampMillis ?: receivedAtMillis,
                        )
                    }
                    .forEach { candidate ->
                        CaptureDraftUploader.upload(appContext, candidate)
                    }
            } finally {
                pendingResult.finish()
            }
        }
    }
}

