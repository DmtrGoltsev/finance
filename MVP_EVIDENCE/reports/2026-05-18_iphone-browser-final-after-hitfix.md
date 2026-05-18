# iPhone Browser Final QA After Hit-Test Fix

Дата прогона: 2026-05-18  
Роль: Final iPhone QA After Hit-Test Fix Worker  
Итог: GO

## Среда

- PWA: `http://127.0.0.1:63520/`
- Backend dev-seed: `http://127.0.0.1:8020/health`
- Browser: Playwright Chromium, device preset `iPhone 14`
- Safari: недоступен в среде, использован требуемый Chromium iPhone 14 fallback
- Product code: не изменялся

## Команды

- `npm.cmd run build` в `apps/web-pwa` - PASS
- Backend: `uvicorn app.dev_seed:app --host 127.0.0.1 --port 8020`
- PWA preview: `npm.cmd run preview -- --port 63520`
- QA: `node .\2026-05-18-iphone-browser-final-after-hitfix.mjs` из `MVP_EVIDENCE/test-runs` - PASS

## Evidence

- JSON: `MVP_EVIDENCE/test-runs/2026-05-18-iphone-browser-final-after-hitfix.json`
- Runner: `MVP_EVIDENCE/test-runs/2026-05-18-iphone-browser-final-after-hitfix.mjs`
- Screenshots: `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18-iphone-browser-final-after-hitfix`

Скриншоты:

- `00-home-loaded.png`
- `01-expense-open.png`
- `01-expense-ready.png`
- `01-expense-saved.png`
- `02-income-open.png`
- `02-income-ready.png`
- `02-income-saved.png`
- `03-transfer-open.png`
- `03-transfer-ready.png`
- `03-transfer-saved.png`
- `04-asset-open.png`
- `04-asset-ready.png`
- `04-asset-saved.png`
- `05-nav-operations.png`
- `06-nav-assets.png`
- `07-nav-categories.png`
- `08-nav-analytics.png`
- `09-import-preview.png`

## Проверки

- PASS: старт PWA и экран `Деньги`.
- PASS: no horizontal overflow на home, Operations, Assets, Categories, Analytics.
  - `innerWidth=390`, `visualWidth=390`, `scrollWidth=390`, `clientWidth=390`, `bodyScrollWidth=390`.
- PASS: hit-test FAB и mobile nav.
  - FAB center hit внутри элемента.
  - `mobile-nav-operations`, `mobile-nav-assets`, `mobile-nav-categories`, `mobile-nav-analytics` center hit внутри соответствующих buttons.
- PASS: normal taps без `force`, без DOM fallback для действий.
  - FAB.
  - Mobile nav: `Операции`, `Активы`, `Категории`, `Аналитика`.
  - Quick Add: `Расход`, `Доход`, `Перевод`, `Актив`.
  - `Еще`.
  - Submit.
- PASS: transfer is not expense.
  - До перевода: `Расходы месяца = 111 $`.
  - После перевода: `Расходы месяца = 111 $`.
- PASS: import preview metadata-only.
  - Request: `sourceType=file_metadata_only`, `fileName`, `fileSizeBytes`, `mimeType`.
  - Fixture content marker `SHOULD_NOT_LEAVE_BROWSER`, raw amount `999`, and CSV body were not sent.
- PASS: no rendered forbidden/dev text on checked screens.

## Notes

- Captured one expected `401 Unauthorized` console resource event from initial `/sessions/current` auth bootstrap before login fallback. It did not block the flow; no `requestfailed` events were recorded.
- Initial attempt on `63520` without explicit backend CORS was an environment setup issue, not a product defect. Final run used fresh backend with `FINANCE_BACKEND_DEV_CORS_ALLOWED_ORIGINS=["http://127.0.0.1:63520"]`.

## Defects

None found in final iPhone Chromium fallback QA.
