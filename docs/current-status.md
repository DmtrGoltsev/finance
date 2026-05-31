# Current Status: Production MVP

## Статус

Production MVP получил **functional GO** на 2026-05-19 для iPhone/browser и Android.

Это не является full security GO и не является безусловным public production GO. Статус фиксирует, что восстановленная production-сборка проходит финальные функциональные проверки MVP в заявленных средах с явно описанными ограничениями и остаточными решениями владельцев.

## Production

- Commit: `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a` / short `808f727`.
- Observed local tag state: `v0.1.0-mvp` points to `94d2484a74131f53badf0cd83610b925770fb710`.
- Tag alignment: open; aligning `v0.1.0-mvp` to production deployed commit evidence requires explicit owner approval before any retag/push/tag mutation.
- Frontend: `http://<production-host>/finance/`.
- Backend API: `http://<production-host>/finance-api`.
- Authoritative final report: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`.

## Финальные доказательства

- Android final GO: `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/android-final-prod-qa-report.md`.
- PWA/iPhone final GO: `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md`.
- Финальное покрытие включает login/logout, accounts/assets, shared/personal privacy, categories add/edit, income/expense/transfer, brokerage/investment API smoke и report modes. Backend/OpenAPI cleanup после этого статуса вывел metadata-only import placeholder из mounted MVP scope.

## Ограничения

- PWA service worker на plain HTTP IP ограничен средой: приложение работает online, но штатный service worker/PWA install требует HTTPS/domain.
- CVE scans, backup/restore, physical iPhone/Safari требуют отдельного proof или waiver.
- Import endpoints не входят в текущий mounted backend/OpenAPI MVP scope; реальные импорт, парсинг файлов и создание операций/категорий/переводов остаются вне scope.
- SMS and push/notification interception are no longer part of the documented product state. The remaining capture-draft flow is user-initiated OCR from a user-selected screenshot: Android uses on-device OCR without screenshot upload, while PWA/iOS browser uses temporary upload to the self-hosted backend OCR endpoint. Screenshots and raw OCR text are not persisted, and transactions are created only after user confirm/edit.
- Investment detailed UI ограничен; подтвержден smoke-уровень brokerage/investment API.
- Production QA data cleanup/retention остается отдельным xhigh owner decision.
- Безопасность, комплаенс, домен/HTTPS и публичный запуск остаются отдельными gate, а не частью этого functional GO.

## Измененные файлы

- Changed files are tracked in git diff/status; this document is not an authoritative complete list.
