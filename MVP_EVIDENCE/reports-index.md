# Curated Evidence Index

Дата: `2026-05-22`
Статус: curated index для release/evidence review. Это не является full security GO.

Traceability caveat: production backend/PWA runtime remains release path `808f7278` (`808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`), while Android client session-restore fix commit `d9ffc75` (`d9ffc75454c57007b465f51b7782c12c52935823`) passed the 2026-05-22 production emulator rerun. Docs commit `2c15b5a` was already pushed. Observed local tag `v0.1.0-mvp` points to `94d2484a74131f53badf0cd83610b925770fb710`. Tag alignment remains open and requires explicit owner approval before any retag/push/tag mutation.

Этот индекс разделяет артефакты по пригодности к публикации и ревью. Authoritative/safe означает, что файл можно использовать как основной evidence artifact без дополнительной санитизации в рамках текущего review scope. Любые новые или не перечисленные ниже production QA данные должны проходить отдельную проверку перед коммитом, публикацией или передачей наружу.

## Authoritative / Safe Without Sanitization

Эти файлы можно считать основными безопасными evidence artifacts:

- `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`
- `MVP_EVIDENCE/prod-final-20260519/README.md`
- `MVP_EVIDENCE/prod-qa-20260519-024402/pwa-iphone/prod-pwa-iphone-qa-report.md`
- `MVP_EVIDENCE/prod-qa-20260519-024402/pwa-iphone/data/iphone-layout-scan.json`
- `MVP_EVIDENCE/prod-qa-20260519-024402/pwa-iphone/data/qa-import-placeholder-fixture.csv`
- `MVP_EVIDENCE/prod-qa-20260519-030840/android-rerun/secret-scan.json`
- `MVP_EVIDENCE/prod-qa-20260519-030840/android-rerun/png-validation.json`
- `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/data/api-health.json`
- `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/png-validation.json`
- `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/secret-scan.json`
- `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md`
- `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/data/desktop-layout-scan.json`
- `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/data/health.json`
- `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/data/iphone-layout-scan.json`
- `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/data/manifest-summary.json`
- `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/data/qa-import-placeholder-fixture.csv`
- `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/SMOKE_EVIDENCE.md`
- `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/api-health.json`
- `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/pwa-health.json`
- `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/png-validation-final-valid.json`
- `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/evidence-validation-summary.json`
- `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/secret-scan-password-exact.json`
- `MVP_EVIDENCE/android-production-release-20260822/SUMMARY_SANITIZED.md`

## Latest Rerun Reference Paths

Эти пути можно использовать для внутренней трассировки latest Android production emulator rerun, но перед публичным sharing или расширением release evidence bundle требуется отдельная privacy/sanitization review:

- Evidence root: `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/`
- QA report: `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/QA_REPORT.md`
- Smoke evidence: `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/SMOKE_EVIDENCE.md`

## Sanitization Needed Before Commit Or Sharing

Коммитить или передавать наружу только после санитизации и повторной проверки:

- Reports или JSON с ID, похожими на UUID.
- Данные с названиями счетов, категорий, транзакций или пользовательских объектов.
- Данные с суммами, балансами, лимитами или другими финансовыми значениями.
- Логи с login metadata, session metadata или сведениями об окружении, которые могут раскрывать доступы.
- Значения, похожие на email, персональные идентификаторы или contact metadata.

## Excluded / Keep Local

Эти материалы не должны входить в release evidence bundle без явного owner approval и отдельной санитизации:

- Raw runner scripts.
- Credential metadata.
- Credential-access proofs.
- Production DB inventory или login logs.
- Authenticated UI XML.
- Raw screenshots.
- JSON inventories с ID, именами пользовательских объектов или финансовыми значениями.
- Latest rerun raw screenshots under `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/screenshots/` unless later privacy-approved.
- Latest rerun UI XML under `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/xml/` unless separately reviewed and sanitized.

## Owner Decision Required

Для production QA data cleanup/retention нужен явный owner decision: что удалить, что оставить локально, что санитизировать и что можно перенести в release evidence. Latest Android rerun created QA data through the production app UI and no cleanup was performed. До owner decision excluded/keep-local материалы остаются локальными и не используются как публичное доказательство готовности.

## Review Notes

- Этот индекс подтверждает только curate/sanitize classification для перечисленных артефактов.
- Наличие `secret-scan.json` в safe list не означает полного security approval.
- Любое изменение состава evidence bundle требует обновления этого файла или отдельного review note.
