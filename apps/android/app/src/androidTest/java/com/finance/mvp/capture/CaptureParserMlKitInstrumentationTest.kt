package com.finance.mvp.capture

import android.net.Uri
import android.os.ParcelFileDescriptor
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CaptureParserMlKitInstrumentationTest {
    @Test
    fun screenshotBaselineRunsMlKitAndParsesCategoryRows() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val screenshot = InstrumentationRegistry.getArguments().getString("financeOcrImagePath")
            ?.let { path ->
                val copied = File(context.cacheDir, "finance_ocr_baseline.jpg")
                copied.delete()
                instrumentation.uiAutomation
                    .executeShellCommand(
                        "run-as ${context.packageName} cp ${path.shellQuote()} ${copied.absolutePath.shellQuote()}",
                    )
                    .use { descriptor ->
                        assertNotNull("Unable to copy pushed baseline screenshot via shell: $path", descriptor)
                        ParcelFileDescriptor.AutoCloseInputStream(descriptor).use { input ->
                            input.readBytes()
                        }
                    }
                if (copied.length() == 0L) {
                    instrumentation.uiAutomation.executeShellCommand("cat ${path.shellQuote()}").use { descriptor ->
                        assertNotNull("Unable to open pushed baseline screenshot via shell: $path", descriptor)
                        ParcelFileDescriptor.AutoCloseInputStream(descriptor).use { input ->
                            FileOutputStream(copied).use { output -> input.copyTo(output) }
                        }
                    }
                }
                copied
            }
            ?: File(context.getExternalFilesDir(null), "finance_ocr_baseline.jpg")
        assertTrue("Missing pushed baseline screenshot: ${screenshot.absolutePath}", screenshot.exists())
        assertTrue("Pushed baseline screenshot is empty: ${screenshot.absolutePath}", screenshot.length() > 0L)

        val image = InputImage.fromFilePath(context, Uri.fromFile(screenshot))
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        val latch = CountDownLatch(1)
        val recognized = AtomicReference<Text?>()
        val error = AtomicReference<Exception?>()

        recognizer.process(image)
            .addOnSuccessListener { text ->
                recognized.set(text)
                latch.countDown()
            }
            .addOnFailureListener { exception ->
                error.set(exception)
                latch.countDown()
            }

        assertTrue("ML Kit OCR timed out", latch.await(30, TimeUnit.SECONDS))
        recognizer.close()
        error.get()?.let { throw AssertionError("ML Kit OCR failed: ${it.message}", it) }

        val rawText = recognized.get()?.text.orEmpty()
        println("MLKIT_TEXT_LENGTH=${rawText.length}")
        println("MLKIT_TEXT_BLOCKS=${recognized.get()?.textBlocks?.size ?: 0}")
        assertTrue("ML Kit OCR returned empty text", rawText.isNotBlank())

        val result = CaptureParser.parseScreenshotOcrResult(
            text = rawText,
            capturedAtMillis = 1_779_558_000_000L,
        )

        println("PARSED_AGGREGATE_COUNT=${result.aggregateCandidates.size}")
        result.aggregateCandidates.forEachIndexed { index, candidate ->
            println(
                "PARSED_ROW_${index + 1}=" +
                    "${candidate.externalLabel}|${candidate.amount}|${candidate.currency}|${candidate.operationCount}",
            )
        }
    }

    private fun String.shellQuote(): String {
        return "'${replace("'", "'\\''")}'"
    }
}
