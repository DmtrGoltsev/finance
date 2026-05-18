# iPhone Browser QA Worker Report

Дата: 2026-05-18  
Проект: `C:\Users\style\Documents\Codex\Финансы`  
Роль: iPhone Browser QA Worker после planner + QA audit + fixes.

## Среда

- Реальный iPhone/Safari в среде недоступен.
- Fallback: Playwright Chromium `1.57.0` + профиль `iPhone 14`.
- Viewport: `390x664`.
- User agent: `Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1`.
- Финальный чистый backend dev seed: `http://127.0.0.1:8114`.
- Финальный PWA dev server: `http://127.0.0.1:5187`.
- Локальные cookie overrides для browser QA: `FINANCE_BACKEND_AUTH_COOKIE_SECURE=false`, `FINANCE_BACKEND_AUTH_SESSION_COOKIE_NAME=finance_session`.

## Evidence

- QA script: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-qa.js`
- JSON result: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-qa-results.json`
- Backend log: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-backend-8114.out.log`
- PWA log: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\test-runs\2026-05-18_iphone-browser-pwa-5187.out.log`

## Screenshots

- Overview: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-004-overview-pass.png`
- Quick Add: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-005-quick-add-pass.png`
- Operations transfer proof: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-006-operations-transfer-proof-pass.png`
- Assets: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-008-assets-pass.png`
- Categories: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-009-categories-pass.png`
- Analytics Личное: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-010-analytics-personal-pass.png`
- Analytics Общее: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-010-analytics-shared-pass.png`
- Analytics Обзор: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-010-analytics-overview-pass.png`
- Import placeholder: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\screenshots\ios-pwa\2026-05-18-iphone-browser-qa\iphone-dev-011-import-placeholder-pass.png`

## Results

- DEV-001 session/login: PASS. Auto-login completed; `localStorage` empty. Initial `401` on `/sessions/current` before login is expected and then recovered by login.
- DEV-002 Деньги / Личное: PASS. Personal view contains personal rows and excludes shared rows.
- DEV-003 Деньги / Общее: PASS. Shared view contains household rows and excludes personal rows.
- DEV-004 Деньги / Обзор: PASS. Overview contains current viewer personal + shared rows.
- DEV-005 Quick Add expense/income: FUNCTIONAL PASS only with QA fallback. Normal iPhone taps are blocked by layout defects; DOM-click fallback allowed creation and refresh proof.
- DEV-006 Quick Add transfer: PASS. `Расходы месяца` stayed `101 $` before and after transfer; transfer did not increase expense.
- DEV-007/008 Quick Add asset + Assets: PASS only with QA fallback. New shared deposit appeared; card/cash/deposit/brokerage/metal groups visible.
- DEV-009 Categories: CONTENT PASS, NAV FAIL. Categories page renders income/expense categories, but iPhone bottom nav does not expose `Категории`; screenshot reached via hidden desktop nav DOM fallback.
- DEV-010 Analytics Личное/Общее/Обзор: PASS. Metrics visible in all three modes.
- DEV-011 Import placeholder: PASS. Preview request captured as metadata-only.
- DEV-012 Import privacy: PASS. Personal preview sent `householdId: null`.
- Technical UI text: FAIL. Rendered UI contains `Dev` seed labels.

Captured import preview body:

```json
{
  "reportType": "brokerage_report",
  "sourceType": "file_metadata_only",
  "targetScope": "personal",
  "householdId": null,
  "fileName": "iphone-broker-report.csv",
  "fileSizeBytes": 26,
  "mimeType": "text/csv"
}
```

The uploaded test buffer contained `account,amount\nsecret,999\n`; neither `secret` nor `999` was present in the request body.

## Defects / Blockers

1. `IPHONE-PWA-FAB-TAP-001`: FAB `Добавить` is visible but normal iPhone tap is intercepted by content.
2. `IPHONE-PWA-QUICKADD-MORE-TAP-001`: Quick Add `Еще` is visible but tap is intercepted inside the sheet.
3. `IPHONE-PWA-QUICKADD-SUBMIT-TAP-001`: Quick Add submit is visible but tap is intercepted by fields above it.
4. `IPHONE-PWA-QUICKADD-KIND-Доход-TAP-001` / `IPHONE-PWA-QUICKADD-KIND-Актив-TAP-001`: Quick Add kind buttons can be intercepted inside the sheet.
5. `IPHONE-PWA-QUICKADD-VISIBILITY-Общее-TAP-001`: Shared visibility radio can be intercepted inside the sheet.
6. `IPHONE-PWA-NAV-Операции-TAP-001`, `IPHONE-PWA-NAV-Деньги-TAP-001`, `IPHONE-PWA-NAV-Активы-TAP-001`: mobile nav taps can be intercepted by main content.
7. `IPHONE-PWA-CATEGORIES-NAV-001`: iPhone bottom nav omits `Категории`; user cannot reach Categories by normal mobile navigation.
8. `IPHONE-PWA-TECH-TEXT-001`: rendered UI exposes `Dev` seed wording.

## Verdict

No GO for iPhone browser UX. Core backend/PWA functional flows are mostly correct under fallback automation, including transfer-not-expense and metadata-only import, but normal iPhone tap paths are not reliable and Categories is not reachable from mobile nav.
