# iPhone Browser Re-QA Rerun

Дата: 2026-05-18
Проект: `C:\\Users\\style\\Documents\\Codex\\Финансы`
Роль: iPhone Browser Re-QA Worker после blocking fixes.

## Verdict

FAIL

## Среда

- Реальный iPhone/Safari недоступен в этой среде.
- Fallback: Playwright 1.60.0 headless Chromium, device profile `iPhone 14`.
- Viewport: `390x664`.
- Backend dev seed: `http://127.0.0.1:8125`.
- PWA dev server: `http://127.0.0.1:5195/`.
- DOM fallback: не использовался.

## Checks

- PASS: PWA loaded and session established
- PASS: Категории available on mobile navigation
- PASS: Обзор mode works
- FAIL: floating Добавить tappable on iPhone - content intercepts the fixed FAB
- PASS: continued Quick Add through visible Операция button
- PASS: Quick Add sheet visible
- FAIL: Quick Add Еще tappable on iPhone - fields intercept the details summary
- FAIL: Quick Add submit tappable on iPhone - fields intercept the submit button
- FAIL: Quick Add expense created with normal taps - submit tap blocked
- FAIL: Quick Add income created with normal taps - not executed after submit blocker
- FAIL: Quick Add transfer created with normal taps - not executed after submit blocker
- FAIL: Quick Add asset created with normal taps - not executed after submit blocker
- FAIL: transfer does not increase Расходы месяца - not executed because transfer Quick Add is blocked
- PASS: PWA recovered after blocked Quick Add
- PASS: mobile navigation visible
- FAIL: mobile nav Операции tappable on iPhone - content intercepts the mobile navigation item
- PASS: Операции page works
- PASS: mobile navigation visible
- FAIL: mobile nav Активы tappable on iPhone - content intercepts the mobile navigation item
- PASS: Активы page works
- PASS: asset groups visible
- PASS: mobile navigation visible
- PASS: Категории page works from mobile nav
- PASS: Категории income/expense visible
- PASS: mobile navigation visible
- PASS: Аналитика page works
- PASS: Личное mode works
- PASS: Общее mode works
- PASS: Обзор mode works on analytics
- PASS: Аналитика metrics visible
- PASS: import preview visible
- PASS: import preview sends metadata only
- PASS: no forbidden rendered UI text
- PASS: mobile navigation visible
- PASS: Деньги page works

## Tap Evidence

- PASS: tap mode Обзор
- FAIL: tap floating Добавить - locator.tap: Timeout 7000ms exceeded.
- PASS: tap visible Операция quick-add opener
- PASS: tap Quick Add kind Расход
- PASS: focus/fill amount
- PASS: select Счет
- PASS: select Категория
- FAIL: tap Quick Add Еще - locator.tap: Timeout 7000ms exceeded.
- FAIL: tap Quick Add submit - locator.tap: Timeout 7000ms exceeded.
- PASS: tap mode Обзор
- FAIL: tap mobile nav Операции - locator.tap: Timeout 7000ms exceeded.
- PASS: forced evidence-continuation click mobile nav Операции
- FAIL: tap mobile nav Активы - locator.tap: Timeout 7000ms exceeded.
- PASS: forced evidence-continuation click mobile nav Активы
- PASS: tap mobile nav Категории
- PASS: tap mobile nav Аналитика
- PASS: tap mode Личное
- PASS: tap mode Общее
- PASS: tap mode Обзор
- PASS: select import report type
- PASS: set import file through file control
- PASS: tap import preview
- PASS: tap mobile nav Деньги

## Import Preview Request

```json
{
  "reportType": "brokerage_report",
  "sourceType": "file_metadata_only",
  "targetScope": "personal",
  "householdId": null,
  "fileName": "iphone-rerun-broker-report.csv",
  "fileSizeBytes": 26,
  "mimeType": "text/csv"
}
```

Файл для проверки содержал строки `account,amount`, `secret,999`; в request body этих значений нет.

## Screenshots

Папка: `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun`

- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\01-money-personal-initial.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\02-quick-add-submit-blocked.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\06-operations.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\07-assets.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\08-categories.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\09-analytics-personal.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\10-analytics-shared.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\11-analytics-overview.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\12-import-preview.png`
- `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\screenshots\\ios-pwa\\2026-05-18-iphone-browser-rerun\\13-money-return.png`

## Runtime Evidence

- JSON result: `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\test-runs\\2026-05-18_iphone-browser-rerun-results.json`
- Backend log: `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\test-runs\\2026-05-18_iphone-browser-rerun-backend-8125.out.log`
- Backend error log: `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\test-runs\\2026-05-18_iphone-browser-rerun-backend-8125.err.log`
- PWA log: `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\test-runs\\2026-05-18_iphone-browser-rerun-pwa-5195.out.log`
- PWA error log: `C:\\Users\\style\\Documents\\Codex\\Финансы\\MVP_EVIDENCE\\test-runs\\2026-05-18_iphone-browser-rerun-pwa-5195.err.log`

## Blockers

- floating Добавить tappable on iPhone: content intercepts the fixed FAB
- Quick Add Еще tappable on iPhone: fields intercept the details summary
- Quick Add submit tappable on iPhone: fields intercept the submit button
- Quick Add expense created with normal taps: submit tap blocked
- Quick Add income created with normal taps: not executed after submit blocker
- Quick Add transfer created with normal taps: not executed after submit blocker
- Quick Add asset created with normal taps: not executed after submit blocker
- transfer does not increase Расходы месяца: not executed because transfer Quick Add is blocked
- mobile nav Операции tappable on iPhone: content intercepts the mobile navigation item
- mobile nav Активы tappable on iPhone: content intercepts the mobile navigation item
- tap floating Добавить: locator.tap: Timeout 7000ms exceeded.
- tap Quick Add Еще: locator.tap: Timeout 7000ms exceeded.
- tap Quick Add submit: locator.tap: Timeout 7000ms exceeded.
- tap mobile nav Операции: locator.tap: Timeout 7000ms exceeded.
- tap mobile nav Активы: locator.tap: Timeout 7000ms exceeded.
