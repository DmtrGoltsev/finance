# PWA iPhone parity post-fix QA evidence

Date: 2026-07-27 Europe/Moscow
Worker role: QA/documentation worker
Scope: local PWA iPhone browser parity smoke after TopCategoriesDialog portal/layer fix; no deploy; no commit/push; no production data.

## Result

PASS.

PWA unit/build gates pass. Local iPhone browser smoke passes for login, home, mobile quick add, category picker overlay, analytics, and `Все категории трат`. The TopCategoriesDialog now overlays the mobile FAB and bottom nav, and its category list scrolls inside the dialog.

Backend code was not changed for this PWA parity task.

## Evidence

- Smoke JSON: `MVP_EVIDENCE/pwa-iphone-parity-postfix-qa-20260727-005600/iphone-parity-smoke.json`
- Smoke runner: `MVP_EVIDENCE/pwa-iphone-parity-postfix-qa-20260727-005600/iphone-parity-smoke.mjs`
- Screenshots:
  - `screenshots/01-login.png`
  - `screenshots/02-home.png`
  - `screenshots/03-quick-add.png`
  - `screenshots/04-category-overlay.png`
  - `screenshots/05-analytics.png`
  - `screenshots/06-top-categories-all.png`
  - `screenshots/07-top-categories-all-scrolled.png`

## Test matrix

| Area | Command / check | Result |
|---|---|---|
| Frontend unit tests | `npm.cmd test` in `apps/web-pwa` | PASS: 4 files, 65 tests |
| Production build | `npm.cmd run build` in `apps/web-pwa` | PASS: `tsc -b && vite build`, 1704 modules |
| Local server | `npm.cmd run dev -- --port 5173` | PASS: local Vite served `http://127.0.0.1:5173/` |
| iPhone login | Playwright Chromium iPhone 14, mocked API | PASS |
| iPhone home / FAB / bottom nav | no horizontal overflow; controls hit-test in viewport | PASS |
| Quick add sheet | no horizontal overflow; sheet, more, submit controls hit-test | PASS |
| Category picker overlay | no horizontal overflow; search and option hit-test | PASS |
| Analytics | no horizontal overflow; 4 metric cards; first/last cards reachable by scroll | PASS |
| Top categories all | server breakdown path, no fallback warning | PASS |
| Top categories all modal stacking | modal hit-test overlays FAB and bottom nav | PASS |
| Top categories all dialog scroll | inner `.listStack` scrolls: `clientHeight=570`, `scrollHeight=2594`, `after=2024` | PASS |

## Android parity covered in PWA browser smoke

- Expense category selection parity: `Категория` opens a searchable vertical overlay.
- Mobile quick add parity: sheet layout and primary controls remain reachable on iPhone viewport.
- Analytics parity: summary metrics remain visible and scrollable on mobile viewport.
- Home top categories parity: `Все` opens all spending categories from server breakdown, sorted/listed in the dialog.

## Limits and residual risks

- Real iPhone/Safari manual run was not performed; this is Playwright Chromium with an iPhone 14 viewport/device profile.
- Production HTTPS/secure-cookie behavior remains a risk if production PWA continues to be served only as plain HTTP IP. Secure cookies/service-worker/installability need a secure origin or an accepted waiver.
- OCR remains online-only for PWA/iOS browser and was not re-tested in this parity smoke.
- API data was mocked in Playwright; no production credentials, cookies, tokens, session IDs or production financial data are stored in evidence.
