import org.gradle.api.GradleException
import org.gradle.api.tasks.testing.Test
import java.io.ByteArrayOutputStream

val productionFinanceApiBaseUrl = "http://45.10.110.42/finance-api"
val defaultLocalFinanceApiBaseUrl = "http://10.0.2.2:8000"
val explicitFinanceApiBaseUrl = providers.gradleProperty("financeApiBaseUrl")
val localFinanceApiBaseUrl = providers.gradleProperty("localFinanceApiBaseUrl")
    .orElse(defaultLocalFinanceApiBaseUrl)
val debugFinanceApiBaseUrl = explicitFinanceApiBaseUrl.orElse(localFinanceApiBaseUrl)
val releaseFinanceApiBaseUrl = explicitFinanceApiBaseUrl.orElse(productionFinanceApiBaseUrl)

fun String.asBuildConfigString(): String = "\"${replace("\\", "\\\\").replace("\"", "\\\"")}\""

fun String.isUnsafeDebugFinanceApiBaseUrl(): Boolean {
    val normalized = trim().trimEnd('/')
    return normalized.contains("45.10.110.42") || normalized.endsWith("/finance-api")
}

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.devtools.ksp")
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

    buildTypes {
        debug {
            buildConfigField(
                "String",
                "FINANCE_API_BASE_URL",
                debugFinanceApiBaseUrl.get().asBuildConfigString(),
            )
        }

        release {
            buildConfigField(
                "String",
                "FINANCE_API_BASE_URL",
                releaseFinanceApiBaseUrl.get().asBuildConfigString(),
            )
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.00")
    val roomVersion = "2.6.1"

    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.room:room-ktx:$roomVersion")
    implementation("androidx.security:security-crypto:1.1.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    ksp("androidx.room:room-compiler:$roomVersion")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    testImplementation("androidx.room:room-testing:$roomVersion")
    testImplementation("androidx.test:core:1.6.1")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("org.json:json:20240303")
    testImplementation("org.robolectric:robolectric:4.13")
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

val verifyDebugFinanceApiBaseUrl by tasks.registering {
    group = "verification"
    description = "Fails debug/local Android builds if FINANCE_API_BASE_URL targets production."

    inputs.property("debugFinanceApiBaseUrl", debugFinanceApiBaseUrl)

    doLast {
        val apiBaseUrl = debugFinanceApiBaseUrl.get()
        if (apiBaseUrl.isUnsafeDebugFinanceApiBaseUrl()) {
            throw GradleException(
                "Unsafe debug FINANCE_API_BASE_URL=$apiBaseUrl. " +
                    "Use the local emulator-host backend default $defaultLocalFinanceApiBaseUrl " +
                    "or pass -PlocalFinanceApiBaseUrl=http://10.0.2.2:<port>.",
            )
        }
    }
}

tasks.matching {
    it.name in setOf("preDebugBuild", "assembleDebug", "testDebugUnitTest")
}.configureEach {
    dependsOn(verifyDebugFinanceApiBaseUrl)
}
