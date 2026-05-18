# PWA-LIVE-API worker report

Дата: 2026-05-18

## Что сделано

- PWA переведена с mock-first клиента на live API клиент.
- Добавлен `VITE_API_BASE_URL` через `import.meta.env`, default: `http://127.0.0.1:8000`.
- Реализован dev MVP login demo-учеткой `demo.owner@example.test` / `demo-password-only`.
- Bearer token сохраняется в `localStorage` под ключом `finance-mvp-pwa-token` и переиспользуется для `/api/v1/sessions/current`.
- Главные экраны получают live data из:
  - `GET /api/v1/accounts`
  - `GET /api/v1/categories`
  - `GET /api/v1/transactions`
  - `GET /api/v1/reports/summary`
- UI оставлен на русском; import/bank/SMS/push/broker UI не добавлялись.
- Добавлены тесты границы API client/state и обновлены UI-тесты.

## Проверки

- `npm.cmd test` -> exit `0`, `2 passed`, `4 tests passed`.
- `npm.cmd run build` -> exit `0`, `tsc -b && vite build` успешно.
- PWA dev server: `http://127.0.0.1:5174`.
- Smoke через Playwright CLI:
  - ожидание `text=Dev Personal Cash` на `http://127.0.0.1:5174` -> exit `0`.

## Evidence

- Test log: `MVP_EVIDENCE/test-runs/pwa-live-api-npm-test.txt`
- Build log: `MVP_EVIDENCE/test-runs/pwa-live-api-npm-build.txt`
- Smoke log: `MVP_EVIDENCE/test-runs/pwa-live-api-smoke.txt`
- Desktop screenshot: `MVP_EVIDENCE/screenshots/pwa-desktop/pwa-live-api-desktop.png`
- iOS-like screenshot: `MVP_EVIDENCE/screenshots/ios-pwa/pwa-live-api-ios.png`

## Оставшиеся ограничения

- Demo seed возвращает часть предметных названий на английском (`Dev Personal Cash`, `Dev household supplies`); UI chrome и разделы PWA остаются русскими.
- В live seed нет transfer-транзакций, поэтому раздел переводов показывает пустое состояние.
- Хранение bearer token в `localStorage` сделано только как MVP/dev компромисс.
