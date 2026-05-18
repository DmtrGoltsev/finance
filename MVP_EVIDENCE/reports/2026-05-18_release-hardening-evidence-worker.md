# Release hardening evidence worker report

Дата: 2026-05-18

Роль: `RELEASE-HARDENING-EVIDENCE worker`

Итоговая рекомендация: **HOLD для полного security GO**.

Причина HOLD: PWA `npm audit` чистый, но для backend Python и Android/JVM полноценный CVE scanner в среде отсутствует (`pip-audit`, `dependency-check`, `osv-scanner`, `grype`, `trivy` не найдены). Dependency inventory собран, но это не заменяет CVE gate.

## Scope

- Бизнес-логика не редактировалась.
- Созданы/обновлены только evidence artifacts в `MVP_EVIDENCE/test-runs/**` и `MVP_EVIDENCE/reports/**`.

## Dependency inventory / SBOM

Статус: **PASS WITH LIMITATIONS**.

Собран dependency inventory без установки новых инструментов:

- PWA: `apps/web-pwa/package-lock.json`, `npm.cmd ls --all --json`.
- Backend: существующая `apps/backend/.venv`, `pip list --format=json`, `apps/backend/pyproject.toml`.
- Android: Gradle wrapper `app:dependencies --configuration debugRuntimeClasspath`.

Ключевые цифры:

- PWA lock entries excluding root: `212`.
- Backend installed packages in `.venv`: `38`.
- Android resolved unique debug runtime coordinates: `155`.

Артефакты:

- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-dependency-inventory.md`
- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-dependency-inventory.json`
- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-pwa-npm-ls.json`
- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-backend-pip-list.json`
- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-android-debugRuntimeClasspath.txt`
- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-android-dependencyInsight-security-crypto.txt`
- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-android-dependencyInsight-tink.txt`

Ограничение: это inventory, а не формальный CycloneDX/SPDX SBOM.

## Vulnerability / CVE checks

Статус: **HOLD**.

Выполнено:

- `npm.cmd audit --json`
  - результат: `0` vulnerabilities total; `critical=0`, `high=0`, `moderate=0`, `low=0`.
  - артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-pwa-npm-audit.json`

Блокеры:

- `pip-audit` отсутствует в backend `.venv`.
  - команда: `.\.venv\Scripts\python.exe -m pip_audit --format=json`
  - результат: `No module named pip_audit`
  - артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-backend-pip-audit.txt`
- Android/JVM CVE scanner отсутствует.
  - `dependency-check`, `osv-scanner`, `grype`, `trivy` не найдены.
  - глобальный `gradle` не найден; Gradle wrapper доступен и использован только для dependency graph / dependency insight.
  - артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-security-tooling-availability.txt`

Вывод: PWA dependency CVE check **PASS**, backend и Android CVE gate **HOLD**.

## Log redaction / secret scan

Статус: **PASS WITH LIMITATIONS**.

Выполнен `rg` scan по evidence/test logs/source областям с исключением `node_modules`, build outputs, venv, binary/png/jar/class и Chrome profiles.

Артефакт:

- `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-redaction-scan.txt`

Классификация найденного:

- Реальные bearer/session/access/refresh token values в evidence logs не обнаружены.
- `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-cookiejar.txt` не содержит cookies.
- Найдены benign/test placeholders: `invalid-token`, `raw-token-must-not-echo`, `test-token-${UUID.randomUUID()}`.
- Найдены dev-only credentials: `demo-password-only`, `correct horse battery staple` в тестах/seed.
- Найдены Android UI dump атрибуты `password="false"`; это не secret dump.
- В старых отчетах есть текстовое упоминание прежнего PWA localStorage bearer blocker, но без token values; более поздний PWA cookie/CSRF отчет закрывает этот blocker.

Ограничение: это regex/static scan, не DLP scanner.

## Offline / API unavailable behavior

Статус: **PASS WITH LIMITATIONS**.

PWA:

- Добавлен evidence-only Vitest test в `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-pwa-api-unavailable.test.tsx`.
- Проверка: `App` с клиентом, у которого `getDashboardSnapshot()` падает как `API unavailable`, рендерит error state с текстом про `live API` вместо crash.
- Итоговый успешный запуск:
  - `apps\web-pwa\node_modules\.bin\vitest.cmd run MVP_EVIDENCE\test-runs\2026-05-18_release-hardening-pwa-api-unavailable.test.tsx --config MVP_EVIDENCE\test-runs\2026-05-18_release-hardening-pwa-api-unavailable.vitest.config.ts --root .`
  - результат: `1 passed (1)`
  - артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-pwa-api-unavailable-vitest-config-3.txt`

Android:

- Source-review evidence: `LiveFinanceApiClient.safeCall` catches `ApiException` and generic `Exception`, returns `ApiResult.Failure` with user-facing API connection message; `FinanceApp` renders `Failure.message` into UI state.
- Unit suite:
  - `.\gradlew.bat testDebugUnitTest`
  - результат: `BUILD SUCCESSFUL`
  - артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-android-testDebugUnitTest.txt`

Ограничения:

- Browser service-worker offline/cache behavior не проверялся.
- Android emulator/device airplane-mode/no-network smoke не запускался в этом worker pass.

## Stale session / invalid token behavior

Статус: **PASS** для backend session boundary.

Выполнено:

- `.\.venv\Scripts\python.exe -m pytest tests\auth\test_session_flow.py::test_malformed_invalid_and_revoked_tokens_are_neutral tests\auth\test_session_flow.py::test_cookie_authenticated_unsafe_request_with_csrf_is_allowed_and_clears_cookies -q`
- результат: `2 passed, 1 warning`.
- артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-backend-stale-session-pytest.txt`

Покрыто:

- malformed bearer: `401`
- invalid bearer: `401`
- bearer logout: `204`
- revoked bearer after logout: `401`
- cookie logout with CSRF: `204`
- cookie current session after logout: `401`
- token plaintext не отражается в response body по тестовому assertion.

PWA regression suite:

- `npm.cmd test -- --run`
- результат: `2 passed test files`, `6 passed tests`.
- артефакт: `MVP_EVIDENCE/test-runs/2026-05-18_release-hardening-pwa-vitest.txt`

## Commands / results summary

- `npm.cmd audit --json`: PASS, `0` vulnerabilities.
- `npm.cmd ls --all --json`: PASS, dependency graph captured.
- `.\.venv\Scripts\python.exe -m pip list --format=json`: PASS, `38` packages captured.
- `.\.venv\Scripts\python.exe -m pip_audit --format=json`: HOLD, `No module named pip_audit`.
- `.\gradlew.bat app:dependencies --configuration debugRuntimeClasspath`: PASS, graph captured.
- `.\gradlew.bat app:dependencyInsight --dependency androidx.security:security-crypto --configuration debugRuntimeClasspath`: PASS, insight captured.
- `.\gradlew.bat app:dependencyInsight --dependency com.google.crypto.tink:tink-android --configuration debugRuntimeClasspath`: PASS, insight captured.
- `rg` redaction scan: PASS WITH LIMITATIONS, no real token values found; benign/dev findings classified.
- Backend stale-session targeted pytest: PASS, `2 passed`.
- PWA full Vitest suite: PASS, `6 passed`.
- PWA API unavailable evidence Vitest: PASS, `1 passed`.
- Android unit tests: PASS, `BUILD SUCCESSFUL`.

## Release recommendation

Security recommendation: **HOLD**.

Release can move only as **PASS WITH LIMITATIONS** if approvers explicitly accept:

- backend Python CVE scan not executed because `pip-audit` is unavailable;
- Android/JVM CVE scan not executed because no vulnerability scanner is installed/configured;
- PWA offline evidence covers API-unavailable UI behavior, not full service-worker/browser offline mode;
- Android offline evidence is source-review + unit-suite, not emulator no-network runtime smoke.

To turn HOLD into GO:

- run backend CVE scan with approved tooling (`pip-audit` or equivalent) against the resolved environment/lock;
- run Android/JVM dependency CVE scan with approved tooling (`dependency-check`, OSV, Gradle plugin, or equivalent);
- optionally add browser offline/service-worker smoke and Android emulator no-network smoke to release evidence.
