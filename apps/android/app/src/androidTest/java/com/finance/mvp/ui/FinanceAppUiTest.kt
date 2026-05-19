package com.finance.mvp.ui

import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.finance.mvp.MainActivity
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class FinanceAppUiTest {
    @Test
    fun launchesMainActivitySmokeWithoutEspressoInputManagerIdle() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                assertFalse(activity.isFinishing)
            }
        }
    }

    @Test
    fun loginFormHasEditableEmailAndMaskedPasswordFieldsWithoutEspressoIdle() {
        val typedPassword = "UiDummy-12345"

        ActivityScenario.launch(MainActivity::class.java).use {
            val fields = waitForEditableFields()
            assertTrue(fields.size >= 2)

            val passwordField = fields.firstOrNull { it.isPassword }
            assertNotNull(passwordField)
            assertTrue(fields.any { !it.isPassword })

            val args = Bundle().apply {
                putCharSequence(
                    AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                    typedPassword,
                )
            }
            assertTrue(passwordField!!.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args))

            val refreshedPasswordField = waitForEditableFields().firstOrNull { it.isPassword }
            assertNotNull(refreshedPasswordField)
            assertNotEquals(typedPassword, refreshedPasswordField!!.text?.toString())
        }
    }

    private fun waitForEditableFields(): List<AccessibilityNodeInfo> {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        repeat(40) {
            instrumentation.waitForIdleSync()
            val nodes = instrumentation.uiAutomation.rootInActiveWindow?.flatten().orEmpty()
            val fields = nodes.filter { it.isEditable }
            if (fields.isNotEmpty()) {
                return fields
            }
            Thread.sleep(250)
        }
        return emptyList()
    }

    private fun AccessibilityNodeInfo.flatten(): List<AccessibilityNodeInfo> {
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        fun visit(node: AccessibilityNodeInfo?) {
            if (node == null) return
            nodes += node
            for (index in 0 until node.childCount) {
                visit(node.getChild(index))
            }
        }
        visit(this)
        return nodes
    }
}
