# Release Checklist MVP

Дата релизной проверки: `2026-05-19`
Production deployed commit evidence: `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`
Observed local tag state: `v0.1.0-mvp` points to `94d2484a74131f53badf0cd83610b925770fb710`
Окружение: `production deployment, iPhone/browser QA, Android QA`
Authoritative final report: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`

Итоговый статус: `Production MVP functional GO with documented limitations`
Safe release wording: `Production MVP functional GO on 2026-05-19 for iPhone/browser and Android on deployed commit evidence 808f7278..., with documented limitations; tag alignment remains open and requires explicit owner approval before any tag mutation.`
Security/ops статус: `NOT FULL SECURITY GO; open follow-ups remain without CVE/HTTPS/backup/restore proofs or explicit waivers`

## Базовая готовность

- [x] Подтвержден актуальный production commit: `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`.
- [ ] Tag alignment remains open: observed local tag `v0.1.0-mvp` points to `94d2484a74131f53badf0cd83610b925770fb710`, not the production deployed commit evidence `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`; retag/push requires explicit owner approval.
- [x] Backend/API доступен в production deployment: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`.
- [x] PWA/iPhone browser final QA завершен со статусом GO: `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md`.
- [x] Android final QA завершен со статусом GO: `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/android-final-prod-qa-report.md`.
- [x] Final production report фиксирует deployed version, Backend/DB status, QA coverage summary и known non-blocking gaps.
- [x] Ранние HOLD reports сохранены как исторический контекст и считаются superseded финальными GO reports.
- [x] Нет открытых P0 functional MVP blockers по финальному production evidence.

## Подтвержденные functional production flows

- [x] Login/logout подтвержден на iPhone/browser и Android.
- [x] Accounts/assets flows подтверждены в рамках documented platform limitations.
- [x] Personal/shared privacy smoke подтвержден для production MVP scope.
- [x] Categories add/edit подтверждены.
- [x] Income, expense и transfer flows подтверждены.
- [x] Reports modes подтверждены: personal, shared/common и overview.
- [x] Brokerage/investment API smoke подтвержден на уровне final production report.
- [x] Import остается metadata-only placeholder и явно задокументирован как limitation.
- [x] PWA service worker limitation на plain HTTP IP отделен от code HOLD и не блокирует online browser use.

## Evidence gates

- [x] Authoritative verdict указан: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`.
- [x] Final PWA/iPhone GO report указан: `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md`.
- [x] Final Android GO report указан: `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/android-final-prod-qa-report.md`.
- [ ] Release tag alignment is open and documented in checklist and release report; production deployed commit evidence remains `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`.
- [x] Historical local/dev evidence не представлено как текущий production verdict.
- [x] Документ не содержит raw screenshots, XML, credential metadata, runner scripts, UUID/account/amount values.

## Known documented limitations

- [x] Нет HTTPS/domain; полноценный PWA install и штатная service worker работа на plain HTTP IP недоступны.
- [x] Android account CRUD покрыт через quick-add asset flow, а не отдельный полный CRUD screen.
- [x] Import остается metadata-only placeholder.
- [x] Investment detailed UI ограничен; final report фиксирует brokerage/investment API smoke.
- [x] Ранние HOLD findings superseded финальными production GO reports, но не удалены.

## Security and ops follow-ups

- [ ] HTTPS/domain для production PWA install и service worker.
- [ ] Backend dependency CVE proof или explicit waiver.
- [ ] Android dependency CVE proof или explicit waiver.
- [ ] Production backup proof.
- [ ] Production restore proof.
- [ ] Formal security release decision после CVE/HTTPS/backup/restore proofs или explicit waivers.

## Решение

Production MVP functional GO: `GO on 2026-05-19 for iPhone/browser and Android`

Production deployed commit evidence: `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`

Observed local tag state: `v0.1.0-mvp` -> `94d2484a74131f53badf0cd83610b925770fb710`

Tag alignment: `OPEN; requires explicit owner approval before retag/push`

Authoritative verdict: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`

Security/ops: `open follow-ups; do not claim full security GO`
