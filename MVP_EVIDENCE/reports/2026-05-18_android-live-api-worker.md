# Android live API worker evidence

Дата: 2026-05-18

## Итог

Android MVP подключен к live API для демо-входа, проверки сессии, счетов, категорий, операций и report summary. UI оставлен на русском языке и не добавляет import, bank, SMS, push или broker-поверхности.

## Изменения

- `apps/android/app/src/main/java/com/finance/mvp/api/ApiClient.kt`: live API abstraction на `HttpURLConnection`, bearer-token flow, методы `login`, `sessionStatus`, `dashboard`, `logout`, DTO для dashboard.
- `apps/android/app/src/main/java/com/finance/mvp/ui/FinanceApp.kt`: Compose UI использует `FinanceApiClient`, демо-вход, обновление dashboard, русские карточки overview/accounts/categories/transactions/reports.
- `apps/android/app/src/main/java/com/finance/mvp/ui/AppSection.kt`: MVP-разделы сведены к live API surface без лишних банковских/импортных поверхностей.
- `apps/android/app/src/main/java/com/finance/mvp/MainActivity.kt`: подключен `LiveFinanceApiClient`.
- `apps/android/app/src/main/java/com/finance/mvp/session/TokenStore.kt`: временное in-memory хранение bearer token для текущего процесса.
- `apps/android/app/src/main/AndroidManifest.xml`: разрешен cleartext HTTP для локального emulator backend.
- `apps/android/app/build.gradle.kts`: добавлен `kotlinx-coroutines-android`; base URL по-прежнему `financeApiBaseUrl` Gradle property с дефолтом `http://10.0.2.2:8000`.
- `apps/android/app/src/test/java/com/finance/mvp/api/ApiConfigTest.kt`: добавлен guard для emulator default.
- `apps/android/app/src/test/java/com/finance/mvp/ui/AppSectionTest.kt`: обновлены русские секции и guard на out-of-scope слова.

## Проверки

- `./gradlew.bat :app:assembleDebug` — PASS, APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk`, размер 16286930 bytes.
- `./gradlew.bat :app:testDebugUnitTest` — PASS.
- Unit tests: `ApiConfigTest` 3/3 PASS, `AppSectionTest` 2/2 PASS.
- Запрещенные UI-поверхности: scan по `apps/android/app/src/main` не нашел `SMS`, `push`, `broker`, `импорт`, `банк`; упоминания есть только в test guard assertions.

## Emulator smoke

- `adb` в PATH не найден, использован SDK binary: `C:\Users\style\AppData\Local\Android\Sdk\platform-tools\adb.exe`.
- `adb devices`: `emulator-5554 device`.
- `adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` — Success.
- Launch: `com.finance.mvp/.MainActivity` — Success.
- UI smoke: tap `Войти демо`; app загрузил live данные с `http://10.0.2.2:8000`.
- UI evidence XML: `MVP_EVIDENCE/test-runs/android-live-api-final-window.xml`.
- Screenshot: `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-final.png`.
- XML подтверждения: `Данные загружены из live API`, `Доходы 250.0000 USD`, `Счетов: 2; категорий: 3; операций: 2`, `API: http://10.0.2.2:8000`.

## Остаточные зазоры

- TokenStore пока in-memory; platform encrypted storage не внедрялся в этой задаче.
- Live API покрыт read/dashboard flow и demo login; создание/редактирование записей не добавлялось.
- Kotlin incremental compilation ранее падал на смешанных roots `W:\...`/`C:\...`, но Gradle fallback завершал сборку успешно; финальные повторные команды прошли без fatal errors.
