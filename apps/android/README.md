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

`assembleDebug` is the local E2E APK. By default it sets
`BuildConfig.FINANCE_API_BASE_URL` to the Android emulator host backend
`http://10.0.2.2:8000`, matching the backend local dev server on
`127.0.0.1:8000`. Override only with a local endpoint:

```powershell
.\gradlew.bat :app:assembleDebug -PlocalFinanceApiBaseUrl=http://10.0.2.2:<port>
```

Do not use the debug APK for production E2E. Production E2E must use an explicit
production-config build, for example a release build or an explicit property:

```powershell
.\gradlew.bat :app:assembleRelease -PfinanceApiBaseUrl=http://45.10.110.42/finance-api
```

Debug builds fail their guard if they point to `45.10.110.42` or the production
`/finance-api` URL.

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
