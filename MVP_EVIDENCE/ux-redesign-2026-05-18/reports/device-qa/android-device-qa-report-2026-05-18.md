# Android Device QA report

Дата: 2026-05-18  
Роль: Android Device QA Worker  
Проект: `C:\Users\style\Documents\Codex\Финансы`

## Устройство и окружение

- Target device: `2_Pixel_6_Pro`
- ADB serial: `emulator-5556`
- ADB: `C:\Users\style\AppData\Local\Android\Sdk\platform-tools\adb.exe`
- Второй emulator не использовался: `emulator-5554` = `1_Pixel_6_Pro`
- Backend: `app.dev_seed:app` на `127.0.0.1:8000`, доступен Android как `http://10.0.2.2:8000`
- Backend был перезапущен на чистый seed, потому что унаследованный процесс уже содержал мутированные данные предыдущих QA прогонов.

## Команды

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices -l
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -s emulator-5556 emu avd name
.\gradlew.bat :app:assembleDebug
adb -s emulator-5556 install -r -d apps\android\app\build\outputs\apk\debug\app-debug.apk
adb -s emulator-5556 shell pm clear com.finance.mvp
adb -s emulator-5556 shell am start -n com.finance.mvp/.MainActivity
adb -s emulator-5556 exec-out screencap -p
adb -s emulator-5556 exec-out uiautomator dump /dev/tty
```

## Результаты

- `assembleDebug`: PASS, лог `android-assembleDebug-2026-05-18.log`.
- Install/clear/start на `emulator-5556`: PASS, лог `android-install-launch-2026-05-18.log`.
- Login через Android UI: PASS.
- Quick Add expense: PASS, создан расход `13,37 USD`, список и summary обновились.
- Quick Add income: PASS, создан доход `21,50 USD`, список и summary обновились.
- Quick Add transfer: PASS для shared-to-shared, создан перевод `15,00 USD`; `expenseTotal` не увеличился.
- Quick Add asset: PASS, создан `Банк 40,00 USD`, капитал и активы обновились.
- Активы: PASS, видны `Карта`, `Банк`, `Наличные`, `Вклад`, `Брокер`, `Металл`.
- Import placeholder: PASS как UI placeholder, confirm disabled; API proof metadata-only сохранен отдельно.
- Forbidden rendered text на чистом seed: PASS, `CRUD|PATCH|Live API|session id|MVP|Manual-first` не найдены.
- PNG validation: PASS, 28/28 screenshots имеют корректную PNG-сигнатуру.
- Secure token plaintext scan: PASS, `dev-only-token`, `demo.owner`, `demo-password`, `Bearer` не найдены в app data.

## Доказательства

- Screenshot validation: `MVP_EVIDENCE\ux-redesign-2026-05-18\reports\device-qa\android-screenshot-validation.json`
- Forbidden rendered scan: `MVP_EVIDENCE\ux-redesign-2026-05-18\reports\device-qa\android-forbidden-rendered-scan.json`
- Token storage proof: `MVP_EVIDENCE\ux-redesign-2026-05-18\reports\device-qa\android-secure-token-storage-proof.txt`
- Transfer proof: `MVP_EVIDENCE\ux-redesign-2026-05-18\reports\device-qa\android-transfer-not-expense-proof.json`
- Import metadata proof: `MVP_EVIDENCE\ux-redesign-2026-05-18\reports\device-qa\android-import-metadata-only-proof.json`
- Offline/background proof: `MVP_EVIDENCE\ux-redesign-2026-05-18\reports\device-qa\android-offline-background-proof.txt`

## Ключевые screenshots

- Overview after login: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-003-overview-clean-after-login.png`
- Home shared: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-004-home-shared.png`
- Home overview: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-005-home-overview-mode.png`
- Operations: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-006-operations.png`
- Quick Add open: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-007-quick-add-open.png`
- Quick Add expense before save: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-012-quick-add-expense-before-save.png`
- Quick Add income before save: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-014-quick-add-income-before-save.png`
- Quick Add transfer before save: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-018-quick-add-transfer-shared-before-save.png`
- Quick Add asset before save: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-020-quick-add-asset-before-save.png`
- Assets: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-024-assets.png`
- Analytics top: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-025-analytics-top.png`
- Import placeholder: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-026-import-placeholder.png`
- Import lower/disabled confirm: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-027-import-placeholder-lower.png`
- Offline refresh: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-028-offline-refresh.png`
- Reopen after background: `MVP_EVIDENCE\ux-redesign-2026-05-18\screenshots\android-device-qa\android-dev-029-reopen-after-background.png`

## Дефекты и блокеры

### DQA-A1: смешение агрегатов personal/shared

Severity: High / stop-the-line для privacy visibility.  
Сценарии: DEV-002, DEV-003, DEV-004.

Факты:
- На чистом seed в режиме `Личное` до создания личного расхода нет расходных операций и top categories пуст, но `Расходы месяца` показывает `69,75 USD` из shared expense.
- В режиме `Общее` `Доходы` показывают `262,50 USD`, а после личного Quick Add income стали `284,00 USD`, то есть shared summary включает personal income.
- Evidence: `android-window-03-clean-after-login-retry.xml`, `android-window-04-home-shared.xml`, `android-window-26-home-shared-after-transfer.xml`.

Expected: агрегаты режима должны считаться только по видимому scope.  
Actual: карточки totals используют общий fallback и смешивают scopes.

### DQA-A2: Analytics Android не имеет report switcher

Severity: Medium.  
Сценарий: DEV-010.

Факты:
- В `Аналитика` нет переключателя `Личное/Общее/Обзор`; раздел всегда показывает overview.
- Evidence: `android-window-29-analytics-top.xml`, `android-dev-025-analytics-top.png`.

Expected: report switcher `Личное/Общее/Обзор`.  
Actual: только overview summary.

### DQA-A3: invalid transfer pair fails without visible message

Severity: Medium.

Факты:
- Quick Add transfer с дефолтной парой `Dev Brokerage -> Dev Household Card` не сохранился и оставил sheet открытым без видимого сообщения.
- Shared-to-shared `Dev Household Card -> Dev Household Deposit` сохранился.
- Evidence: `android-window-20-quick-add-transfer-before-save.xml`, `android-window-21-after-transfer-save.xml`, `android-window-22-quick-add-transfer-shared-before-save.xml`.

Expected: disabled invalid pair or clear user-facing validation.  
Actual: пользователь не получает понятной причины.

### DQA-A4: logout не доступен через Android UI

Severity: Medium / checklist gap.  
Сценарий: DEV-013.

Факты:
- Явной кнопки logout в Android UI не найдено.
- Back/home/reopen финансовые данные не показывают до повторного входа/загрузки dashboard, но полноценный logout flow проверить через UI нельзя.
- Evidence: `android-window-13-after-dismiss-stuck-sheet.xml`, `android-window-14-relaunched.xml`.

### DQA-A5: inherited backend state showed forbidden technical term

Severity: Environment contamination, not reproduced after clean seed restart.

Факты:
- До reset seed унаследованный backend процесс рендерил `Android CRUD категория 418933`.
- После перезапуска clean `app.dev_seed` forbidden scan по 30 XML: no matches.
- Evidence before reset: `android-window-01-after-login.xml`.
- Clean scan: `android-forbidden-rendered-scan.json`.

## Checklist summary

- DEV-001 Login/session: PASS with note, token plaintext scan PASS.
- DEV-002 Деньги/Личное: FAIL, aggregate leakage in month expenses.
- DEV-003 Деньги/Общее: FAIL, income aggregate includes personal income.
- DEV-004 Деньги/Обзор: PASS for combined visibility, but inherits aggregate concerns.
- DEV-005 Quick Add expense/income: PASS.
- DEV-006 Quick Add transfer: PASS for valid shared transfer; transfer not expense PASS.
- DEV-007 Quick Add asset: PASS.
- DEV-008 Активы: PASS.
- DEV-009 Категории: PARTIAL, categories visible in Quick Add/analytics, no standalone Categories tab.
- DEV-010 Аналитика: PARTIAL/FAIL, transfer separated PASS, report switcher missing.
- DEV-011 Import placeholder: PASS, disabled confirm and no file parsing in UI.
- DEV-012 Import privacy: PARTIAL, metadata-only API proof for personal scope PASS; shared active-household path not fully exercised through Android UI.
- DEV-013 Logout/back-stack: PARTIAL, no logout UI; back/home/reopen hides financial data until reload.
- DEV-014 Offline/background: PARTIAL, no crash/no mutation observed; no clear offline error state visible.
