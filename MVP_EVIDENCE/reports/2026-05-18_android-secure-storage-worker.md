# Android secure storage worker — 2026-05-18

## Итог

Secure storage: **PASS**.

Android release path больше не использует pure in-memory token storage. `MainActivity` создает `AndroidSecureTokenStore`, который сохраняет access token в `EncryptedSharedPreferences` с `MasterKey` AES-256-GCM. Ordinary plaintext `SharedPreferences`/files для токена не добавлялись.

HOLD: **нет**.

## Изменения

- `apps/android/app/src/main/java/com/finance/mvp/session/TokenStore.kt`
  - добавлен `AndroidSecureTokenStore`;
  - добавлен Keystore-backed `EncryptedSharedPreferences`;
  - сохранение выполняется через `commit()` для явного результата записи;
  - in-memory store переименован в `InMemorySecureTokenStore` и не используется release path.
- `apps/android/app/src/main/java/com/finance/mvp/MainActivity.kt`
  - live API client теперь получает `AndroidSecureTokenStore(applicationContext)`.
- `apps/android/app/build.gradle.kts`
  - добавлена зависимость `androidx.security:security-crypto:1.1.0`.
- `apps/android/app/src/androidTest/java/com/finance/mvp/session/AndroidSecureTokenStoreTest.kt`
  - проверяет persistence между инстансами store;
  - проверяет, что XML-файл encrypted preferences не содержит plaintext token;
  - проверяет очистку token store.

## Доказательства

- `./gradlew.bat :app:testDebugUnitTest` — **PASS**
  - лог: `MVP_EVIDENCE/test-runs/2026-05-18_android-secure-storage-testDebugUnitTest.txt`
  - результат: `BUILD SUCCESSFUL in 47s`
- `./gradlew.bat :app:assembleDebug` — **PASS**
  - лог: `MVP_EVIDENCE/test-runs/2026-05-18_android-secure-storage-assembleDebug.txt`
  - результат: `BUILD SUCCESSFUL in 17s`
- `./gradlew.bat :app:connectedDebugAndroidTest` — **PASS**
  - лог: `MVP_EVIDENCE/test-runs/2026-05-18_android-secure-storage-connectedDebugAndroidTest.txt`
  - результат: `Finished 2 tests on 1_Pixel_6_Pro(AVD) - 17`, `BUILD SUCCESSFUL in 2m 23s`
- Emulator smoke install/run — **PASS**
  - лог: `MVP_EVIDENCE/test-runs/2026-05-18_android-secure-storage-emulator-smoke.txt`
  - устройство: `emulator-5554`
  - результат: install `Success`, `Status: ok`, `LaunchState: COLD`, pid `9105`

## Источник по зависимости

Официальная страница AndroidX Security фиксирует релиз `androidx.security:security-crypto:1.1.0` и описывает `EncryptedSharedPreferences` как реализацию, которая шифрует ключи и значения SharedPreferences: https://developer.android.com/jetpack/androidx/releases/security

## Риски / gaps

- В AndroidX Security 1.1.0 API `EncryptedSharedPreferences`/`MasterKey` помечены deprecated в пользу platform APIs/direct Android Keystore. Для MVP release blocker закрыт, но после MVP стоит запланировать миграцию на прямую Keystore-реализацию или утвержденный project-wide storage standard.
- Instrumented proof проверяет отсутствие plaintext в XML encrypted preferences; он не доказывает защиту от rooted device / runtime memory inspection, что ожидаемо для mobile token storage.
