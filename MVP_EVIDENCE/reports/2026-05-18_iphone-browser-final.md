# iPhone Browser Final QA

Дата: 2026-05-18
Проект: `C:\Users\style\Documents\Codex\Финансы`
Роль: Final iPhone Browser QA Worker после final blocking fixes.

## Verdict

NO GO

## Среда

- Реальный Safari/iPhone недоступен в этой среде.
- Fallback: Playwright Chromium, device profile `iPhone 14`.
- Backend dev seed: `http://127.0.0.1:63517` (pid: `35516`).
- PWA dev server: `http://127.0.0.1:63518/` (pid: `41172`).
- Product code не менялся.
- `force` clicks и DOM fallback для взаимодействий не использовались.

## Checks

- PASS: PWA загрузилась против fresh backend/PWA после явной runtime CORS-настройки.
- PASS: no rendered `Dev`, no forbidden rendered text `CRUD`, `PATCH`, `Live API`, `session id`, `MVP`, `Manual-first`.
- PASS: раздел `Деньги` виден.
- PASS: режимы `Личное`, `Общее`, `Обзор` на `Деньги` переключаются обычными taps.
- FAIL: normal tap `FAB Добавить` не открывает Quick Add: `locator.tap: Timeout 8000ms exceeded`.
- FAIL: normal tap mobile nav `Операции`: `locator.tap: Timeout 8000ms exceeded`.
- FAIL: normal tap mobile nav `Активы`: `locator.tap: Timeout 8000ms exceeded`.
- FAIL: normal tap mobile nav `Категории`: `locator.tap: Timeout 8000ms exceeded`.
- FAIL: normal tap mobile nav `Аналитика`: `locator.tap: Timeout 8000ms exceeded`.
- FAIL: `Quick Add` expense/income/transfer/asset through normal clicks не выполнены, потому что FAB tap заблокирован.
- FAIL: `Quick Add Еще` и `Submit` не выполнены, потому что sheet не открывается обычным tap.
- FAIL: `transfer does not increase Расходы месяца` не подтвержден browser-flow evidence, потому что transfer Quick Add недоступен без blocked FAB.
- FAIL: import preview metadata-only не подтвержден browser-flow evidence, потому что `Аналитика` недоступна через normal mobile nav tap; обходы не использовались.

## Tap Evidence

Короткий probe после основного прогона:

```json
{
  "pwaUrl": "http://127.0.0.1:63518/",
  "checks": [
    { "name": "no forbidden rendered UI text", "ok": true, "details": "" },
    { "name": "loaded finance UI", "ok": true, "details": "Личное видно только вам / Деньги / Личное / Общее / Обзор" },
    { "name": "FAB Добавить", "ok": false, "details": "locator.tap: Timeout 8000ms exceeded." },
    { "name": "mobile nav Операции", "ok": false, "details": "locator.tap: Timeout 8000ms exceeded." },
    { "name": "mobile nav Активы", "ok": false, "details": "locator.tap: Timeout 8000ms exceeded." },
    { "name": "mobile nav Категории", "ok": false, "details": "locator.tap: Timeout 8000ms exceeded." },
    { "name": "mobile nav Аналитика", "ok": false, "details": "locator.tap: Timeout 8000ms exceeded." }
  ],
  "forbidden": []
}
```

## Screenshots

Папка: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final`

- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\01-money-personal-initial.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\02-money-personal-mode.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\03-money-shared-mode.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\04-money-overview-mode.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\blocked-expense-fab.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\blocked-income-fab.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\blocked-transfer-fab.png`
- `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-final\blocked-asset-fab.png`

## Runtime Evidence

- QA runner: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\iphone-browser-final-runner\final-iphone-browser-qa.mjs`
- Backend log: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-final-backend-63517.out.log`
- Backend error log: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-final-backend-63517.err.log`
- PWA log: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-final-pwa-63518.out.log`
- PWA error log: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-final-pwa-63518.err.log`

## Defects

- P0: iPhone-profile normal taps on fixed FAB are still blocked; Quick Add cannot be opened through the required mobile control.
- P0: iPhone-profile normal taps on mobile nav `Операции`, `Активы`, `Категории`, `Аналитика` are still blocked.
- P0: Required final GO scope cannot be completed without forbidden fallback interactions.
