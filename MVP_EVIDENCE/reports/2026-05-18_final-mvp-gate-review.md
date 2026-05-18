# Final MVP Gate Review

Дата: `2026-05-18`
Роль: `FINAL-MVP-GATE-REVIEWER`
Рабочая папка: `C:\Users\style\Documents\Codex\Финансы`

## Итоговое решение

- MVP completion относительно запроса "полноценный MVP со всеми тестами на Android и iOS/PWA": `HOLD / NOT FULL MVP`.
- GitHub publication/tag: `HOLD / DO NOT PUBLISH OR TAG AS MVP`.
- Evidence folder readiness: `READY FOR HOLD DECISION`, но `NOT READY FOR GO RELEASE`.

Основание: PWA full-flow evidence существенно продвинулось и закрывает operation lifecycle, transfer display count и report modes. Android live evidence доказывает read/report/transfer equivalence и secure storage, но сам Android worker фиксирует `HOLD` для full native CRUD UX: в Android UI нет нативных controls создания/редактирования/удаления сущностей. Для "полноценного MVP" это blocker, потому что product MVP требует ручной ввод и редактирование счетов, категорий и операций на Android и PWA/браузере.

## Fresh reviewer checks

Выполнены safe повторные проверки без правок продуктового кода:

- Backend: `.\.venv\Scripts\python.exe -m pytest -q` в `apps/backend` -> `149 passed, 3 warnings in 13.10s`.
- PWA: `npm.cmd test` в `apps/web-pwa` -> `2 passed`, `6 passed`.
- Android quick: `.\gradlew.bat :app:testDebugUnitTest` в `apps/android` -> `BUILD SUCCESSFUL`, `25 actionable tasks: 1 executed, 24 up-to-date`.

Connected Android, PWA E2E, build и screenshot validation не перезапускались reviewer-ом: свежие worker artifacts от `2026-05-18` уже присутствуют и достаточны для gate-решения.

## Evidence accepted

- PWA cookie/CSRF: `PASS`; no localStorage bearer blocker closed.
- PWA full-flow E2E: `PASS` для operation create/update/archive/delete/restore, transfer section `count=1`, reports `2` modes, desktop и iOS-like screenshots.
- Android secure storage: `PASS`; encrypted preferences evidence есть.
- Android live read/report/transfer: `PASS` для equivalent read/report flow, transfer seed `TRANSFER_COUNT=1`, valid PNG evidence.
- PostgreSQL/Alembic live proof: `PASS` для disposable local PostgreSQL + Alembic head; route-level DB sync smoke ограничен отсутствием `psycopg/psycopg2`.
- Release hardening: PWA `npm audit` `0` vulnerabilities, stale-session tests pass, secret scan without real token values.

## Gate findings

### MVP completion

`HOLD`.

Android proven equivalent is not enough. It proves backend/API compatibility and Android read/report visibility, but not user-facing native CRUD controls. Product MVP acceptance requires manual create/edit for accounts, categories and operations, and main scenarios must be available on Android and PWA/browser for iPhone.

PWA operation lifecycle is now proven, but full MVP still lacks complete cross-platform proof for accounts/categories CRUD/archive/restore and user-facing transfer creation/update lifecycle. Seeded transfer display is useful evidence, not proof that the user can manually create and edit transfers on both platforms.

### CVE tooling

Unavailable backend/Android CVE scanners are not the primary functional MVP blocker. They remain a release-hardening/security limitation and keep full security GO on `HOLD` unless approvers explicitly accept the limitation.

For public release, enterprise handoff, or a release tag claiming security-ready status, backend Python and Android/JVM CVE scanning should be completed with approved tooling.

### Git/GitHub

`HOLD` for GitHub publication/tag as completed MVP.

The folder is not a git repository (`NOT_A_GIT_REPO`), so commit/tag traceability is absent. Git bootstrap can start as a separate traceability task, but a public repository publication or MVP release tag must wait until functional blockers are closed and the release report points to an actual release candidate commit/tag.

## Remaining blockers

| ID | Severity | Blocker | Required closure evidence |
|---|---|---|---|
| FMG-001 | P0 | Android native CRUD controls absent | Android UI controls and connected/e2e evidence for create/edit/archive/delete/restore of required MVP entities. |
| FMG-002 | P0 | Cross-platform accounts/categories CRUD not fully proven | PWA and Android evidence for account/category create/edit/archive/delete/restore, with screenshots/logs. |
| FMG-003 | P0 | User-facing transfer lifecycle not fully proven | PWA and Android live scenario for manual same-scope transfer create/update/archive/restore or approved scope narrowing. |
| FMG-004 | P1 | Client/device negative privacy smoke incomplete | PWA/iOS-like and Android UI/cache/session evidence for no hidden personal data leakage after denied/stale/left/revoked scenarios. |
| FMG-005 | P1 | Release traceability absent | Git repository initialized or selected, clean release candidate commit recorded, tag strategy documented. |
| FMG-006 | P1 | Backend/Android CVE scanners unavailable | Approved backend Python and Android/JVM vulnerability scans, or explicit release-hardening waiver. |

## Exact next workers

1. `ANDROID-NATIVE-CRUD-UX-WORKER` - Android engineer, reasoning `high`; implement and prove native controls for MVP CRUD/lifecycle flows, including connected tests and screenshots.
2. `PWA-ACCOUNTS-CATEGORIES-TRANSFER-CRUD-WORKER` - PWA engineer, reasoning `medium`; close account/category CRUD and manual transfer lifecycle gaps on PWA/iOS-like viewport.
3. `CLIENT-PRIVACY-NEGATIVE-QA-WORKER` - QA/security engineer, reasoning `high`; prove client/device negative privacy, stale session and cache/back-stack behavior on PWA and Android.
4. `RELEASE-TRACEABILITY-GIT-WORKER` - release engineer, reasoning `medium`; bootstrap or select git repo/remote and prepare release candidate traceability. Final MVP tag only after gate GO.
5. `SECURITY-CVE-SCAN-WORKER` - security/release-hardening engineer, reasoning `high`; run approved backend and Android/JVM CVE tooling or produce an explicit waiver package.
6. `FINAL-MVP-GATE-REVIEWER` - reviewer, reasoning `high`; rerun gate after blockers close and update `MVP_EVIDENCE`.

## Final note

Evidence folder is coherent enough to defend a `HOLD` decision. It is not yet coherent enough to defend "полноценный MVP со всеми тестами на Android и iOS/PWA" as complete.
