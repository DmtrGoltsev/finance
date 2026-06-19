# Current Status: Production MVP

## Статус

Production MVP получил **functional GO** на 2026-05-19 для iPhone/browser и Android.

Это не является full security GO и не является безусловным public production GO. Статус фиксирует, что восстановленная production-сборка проходит финальные функциональные проверки MVP в заявленных средах с явно описанными ограничениями и остаточными решениями владельцев.

`newDis` copy alignment находится в плановом состоянии и не означает, что редизайн уже выпущен, задеплоен или прошел релизные проверки. Любые утверждения о новом UX, Planning parity, OCR smoke, release-signed APK или public/security GO должны появляться только после отдельного release-agent evidence.

## Production

- Backend commit: `26b487d61b7d2d6de704f0a632bcb08ff7f240f7` / short `26b487d` (deployed 2026-06-12).
- PWA commit: `8b0447a` / short `8b0447a` (deployed 2026-06-12, includes registration + all 18 Android-PWA gap closures).
- PWA release: `20260612T183500Z-8b0447a`.
- PWA assets: `index-cwshrAjc.js`, `index-CLMqvBfm.css`.
- Observed local tag state: `v0.1.0-mvp` points to `94d2484a74131f53badf0cd83610b925770fb710`.
- Tag alignment: open; aligning `v0.1.0-mvp` to production deployed commit evidence requires explicit owner approval before any retag/push/tag mutation.
- Frontend: `http://45.10.110.42/finance/`.
- Backend API: `http://45.10.110.42/finance-api`.
- Authoritative final report: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`.

## Self-service registration (2026-06-12)

- Commit: `41daee8` (`feat(web-pwa): add self-service registration UI`).
- PWA теперь поддерживает самостоятельную регистрацию через `POST /api/v1/users` с `transport: pwa_cookie`.
- UI: переключатель Вход/Регистрация на login screen; валидация email, password >= 12, confirm match.
- Duplicate/accepted: нейтральное сообщение с предложением войти, без раскрытия существования аккаунта.
- Backend изменений не потребовалось.
- Риск: пароли регистрации идут по plain HTTP; HTTPS/domain остается открытым security gate.

## PWA parity: закрытие 18 Android-PWA gap (2026-06-12)

- Commit: `8b0447a` (`feat(web-pwa): close all 18 Android-PWA gaps`), +4327 строк в 6 файлах.
- PWA release: `20260612T183500Z-8b0447a`.
- Тесты: 56/56 PASS, production build PASS.

### Реализованные gap

| Область | Что добавлено |
|---------|--------------|
| **Планирование** | Полный модуль: создание плана, доходы, распределения, история, копирование, savings goals, мини-карточка на главной |
| **Planning API** | 12 методов: plans CRUD, income-sources CRUD, allocations CRUD, copy |
| **Asset Categories** | CRUD: создание, редактирование, архивация, восстановление; picker иконок |
| **Инвестиции** | Карточка с investmentsByCurrency/investmentsTotal |
| **Account-Balances** | GET /reports/account-balances с assetCategoryGroups |
| **Удаление операций** | Кнопка удаления с подтверждением |
| **Редактирование операций** | Полная форма: amount, description, categoryId, occurredDate (вместо хардкода) |
| **Редактирование счёта** | Поля: name, balance, currency, assetCategoryId, isPaymentAccount |
| **Валюта XAU** | Поддержка золота в выборе валюты |
| **Метрика «Переводы»** | Карточка в аналитике |
| **Archive/Restore UI** | Кнопки для счетов, категорий активов, обычных категорий |
| **Legacy-привязка** | Счета без assetCategoryId показаны с предложением привязки |
| **Переупорядочивание** | Кнопки ↑/↓ для категорий активов |
| **Analytics табы** | «Сводка» / «План месяца» |

### Осознанно отложено

- Push-уведомления (Web Push) — отдельная инфраструктура
- Локальный OCR-парсер — backend-side OCR достаточен
- Drag-and-drop — заменён на кнопки ↑/↓

## Offline-first scope (2026-06-18)

Завершенный offline-first scope покрывает backend/Android синхронизацию для transactions, accounts, categories, asset categories, planning plans/income sources/allocations и investment migration command.

Границы scope зафиксированы в `docs/architecture/client-state-contracts.md`:

- syncable операции: ручные mutations по transactions/accounts/categories/asset categories/planning entities и единая `investment_migrations:create`;
- online-only операции: OCR/screenshot upload, `copy_plan`, planning history mutation и target repair workflows;
- OCR/screenshot upload остается online-only навсегда: raw images, raw OCR text и OCR payloads не должны попадать в Room, pending sync, logs или telemetry;
- planning delete/restore использует tombstones, чтобы local-first Android не воскрешал удаленные plans/income sources/allocations между replay и pull;
- investment migration является одной атомарной backend command, а не группой независимых queued mutations;
- conflict UI MVP показывает failed/rejected sync issues, дает retry для failed и безопасное объяснение для rejected без destructive choose-server/choose-local overwrite.

QA evidence для этого scope должно опираться на targeted backend ruff/tests, Android JVM tests, Android APK build и APK zip gate. Full backend ruff может оставаться красным из-за legacy unrelated files и не является единственным gate для этого scope.

## Offline-first release QA and merge status (2026-06-18/2026-06-19)

- Branch `codex/offline-first-release-qa` был зеленым на GitHub Actions run `27796358035`, head `b09043e531152bb5f9b2fdb6ef18b21d786bbebf`.
- Release id: `20260618T234841Z-b09043e5`.
- Package gates: frontend package `56 passed`; backend package `285 passed, 6 skipped`.
- Local emulator E2E PASS до CI зафиксирован в sanitized evidence: `MVP_EVIDENCE/offline-first-release-qa-20260618-234050/QA_REPORT_SANITIZED.md`.
- Release blockers fixed before green CI: backend ruff gate; FastAPI `0.137.2` route introspection through `iter_route_contexts`; pinned backend dependencies `fastapi==0.137.2`, `starlette==1.3.1`.
- PR: `https://github.com/DmtrGoltsev/finance/pull/1` merged at `2026-06-18T23:53:47Z`; remote `main` HEAD и merge commit подтверждены как `cff578df0be001c0af187c5a90d9917fc0b2c1e9` с parents `3f70a3bf...` + release head `b09043e5...`.
- Workflows on `main`: files present; active workflows confirmed: `Finance HexCore Production CI/CD` id `298526666`, `Finance Production Manual Rollback` id `298581092`.
- Production deploy не считать выполненным. Public backend health PASS и frontend PASS, но `workflow_dispatch` остается BLOCKED: GitHub `production` environment absent (`total_count=0`, direct endpoint 404), environment secrets absent, repo secrets `total_count=0`; также нужны backup proof, production `alembic current`, service/symlink proof.

## Финальные доказательства

- Android final GO: `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/android-final-prod-qa-report.md`.
- PWA/iPhone final GO: `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md`.
- Финальное покрытие включает login/logout, accounts/assets, shared/personal privacy, categories add/edit, income/expense/transfer, brokerage/investment API smoke и report modes. Backend/OpenAPI cleanup после этого статуса вывел metadata-only import placeholder из mounted MVP scope.

## Ограничения

- PWA service worker на plain HTTP IP ограничен средой: приложение работает online, но штатный service worker/PWA install требует HTTPS/domain.
- CVE scans, backup/restore, physical iPhone/Safari требуют отдельного proof или waiver.
- Import endpoints не входят в текущий mounted backend/OpenAPI MVP scope; реальные импорт, парсинг файлов и создание операций/категорий/переводов остаются вне scope.
- SMS and push/notification interception are no longer part of the documented product state. The remaining capture-draft flow is user-initiated OCR from a user-selected screenshot through a backend OCR request. Screenshots and raw OCR text are not expected to be persisted, and transactions are created only after user confirm/edit. Authenticated production login/OCR smoke and OCR retention/privacy evidence remain separate release evidence.
- Planning: PWA теперь имеет паритетный модуль планирования с Android (создание плана, доходы, распределения, история, копирование, savings goals). `newDis` copy alignment завершен для PWA planning.
- Investment detailed UI: PWA теперь показывает карточку инвестиций с investmentsByCurrency/investmentsTotal.
- Production QA data cleanup/retention остается отдельным xhigh owner decision.
- Android APK/public distribution status must not be overclaimed: debug-signed APK, release signing, безопасность, комплаенс, домен/HTTPS и публичный запуск остаются отдельными gate, а не частью этого functional GO.

## Измененные файлы

- Changed files are tracked in git diff/status; this document is not an authoritative complete list.
