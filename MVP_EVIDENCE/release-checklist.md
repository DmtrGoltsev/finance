# Release Checklist MVP

Дата релизной проверки: `2026-05-18`
Сборка / commit / tag: `PENDING: current folder is not a git repo; release-git-worker approved`
Окружение: `local Windows workspace, dev seeded backend, PWA dev/build evidence, Android emulator evidence`
Ответственный QA/evidence: `FINAL-MVP-GATE-REVIEWER-2`

Итоговый статус MVP completion: `GO / FUNCTIONAL MVP COMPLETE WITH DOCUMENTED LIMITATIONS`
Итоговый статус GitHub publication worker: `GO TO START release-git-worker`
Итоговый статус GitHub public publication/tag: `PENDING release-git-worker safety gates`

## Базовая готовность

- [ ] Подтвержден актуальный commit/tag сборки MVP. Статус: pending `release-git-worker`.
- [x] Backend/API доступны в локальном dev/demo окружении: `http://127.0.0.1:8000`.
- [x] Backend/API подтверждены в production-like DB migration proof на real PostgreSQL: `MVP_EVIDENCE/reports/2026-05-18_postgres-alembic-live-proof-worker.md`.
- [x] PWA открывается на desktop viewport с live backend flow и CRUD evidence.
- [x] iOS-like PWA viewport screenshots получены как browser evidence.
- [x] Android собран, unit tests и connected tests проходят.
- [x] Android native CRUD screenshots валидны как PNG.
- [x] Нет открытых P0 functional MVP blockers.
- [x] Final MVP gate review 2 создан: `MVP_EVIDENCE/reports/2026-05-18_final-mvp-gate-review-2.md`.

## Подтвержденные automated checks

- [x] Backend full pytest fresh reviewer run: `149 passed, 3 warnings`.
- [x] Backend W3 API contract/runtime evidence exists.
- [x] Backend transactions runtime evidence exists.
- [x] Backend transfer safety evidence exists.
- [x] Backend report runtime evidence exists.
- [x] PWA tests fresh reviewer run: `2 test files passed`, `7 tests passed`.
- [x] PWA build fresh reviewer run: `vite build` succeeded.
- [x] PWA live CRUD/transfer/reports E2E worker pass exists.
- [x] Android `:app:testDebugUnitTest`: `BUILD SUCCESSFUL`.
- [x] Android `:app:assembleDebug`: `BUILD SUCCESSFUL`.
- [x] Android `:app:connectedDebugAndroidTest`: `BUILD SUCCESSFUL`, `2` tests on emulator.

## Обязательные release flows

- [x] Demo login/session через dev seeded backend.
- [x] Release-grade PWA cookie/CSRF session flow: `MVP_EVIDENCE/reports/2026-05-18_pwa-cookie-csrf-integration-worker.md`.
- [x] Release-grade Android secure token persistence: `MVP_EVIDENCE/reports/2026-05-18_android-secure-storage-worker.md`.
- [x] Accounts CRUD/archive/restore/delete на PWA с live backend evidence.
- [x] Accounts lifecycle controls на Android с live backend evidence.
- [x] Categories CRUD/archive/restore/delete на PWA с live backend evidence.
- [x] Categories lifecycle controls на Android с live backend evidence.
- [x] Transactions create/edit/list/delete/restore на PWA/Android с live backend evidence.
- [x] Same-scope transfer lifecycle на PWA/Android с live backend evidence via transaction semantics.
- [x] Backend same-scope transfer safety tests.
- [x] Backend shared family / combined viewer report tests.
- [x] Report UX screenshots/evidence на PWA/iOS-like и Android.
- [x] Backend negative privacy cases for financial runtime.
- [ ] Expanded client/device negative privacy smoke. Статус: release-hardening follow-up, not functional P0.
- [x] Real PostgreSQL + Alembic startup/migration evidence.
- [x] Final Android screenshots are valid PNG.
- [x] Final iOS/PWA browser screenshots are valid PNG.

## Evidence Gates

- [x] Для каждого текущего `PASS` есть ссылка на screenshot, log, report или run note.
- [x] Для каждого limitation указана причина и следующий evidence target.
- [x] Android screenshots являются валидными изображениями.
- [ ] Итоговый `MVP_RELEASE_REPORT.md` отражает release candidate commit/tag. Статус: pending `release-git-worker`.
- [x] Нет TODO placeholders, противоречащих актуальным functional MVP evidence.

## Release Blockers

- [x] RB-001 закрыт: real PostgreSQL + Alembic live runtime доказан.
- [x] RB-002 закрыт: PWA cookie/CSRF доказан.
- [x] RB-003 закрыт: Android secure token storage доказан.
- [x] RB-004 закрыт с limitation: frontend/mobile full CRUD/transaction lifecycle evidence доказан; Android controls deterministic MVP values.
- [x] RB-005 закрыт: transfer lifecycle evidence на PWA/Android доказан через transaction semantics.
- [x] RB-006 закрыт: final screenshots, включая валидные Android/PWA/iOS-like PNG.
- [ ] RB-007 pending: commit/tag/release candidate traceability. Next worker: `release-git-worker`.
- [ ] RB-008 accepted limitation: backend/Android CVE tooling unavailable; PWA audit clean.

## Известные ограничения MVP

- [x] Bank import не входит в MVP.
- [x] Bank API integrations не входят в MVP.
- [x] SMS import/parsing не входит в MVP.
- [x] Push notifications не входят в MVP.
- [x] Broker/investment integrations не входят в MVP.
- [x] Physical iPhone validation заменена iOS-like PWA viewport evidence.
- [x] Android arbitrary edit forms остаются post-MVP UX improvement; MVP lifecycle controls proven.
- [x] Backend/Android CVE scanner reports pending approved tooling or explicit waiver.

## Решение

MVP completion: `GO / FUNCTIONAL MVP COMPLETE WITH DOCUMENTED LIMITATIONS`

GitHub publication worker: `GO TO START release-git-worker`

Actual GitHub publication/tag: `PENDING release-git-worker safety gates`

