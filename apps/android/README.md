# Android MVP

Kotlin + Jetpack Compose shell for the manual-first finance MVP.

## Open

Open `apps/android` in Android Studio, let Gradle sync, then run the `app` configuration.

## Build and test

```powershell
cd apps/android
.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:testDebugUnitTest
```

This workspace currently does not include the Gradle wrapper binaries. If Android Studio creates the wrapper, use the
commands above. Otherwise install Gradle locally and run:

```powershell
gradle :app:assembleDebug
gradle :app:testDebugUnitTest
```

## Current scope

- Compose app shell with Russian UI.
- Sections: session/login shell, overview, accounts, categories, transactions, transfers, reports.
- API client abstraction with configurable base URL.
- Secure token storage contract prepared for Android platform-backed implementation.
- JVM smoke tests for section coverage and API base URL behavior.

Not included in MVP: bank import, SMS, push, broker UI.
