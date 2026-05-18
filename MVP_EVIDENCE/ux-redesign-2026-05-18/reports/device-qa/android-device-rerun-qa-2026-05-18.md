# Android device Re-QA rerun

Дата: 2026-05-18
Устройство: `2_Pixel_6_Pro` / `emulator-5556`
ADB: `C:\Users\style\AppData\Local\Android\Sdk\platform-tools\adb.exe`
APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk`

## Итог

FAIL.

Причины:
- invalid transfer pair не показывает пользователю понятное сообщение: после `Сохранить` на паре personal -> shared sheet остается без видимого error text/snackbar/dialog.
- В rendered UI остаются seed/debug строки `Dev ...` в Home, Operations и Quick Add picker. Это нарушает требование `no forbidden rendered text`.

## Прогоны

- `.\gradlew.bat :app:testDebugUnitTest` - PASS.
  Лог: `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-rerun-testDebugUnitTest.txt`
- `.\gradlew.bat :app:assembleDebug` - PASS.
  Лог: `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-rerun-assembleDebug.txt`
- `adb -s emulator-5556 install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` - PASS.
  Лог: `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-rerun-adb-install.txt`
- `ANDROID_SERIAL=emulator-5556 .\gradlew.bat :app:connectedDebugAndroidTest` - PASS, `3 tests on 2_Pixel_6_Pro(AVD)`.
  Лог: `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-rerun-connectedDebugAndroidTest.txt`

## Проверки

| Проверка | Статус | Evidence |
| --- | --- | --- |
| `Личное` не показывает shared expense в `Расходы месяца` | PASS | `01-home-personal.png`: `Расходы месяца 0,00 USD`, при этом shared seed expense `69,75 USD` отсутствует в personal total. |
| `Общее` не включает personal income | PASS | `02-home-shared.png`: `Доходы 0,00 USD`, personal income `250,00 USD` отсутствует в shared total. |
| Android `Аналитика` имеет switcher `Личное/Общее/Обзор` | PASS | `03-analytics-shared.png`, `04-analytics-personal.png`, `05-analytics-overview.png`. |
| invalid transfer pair показывает понятное сообщение | FAIL | `15-quickadd-transfer-invalid-ready.png` -> `16-quickadd-transfer-invalid-message.png`: после save видимого сообщения нет, XML содержит только sheet controls. |
| compact logout `Выйти` | PASS | `00-login.png` и все authenticated screenshots показывают compact `Выйти` в top bar. |
| Деньги/Home flow | PASS с caveat | `01-home-personal.png`, `02-home-shared.png`; caveat: видимый seed text `Dev ...`. |
| Операции flow | PASS с caveat | `06-operations.png`; caveat: видимый seed text `Dev ...`. |
| Активы flow | PASS | `07-assets.png`, после Quick Add asset `18-quickadd-transfer-saved.png` показывает `Банк 1 шт.`. |
| Аналитика flow | PASS | `03-analytics-shared.png`, `04-analytics-personal.png`, `05-analytics-overview.png`. |
| Quick Add расход | PASS | `08-quickadd-expense-sheet.png`, `09-quickadd-expense-ready.png`, `10-quickadd-expense-saved.png`; API post-check нашел `expense=12.34`. |
| Quick Add доход | PASS | `11-quickadd-income-ready.png`, `12-quickadd-income-saved.png`; API post-check нашел `income=23.45`. |
| Quick Add актив | PASS | `13-quickadd-asset-ready.png`, `14-quickadd-asset-saved.png`; API post-check нашел новый `bank` account с `34.56`. |
| Quick Add перевод | PASS for valid transfer, FAIL for invalid-message requirement | `17-quickadd-transfer-valid-ready.png`, `18-quickadd-transfer-saved.png`; API post-check нашел `transfer=45.67` / `household_same_household`. Invalid case still FAIL. |
| Import placeholder metadata-only | PASS | `19-import-placeholder-details.png`: файл не сохраняется, не разбирается, операции/категории/переводы не создаются. |
| Screenshots валидные | PASS | 20 PNG, все `1440x3120`, ненулевой размер. |
| No forbidden rendered text | FAIL | XML scan нашел `Dev` в `01`, `02`, `06`, `08`, `09`, `11`, `15`, `16`, `17`. |

## Screenshot paths

- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\00-login.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\01-home-personal.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\02-home-shared.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\03-analytics-shared.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\04-analytics-personal.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\05-analytics-overview.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\06-operations.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\07-assets.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\08-quickadd-expense-sheet.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\09-quickadd-expense-ready.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\10-quickadd-expense-saved.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\11-quickadd-income-ready.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\12-quickadd-income-saved.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\13-quickadd-asset-ready.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\14-quickadd-asset-saved.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\15-quickadd-transfer-invalid-ready.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\16-quickadd-transfer-invalid-message.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\17-quickadd-transfer-valid-ready.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\18-quickadd-transfer-saved.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa-rerun\19-import-placeholder-details.png`

## Дополнительные артефакты

- UI XML dumps: `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-rerun-*.xml`
- Screenshot validity scan: все PNG `1440x3120`, ненулевые.
- Forbidden text scan: `Dev` найден в rendered XML, mojibake/debug/API/local URLs не найдены.
- API post Quick Add check: `MVP_EVIDENCE/ux-redesign-2026-05-18/test-runs/android-rerun-api-post-quickadd-summary.json`
- Seed backend был запущен только для QA и остановлен после проверки.

## Blockers

1. Invalid transfer validation не выводится пользователю в Android UI. До исправления requirement 3 остается FAIL.
2. Rendered UI содержит `Dev ...` seed labels. До замены seed labels на product-safe demo labels requirement 6 остается FAIL.
