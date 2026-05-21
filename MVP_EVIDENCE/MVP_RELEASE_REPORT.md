# MVP Release Report

Дата отчета: `2026-05-22`
Production deployed commit evidence: `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`
Current production backend/PWA runtime: `808f7278` release path
Android client fix commit: `d9ffc75454c57007b465f51b7782c12c52935823` (`d9ffc75`)
Docs commit already pushed: `2c15b5a`
Observed local tag state: `v0.1.0-mvp` points to `94d2484a74131f53badf0cd83610b925770fb710`
Окружение: `production deployment, iPhone/browser QA, Android QA, Android production emulator rerun`
Authoritative final report: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`
Latest Android production emulator rerun: `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/QA_REPORT.md`

Итоговый статус: `Production MVP functional GO with documented limitations`
Safe release wording: `Production MVP functional GO on 2026-05-19 for iPhone/browser and Android on deployed backend/PWA runtime evidence 808f7278..., with documented limitations; Android client session-restore fix d9ffc75 passed production emulator rerun on 2026-05-22; docs/evidence package GO excludes tag mutation, and tag alignment remains open pending explicit owner approval.`
Security/ops статус: `NOT FULL SECURITY GO; CVE/HTTPS/backup/restore proofs or explicit waivers are still required`

## Current authoritative status

Authoritative verdict теперь находится в `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`.

Финальный production MVP принят как functional GO для iPhone/browser и Android на production deployed commit evidence `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a` с documented limitations. Этот документ синхронизирован с финальным отчетом и не должен читаться как отдельный full security GO.

## Traceability Note

Production deployed commit evidence for the backend/PWA runtime remains `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a` (`808f7278`). Android client session-restore fix commit is `d9ffc75454c57007b465f51b7782c12c52935823` (`d9ffc75`). Docs commit `2c15b5a` was already pushed. Observed local tag state is `v0.1.0-mvp` -> `94d2484a74131f53badf0cd83610b925770fb710`. Therefore tag alignment remains open in this docs package, and any retag/push/tag mutation requires explicit owner approval. The GO language in this report applies only to the docs/evidence package and functional production evidence, excluding tag mutation.

## Superseded historical context

Отчеты и checklist от `2026-05-18` остаются историческим evidence context для pre-production и pre-release проверок. Они не удаляются, но прежние ожидания traceability, прежние описания pre-production окружения и earlier HOLD statements считаются superseded финальным production report от `2026-05-19`.

Earlier HOLD reports также остаются в evidence folder как история remediation. Current release status определяется только финальным production report и двумя final GO reports:

- PWA/iPhone final GO: `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md`.
- Android final GO: `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/android-final-prod-qa-report.md`.

## Production QA summary

| Область | Статус | Доказательства | Комментарий |
|---|---|---|---|
| Final production verdict | GO | `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md` | Authoritative source of truth for release status. |
| PWA/iPhone browser | GO | `MVP_EVIDENCE/prod-qa-20260519-040710/pwa-iphone-final/prod-pwa-iphone-final-qa-report.md` | Browser/iPhone production QA passed; service worker limitation on plain HTTP IP is environmental. |
| Android | GO | `MVP_EVIDENCE/prod-qa-20260519-040640/android-final/android-final-prod-qa-report.md` | Android production QA passed after remediation. |
| Android session restore rerun | PASS | `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/QA_REPORT.md`; `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/SMOKE_EVIDENCE.md` | APK built from Android client fix `d9ffc75` was tested on emulator against production API/PWA while backend/PWA runtime remained `808f7278`; force-stop/cold relaunch session persistence passed. |
| Latest evidence hygiene | PASS | `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/evidence-validation-summary.json`; `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/png-validation-final-valid.json`; `MVP_EVIDENCE/prod-full-test-20260522-000115-rerun/android-emulator/data/secret-scan-password-exact.json` | Latest rerun recorded 21/21 valid screenshots, 0 exact password hits, 0 email hits in XML, and PWA/API health 200. Raw screenshots remain uncommitted unless later privacy-approved. |
| Backend/DB production status | PASS | `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md` | Final report records Backend/DB status and health summary. |
| Release traceability | OPEN | deployed commit evidence `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`; observed local tag `v0.1.0-mvp` -> `94d2484a74131f53badf0cd83610b925770fb710` | Tag alignment requires explicit owner approval before any retag/push/tag mutation. |
| Security/ops | OPEN FOLLOW-UP | This report and final report limitations | Not a full security GO without CVE/HTTPS/backup/restore proofs or explicit waivers. |

## Confirmed functional scope

- Login/logout.
- Accounts/assets flows within documented platform limitations.
- Personal/shared privacy smoke.
- Categories add/edit.
- Income, expense and transfer flows.
- Reports modes: personal, shared/common and overview.
- Android session persistence after force-stop/cold relaunch, verified in the 2026-05-22 production emulator rerun.
- Brokerage/investment API smoke.
- Import metadata-only placeholder, documented as non-blocking MVP limitation.

## Documented limitations

- No HTTPS/domain yet; PWA service worker and full PWA install are unavailable on plain HTTP IP.
- Android account CRUD is covered through quick-add asset flow rather than a dedicated full account CRUD screen.
- Import remains a metadata-only placeholder.
- Investment detailed UI is limited; production evidence covers brokerage/investment API smoke.
- Earlier HOLD reports are superseded by final production GO reports, not deleted.
- Latest Android production emulator rerun created production QA data through the app UI; no production cleanup was performed. Cleanup/retention remains an owner decision.
- Raw screenshots from the latest rerun remain local/uncommitted unless later privacy-approved.

## Security and ops follow-ups

The release docs must not claim full security GO until one of the following is available for each area: proof or explicit waiver.

- HTTPS/domain proof for production PWA install and service worker.
- Backend dependency CVE proof or waiver.
- Android dependency CVE proof or waiver.
- Production backup proof or waiver.
- Production restore proof or waiver.

## Release decision

Production MVP functional GO: `GO on 2026-05-19 for iPhone/browser and Android`

Production deployed commit evidence: `808f7278a7cc29aaf6f179adb22b61ffdc6fa06a`

Observed local tag state: `v0.1.0-mvp` -> `94d2484a74131f53badf0cd83610b925770fb710`

Tag alignment: `OPEN; requires explicit owner approval before retag/push`

Authoritative verdict: `MVP_EVIDENCE/prod-final-20260519/FINAL_PROD_MVP_REPORT.md`

Security/ops: `open follow-ups; do not claim full security GO`

Production QA data cleanup/retention: `owner decision required; no cleanup performed in latest Android rerun`
