# Android device final QA

Дата: 2026-05-18
Роль: Final Android Device QA Worker
Устройство: `2_Pixel 6 Pro` / `emulator-5556`
ADB: `C:\Users\style\AppData\Local\Android\Sdk\platform-tools\adb.exe`
APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk`

## Итог

GO.

Android на `emulator-5556` проходит финальный device QA после blocking fixes.

## Команды и тесты

| Проверка | Статус | Evidence |
| --- | --- | --- |
| `.\gradlew.bat :app:testDebugUnitTest` | PASS | `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-final-testDebugUnitTest.txt` |
| `.\gradlew.bat :app:assembleDebug` | PASS | `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-final-assembleDebug.txt` |
| `adb -s emulator-5556 install -r ...app-debug.apk` | PASS | `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-final-adb-install-after-connected.txt` |
| `ANDROID_SERIAL=emulator-5556 .\gradlew.bat :app:connectedDebugAndroidTest` | PASS | `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-final-connectedDebugAndroidTest.txt` |

`connectedDebugAndroidTest` finished `3 tests on 2_Pixel_6_Pro(AVD) - 17`.

## Screenshots

Папка: `MVP_EVIDENCE/ux-redesign-2026-05-18/screenshots/android-device-qa-final`

Снято 26 PNG. Валидация: `MVP_EVIDENCE/ux-redesign-2026-05-18/reports/device-qa/android-final-screenshot-validation.json`.

Ключевые файлы:

- `00-login.png`
- `01-home-personal.png`
- `02-home-shared.png`
- `03-home-overview.png`
- `04-operations.png`
- `05-assets.png`
- `06-analytics-overview.png`
- `07-analytics-personal.png`
- `08-analytics-shared.png`
- `10-quickadd-expense-ready.png`
- `11-quickadd-expense-saved.png`
- `12-quickadd-income-ready.png`
- `13-quickadd-income-saved.png`
- `14-quickadd-asset-ready.png`
- `15-quickadd-asset-saved.png`
- `16-quickadd-transfer-invalid-ready.png`
- `17-quickadd-transfer-invalid-error.png`
- `18-quickadd-transfer-valid-ready.png`
- `19-quickadd-transfer-saved.png`
- `20-import-placeholder-metadata-only.png`
- `21-home-personal-after-flows.png`
- `22-home-shared-after-flows.png`
- `23-home-overview-after-flows.png`
- `24-assets-after-flows.png`
- `25-operations-after-flows.png`

## Финальные проверки

| Требование | Статус | Evidence |
| --- | --- | --- |
| No rendered `Dev` | PASS | `android-final-forbidden-rendered-scan.json`, 0 findings |
| No forbidden text `CRUD/PATCH/Live API/session id/MVP/Manual-first` | PASS | `android-final-forbidden-rendered-scan.json`, 0 findings |
| Invalid transfer pair shows visible Russian error after save | PASS | `17-quickadd-transfer-invalid-error.png`: `Перевод между личным и общим недоступен. Выберите счета одного режима.` |
| Personal/Shared aggregation remains fixed | PASS | `21-home-personal-after-flows.png`: personal expenses `12,34 USD`, income `273,45 USD`; `22-home-shared-after-flows.png`: shared expenses `69,75 USD`, income `0,00 USD`, transfers `70,67 USD` |
| Analytics switcher `Личное/Общее/Обзор` visible | PASS | `06-analytics-overview.png`, `07-analytics-personal.png`, `08-analytics-shared.png` |
| Logout visible | PASS | top bar `Выйти` visible on authenticated screenshots |
| Деньги flow | PASS | `01-home-personal.png`, `02-home-shared.png`, `03-home-overview.png`, post-flow `21-23` |
| Операции flow | PASS | `04-operations.png`, post-flow `25-operations-after-flows.png` shows расход/доход/перевод |
| Активы flow | PASS | `05-assets.png`, post-flow `24-assets-after-flows.png` shows new `Банк 34,56 USD` |
| Аналитика flow | PASS | `06-analytics-overview.png`, `07-analytics-personal.png`, `08-analytics-shared.png` |
| Quick Add расход | PASS | `10-quickadd-expense-ready.png`, `11-quickadd-expense-saved.png`, post-flow personal `-12,34 USD` |
| Quick Add доход | PASS | `12-quickadd-income-ready.png`, `13-quickadd-income-saved.png`, post-flow `+23,45 USD` |
| Quick Add перевод | PASS | invalid error in `17`, valid saved in `19`, shared transfers update to `70,67 USD` |
| Quick Add актив | PASS | `14-quickadd-asset-ready.png`, `15-quickadd-asset-saved.png`, post-flow assets `Банк 34,56 USD` |
| Import placeholder metadata-only | PASS | `20-import-placeholder-metadata-only.png`; API proof `android-final-import-metadata-only-proof.json` has `sourceType=file_metadata_only`, `canConfirm=false`, `willChangeData=false`, unchanged counts |

## Дополнительные артефакты

- Rendered text scan: `MVP_EVIDENCE/ux-redesign-2026-05-18/reports/device-qa/android-final-forbidden-rendered-scan.json`
- Screenshot validation: `MVP_EVIDENCE/ux-redesign-2026-05-18/reports/device-qa/android-final-screenshot-validation.json`
- Import metadata-only proof: `MVP_EVIDENCE/ux-redesign-2026-05-18/reports/device-qa/android-final-import-metadata-only-proof.json`
- UI XML dumps: `MVP_EVIDENCE/ux-redesign-2026-05-18/reports/device-qa/android-final-window-*.xml`

## Defects

Нет открытых дефектов для финального Android GO.

QA note: `connectedDebugAndroidTest` удалил приложение после своего прогона, поэтому APK был установлен повторно перед ручной device QA. Это не продуктовый дефект.
