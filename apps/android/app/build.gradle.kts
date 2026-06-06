import org.gradle.api.tasks.testing.Test
import java.io.ByteArrayOutputStream

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.finance.mvp"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.finance.mvp"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField(
            "String",
            "FINANCE_API_BASE_URL",
            "\"${providers.gradleProperty("financeApiBaseUrl").orNull ?: "http://10.0.2.2:8000"}\"",
        )
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.00")

    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.security:security-crypto:1.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}

tasks.withType<Test>().configureEach {
    fun File.windowsShortPath(): File {
        if (!System.getProperty("os.name").contains("Windows", ignoreCase = true)) {
            return this
        }

        val output = ByteArrayOutputStream()
        exec {
            commandLine("cmd", "/c", "for %I in (\"$absolutePath\") do @echo %~sI")
            standardOutput = output
            isIgnoreExitValue = true
        }

        val path = output.toString().trim()
        return if (path.isNotBlank()) file(path) else this
    }

    doFirst {
        testClassesDirs = files(testClassesDirs.files.map { it.windowsShortPath() })
        classpath = files(classpath.files.map { it.windowsShortPath() })
    }
}
