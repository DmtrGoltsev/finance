# Import placeholder QA, 2026-05-18

## Итог

Статус: PASS с ограничением по Android connected UI.

Проверен metadata-only placeholder `POST /api/v1/imports/report-preview` и интеграция PWA/Android. Реальный импорт, парсинг файла и изменение финансовых данных не обнаружены.

## Contract alignment

- Request поля совпадают с контрактом: `reportType`, `sourceType=file_metadata_only`, `targetScope`, `householdId`, `fileName`, `fileSizeBytes`, `mimeType`.
- Backend response возвращает `status=preview_placeholder`, `canConfirm=false`, `willChangeData=false`.
- Секции response фиксированы и идут в ожидаемом порядке: `accounts_assets`, `transactions`, `categories`, `transfers`, `brokerage_deposits_metals`.
- Все секции имеют `status=not_recognized_yet`; counts, суммы, балансы, названия счетов/категорий и описания операций из файла не возвращаются.
- Warnings покрывают placeholder-only, отсутствие storage/parsing и отсутствие изменений данных.

## Совместимый fix

Найден мелкий mismatch: backend возвращает warning code `NO_FILE_STORAGE_OR_PARSING`, а PWA type/fallback/test fixture допускали только `NO_DATA_CHANGES_WITHOUT_CONFIRMATION` и `PLACEHOLDER_ONLY`.

Исправлено:

- `apps/web-pwa/src/api/types.ts`
- `apps/web-pwa/src/api/client.ts`
- `apps/web-pwa/src/api/client.test.ts`
- `apps/web-pwa/src/App.test.tsx`

Суть fix: PWA response type и fallback теперь поддерживают `NO_FILE_STORAGE_OR_PARSING`; тесты обновлены на 3 warning entries.

## Финальные проверки

- Backend: `apps/backend/.venv/Scripts/python.exe -m pytest` -> `157 passed`, 5 deprecation warnings.
- PWA: `npm.cmd test` -> `2 passed`, `12 passed`.
- PWA: `npm.cmd run build` -> `tsc -b && vite build` completed successfully.
- Android unit: `apps/android/gradlew.bat testDebugUnitTest` -> BUILD SUCCESSFUL.
- Android build: `apps/android/gradlew.bat assembleDebug` -> BUILD SUCCESSFUL.

PowerShell `npm` wrapper был заблокирован execution policy, поэтому PWA команды запускались через `npm.cmd`.

## Counts evidence

Файл: `MVP_EVIDENCE/reports/import-placeholder-counts-2026-05-18.json`

Проверка выполнена на свежем `app.dev_seed:app` текущего workspace, поднятом временно на `http://127.0.0.1:8010`, потому что порт `8000` был занят старым dev backend без imports route.

Результат:

- route present in OpenAPI: true;
- before counts: accounts 5, categories 3, transactions 6;
- after counts: accounts 5, categories 3, transactions 6;
- `unchanged.accounts=true`, `unchanged.categories=true`, `unchanged.transactions=true`;
- `canConfirm=false`, `willChangeData=false`;
- result: PASS.

## Screenshots

PWA:

- `MVP_EVIDENCE/ux-redesign-2026-05-18/screenshots/import-placeholder/pwa-import-placeholder.png`
- PNG verification: 1414x1100, 87770 bytes, sampled unique colors 12.
- Rendered state: import preview visible, selected file metadata visible, 5 recognition sections, 3 warnings, no active real-confirm flow.

Android:

- Connected screenshot не создан: `adb` не найден в PATH, emulator/device недоступны.
- Android UI покрыт unit/build проверками; existing `androidTest` импортируется, но тест помечен `@Ignore` и требует emulator image.

## Блокеры и риски

- Blocker: нет `adb`, поэтому `connectedAndroidTest` и Android screenshot выполнить нельзя.
- Risk: PWA in-app browser plugin дважды завис на открытии localhost; PWA screenshot снят резервно через локальный headless Chrome/CDP на корректном Vite URL `http://127.0.0.1:5174`.
- Risk: на `127.0.0.1:8000` работал старый backend без imports route; backend evidence собран на отдельном временном порту `8010` с кодом текущего workspace.
