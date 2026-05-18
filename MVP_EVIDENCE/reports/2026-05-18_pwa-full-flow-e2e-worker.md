# PWA full flow E2E worker report

Дата: 2026-05-18

## Итог

PASS: PWA против live backend `http://127.0.0.1:8000` показывает live transfer seed (`count=1`), оба режима отчетов, и выполняет lifecycle операции через live API: create, update, archive/delete, restore.

## Что изменено

- `apps/web-pwa/src/api/client.ts`:
  - добавлены методы `createDemoOperation`, `updateOperation`, `archiveOperation`, `restoreOperation`;
  - добавлен retry unsafe-запроса после CSRF `403` через повторный cookie-login;
  - в summary вынесены `version`, `ownershipType`, `householdId`, `scope` для выбора совместимых live данных.
- `apps/web-pwa/src/api/types.ts`:
  - расширены `AccountSummary`, `CategorySummary`, `OperationSummary`.
- `apps/web-pwa/src/App.tsx`:
  - добавлена минимальная UX-панель lifecycle в разделе `Операции`;
  - create выбирает расходную категорию из того же scope, что и счет;
  - разделы `Переводы` и `Отчеты` показывают явные count/mode индикаторы.
- `apps/web-pwa/src/styles.css`:
  - добавлены стили lifecycle-панели и action buttons.
- `apps/web-pwa/src/App.test.tsx`:
  - добавлены проверки lifecycle controls и transfer count.

## Проверки

- `npm.cmd test`: PASS, `2 passed`, `6 passed`.
  - Лог: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-full-flow-npm-test.txt`
- `npm.cmd run build`: PASS, `tsc -b && vite build`.
  - Лог: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-full-flow-npm-build.txt`
- Chrome CDP E2E against `http://127.0.0.1:5174`: PASS.
  - Лог: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-full-flow-e2e.txt`
  - DOM: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-full-flow-e2e-dom.txt`
  - Runner: `MVP_EVIDENCE/test-runs/pwa-full-flow-e2e.cjs`

## E2E доказательства

- Desktop overview: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-overview-desktop.png`
- Desktop transfers: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-transfers-desktop.png`
- Desktop reports: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-reports-desktop.png`
- Desktop operation created: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-operation-created-desktop.png`
- Desktop operation updated: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-operation-updated-desktop.png`
- Desktop operation archived/deleted: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-operation-archived-desktop.png`
- Desktop operation restored: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-full-flow-operation-restored-desktop.png`
- iOS transfers: `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-full-flow-transfers-ios.png`
- iOS reports: `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-full-flow-reports-ios.png`
- iOS lifecycle: `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-full-flow-lifecycle-ios.png`

## Остаточные ограничения

- Для операций backend предоставляет `DELETE` + `restore`, поэтому UX подписан как архив/lifecycle proof, но API-действие для операции фактически soft-delete/restore.
- Отдельный Vite `5178`, поднятый для проверки гипотезы, остановлен; финальный E2E выполнен на `5174`.
