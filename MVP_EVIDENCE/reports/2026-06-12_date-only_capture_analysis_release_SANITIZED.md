# Finance date-only capture / analysis release closure

Дата: 2026-06-12
Проект: Finance
Branch: `newDis`
Scope: backend date-only/report flow, PWA deploy, Android asset editing stabilization, curated QA/KB integration.

## Executive status

Release status: PASS with one explicit residual BLOCKED item.

- Backend production deploy: PASS.
- PWA production deploy: PASS.
- Android payment filter/date-only/analysis regression coverage: PASS by sanitized QA evidence.
- Android asset edit regression: PASS after Metal manual amount fix.
- Capture confirmation live Android confirmation: BLOCKED, not converted to PASS.
- Secret handling: no secrets, tokens, cookies, passwords, raw auth payloads, raw OCR payloads, screenshots, or UI XML are stored in this curated report.

## Backend production deploy

- Commit deployed: `26b487d61b7d2d6de704f0a632bcb08ff7f240f7`.
- Host: `45.10.110.42`.
- Service: `finance-backend.service`.
- Release path: `/opt/finance/releases/20260612T045020Z-26b487d6`.
- Alembic before: `20260607_0013`.
- Alembic after: `20260612_0015`.
- Backup: `/var/backups/finance/finance_prod_pre_20260612_0015_20260612T045110Z_26b487d6.dump`.
- Backup SHA256: `6b48a4e8f73cbabeb40553eb052869c861bb2954edad0d960d3bbc7a34316ef8`.
- Smoke: health PASS, OpenAPI PASS, authenticated smoke PASS.

## PWA production deploy

- Target: `http://45.10.110.42/finance/`.
- Release: `20260612T091555Z-26b487d61b7d`.
- Public JS asset: `/finance/assets/index-BxFzW0Su.js`.
- Public CSS asset: `/finance/assets/index-BGpCKtps.css`.
- Local gate: `npm.cmd run test` PASS, `npm.cmd run build` PASS.
- Remote/static smoke: nginx/public frontend/manifest/service worker asset/backend health PASS.
- Evidence: `MVP_EVIDENCE/reports/2026-06-12_pwa_prod_deploy_SANITIZED.md`.

## Android final APK

- Source APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk`.
- Approved local artifact copy: `artifacts/apk/finance-mvp-newd-0.1.0-debug.apk`.
- APK SHA256: `6AEE934A8817055B1738B32E1468D2A4C5415502C224115F9C7953F63EC3D893`.
- Size: `54235740` bytes.
- Artifact staging status: local only; `*.apk` is intentionally ignored by repository rules.

## Android QA summary

Final sanitized Android evidence:

- `MVP_EVIDENCE/date-only-capture-analysis-qa-metal-fix-20260612-133358/QA_REPORT_SANITIZED.md`.

PASS items:

- Payment account filter excludes non-payment accounts for expenses and keeps income account selection broader.
- Date-only analysis/report flow remains covered by final date-only analysis QA evidence.
- Asset edit dialogs for Broker/Card do not show icon picker.
- Legacy `Металл` manual-only flow now exposes `Ручная сумма`, saves manual amount, reopens with the saved value, and still has no icon picker.
- Broker/Card negative checks show no manual amount field and no icon picker for account-backed groups.
- Focused JVM, full Android JVM, and debug APK build were reported PASS in the final Metal fix evidence.
- Secret scan in final Metal fix evidence: PASS.

Historical regression note:

- `MVP_EVIDENCE/date-only-capture-analysis-qa-final-D401-20260612-130029/QA_REPORT_SANITIZED.md` remains historical FAIL evidence for Metal before the manual amount fix.
- Final release status uses the later Metal fix PASS report above.

## Capture confirmation status

Status: BLOCKED.

No newer `MVP_EVIDENCE/date-only-capture-confirmation-escalation-*` sanitized report was present during release integration. The current source of truth is:

- `MVP_EVIDENCE/date-only-capture-confirmation-qa-20260612-100149/QA_REPORT_SANITIZED.md`.

Exact unblock options from the sanitized report:

- Provide a parseable synthetic image fixture known to produce at least one candidate through the live backend OCR engine.
- Provide an approved test-only seed endpoint/helper that creates a pending screenshot capture draft for the logged-in Android QA account without raw OCR/image input.
- Restore access to `/etc/finance/qa-owner.env` with key `FINANCE_QA_PASSWORD`, or reset the remote registration rate limit, so one synthetic account can be driven through Android UI safely.

Backend and Android unit/JVM coverage for update + confirm is reported PASS in the blocker report, but live Android confirmation did not complete and is not claimed as PASS.

## Safe QA account metadata

| Environment | Safe alias / identifier | Purpose | Secret handling |
|-------------|-------------------------|---------|-----------------|
| Production QA | `finance.qa@local.test` | Owner-operated production smoke and authenticated QA flows | Password value is never stored. Out-of-band locator only: `/etc/finance/qa-owner.env`, key `FINANCE_QA_PASSWORD`. |
| Development | `demo.owner@example.test` | Local/dev seeded flows and emulator/PWA development checks | No passwords, tokens, cookies, or sessions are stored. |

## Residual risks

- Capture confirmation live Android confirmation remains BLOCKED until one unblock path above is available.
- APK is debug-signed, not release-signed.
- Raw evidence directories remain intentionally local/ignored; only curated sanitized Markdown/JSON summaries are candidates for Git.
