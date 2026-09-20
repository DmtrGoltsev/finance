package com.finance.mvp.investments

import android.content.Context
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

class PortfolioScreenshotRecognizer(
    private val context: Context,
) {
    suspend fun recognize(uris: List<Uri>): List<String> {
        require(uris.isNotEmpty()) { "Нужно выбрать хотя бы один скриншот" }
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        return try {
            uris.map { uri ->
                val image = InputImage.fromFilePath(context, uri)
                suspendCancellableCoroutine { continuation ->
                    recognizer.process(image)
                        .addOnSuccessListener { result -> if (continuation.isActive) continuation.resume(result.text) }
                        .addOnFailureListener { error -> if (continuation.isActive) continuation.resumeWithException(error) }
                }
            }
        } finally {
            recognizer.close()
        }
    }
}
