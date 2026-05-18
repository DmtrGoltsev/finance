# PWA accounts/categories/transfer CRUD recovery worker

Дата: 2026-05-18

Итог: **PASS для PWA full CRUD/transfer MVP**.

## Контекст восстановления

- Worker запущен после transport error предыдущего PWA worker `019e3b35-65dd-7502-8cf2-44b3ba8e62b1`.
- `.git` в `C:\Users\style\Documents\Codex\Финансы` недоступен, поэтому git diff/status снять нельзя.
- Частичные изменения предыдущего worker обнаружены:
  - `apps/web-pwa/src/App.tsx` уже содержал русские lifecycle-панели для счетов, категорий, операций и переводов.
  - `apps/web-pwa/src/api/client.ts` уже содержал cookie/CSRF API client без localStorage bearer и методы account/category/operation/transfer lifecycle.
  - Были созданы screenshots `2026-05-18_pwa-account-crud-*`, `2026-05-18_pwa-category-crud-*`, `2026-05-18_pwa-transfer-*`.
  - Предыдущий e2e `2026-05-18_pwa-accounts-categories-transfer-crud-e2e.txt` падал на account delete: `Timed out waiting for CRUD / архив / восстановление счета delete`.

## Что исправлено

- Убрана UI race condition: PWA раньше показывала финальный статус restore/create/update/archive/delete до завершения `loadSnapshot()`. E2E успевал нажать delete по stale archived account и получал backend conflict. Теперь финальный статус выставляется после синхронизации snapshot.
- Исправлен live reports mapping: backend возвращает report mode в `data.scope.reportMode` и суммы в `data.totalsByCurrency[]`, а PWA ожидала flat-поля. Из-за этого кнопки режимов отчета были пустыми. Теперь отображаются:
  - `Общий семейный отчет`
  - `Сводный обзор участника`
- E2E runner усилен:
  - пишет failure DOM при падении;
  - доказывает operation create/update/delete/restore в текущем прогоне;
  - проверяет iOS-like reports по реальному разделу `Отчеты`.

## Измененные файлы

- `apps/web-pwa/src/App.tsx`
- `apps/web-pwa/src/api/client.ts`
- `apps/web-pwa/src/api/client.test.ts`
- `apps/web-pwa/dist/index.html`
- `apps/web-pwa/dist/assets/index-DinSd_zJ.js`
- `apps/web-pwa/dist/assets/index-BixWBhQa.css`
- `MVP_EVIDENCE/test-runs/pwa-accounts-categories-transfer-crud-e2e.cjs`
- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-accounts-categories-transfer-crud-e2e.txt`
- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-accounts-categories-transfer-crud-e2e-dom.txt`
- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-accounts-categories-transfer-crud-e2e-operation-pass-output.txt`
- screenshots under `MVP_EVIDENCE/screenshots/pwa-desktop/`
- screenshots under `MVP_EVIDENCE/screenshots/ios-pwa/`

Backend, Android и OpenAPI не редактировались.

## Проверки

`npm.cmd test` в `apps/web-pwa`:

- PASS
- `Test Files 2 passed (2)`
- `Tests 7 passed (7)`

`npm.cmd run build` в `apps/web-pwa`:

- PASS
- `tsc -b && vite build`
- bundle: `assets/index-DinSd_zJ.js`

Live E2E against PWA `http://127.0.0.1:5174` and backend `http://127.0.0.1:8000`:

- PASS
- evidence file: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-accounts-categories-transfer-crud-e2e.txt`
- runner output: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-accounts-categories-transfer-crud-e2e-operation-pass-output.txt`
- localStorage proof: `{"length":0,"keys":[]}`

Final E2E summary:

```text
desktop: loaded Russian live PWA shell
desktop: localStorage proof {"length":0,"keys":[]}
desktop: account create/update/archive/restore/delete PASS
desktop: category create/update/archive/restore/delete PASS
desktop: operation create/update/delete/restore PASS
desktop: transfer count/row visible count=6
desktop: manual transfer create/update/delete/restore PASS
desktop: report modes PASS
ios viewport: account/category/transfer/report flows visible
```

## Transfer route semantics

Standalone `/api/v1/transfers` route was not invented or used.

Manual transfer lifecycle is proven through existing backend semantics:

- `POST /api/v1/transactions` with `transactionType: "transfer"`
- `PATCH /api/v1/transactions/{transactionId}`
- `DELETE /api/v1/transactions/{transactionId}`
- `POST /api/v1/transactions/{transactionId}/restore`

Live transfer row/count was visible before lifecycle actions; final E2E recorded `transfer count/row visible count=6`.

## Screenshots

Desktop:

- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-crud-transfer-overview-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-account-crud-initial-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-account-crud-created-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-account-crud-updated-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-account-crud-archived-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-account-crud-restored-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-account-crud-deleted-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-category-crud-initial-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-category-crud-created-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-category-crud-updated-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-category-crud-archived-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-category-crud-restored-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-category-crud-deleted-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-operation-created-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-operation-updated-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-operation-deleted-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-operation-restored-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-transfer-visible-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-transfer-created-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-transfer-updated-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-transfer-deleted-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-transfer-restored-desktop.png`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-reports-modes-desktop.png`

iOS-like:

- `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-account-crud-ios.png`
- `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-category-crud-ios.png`
- `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-transfer-lifecycle-ios.png`
- `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-reports-modes-ios.png`

## Remaining gaps

- Нет standalone transfer route, но это соответствует контракту MVP: transfer lifecycle идет через `/api/v1/transactions` с `transactionType=transfer`.
- Рабочая директория не является git repo, поэтому список измененных файлов подтвержден инспекцией файлов/mtime, а не `git diff`.
