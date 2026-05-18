# MVP Evidence

Дата обновления: `2026-05-17`
Ответственный worker: `W2-EVIDENCE`
Текущий статус пакета: `HOLD / NOT READY`

Эта папка собирает доказательства готовности MVP: отчеты, результаты тестовых прогонов, release blockers, placeholders для второй волны и будущие live/device screenshots. На момент этого обновления здесь зафиксированы реальные результаты first wave и подготовлены места для W2 evidence. Release-ready PASS не заявлен.

## Структура

- `reports/` - русскоязычные отчеты, summaries и ссылки на review-артефакты.
- `test-runs/` - результаты тестовых прогонов и placeholders для W2 runtime/build evidence.
- `screenshots/pwa-desktop/` - будущие screenshots PWA desktop.
- `screenshots/ios-pwa/` - будущие screenshots iOS/PWA.
- `screenshots/android/` - будущие screenshots Android.
- `release-checklist.md` - release checklist с текущими blockers.
- `test-matrix.md` - матрица MVP flows без фиктивных PASS.
- `MVP_RELEASE_REPORT.md` - итоговый пользовательский отчет, сейчас в статусе HOLD.

## First Wave Evidence

- Summary report: `MVP_EVIDENCE/reports/2026-05-17_first-wave-summary.md`
- Integration review links: `MVP_EVIDENCE/reports/2026-05-17_first-wave-integration-review-links.md`
- Test summary: `MVP_EVIDENCE/test-runs/2026-05-17_first-wave-test-summary.md`
- Основной first-wave review: `docs/architecture/mvp-first-wave-integration-review.md`
- Архитектурный Wave 1 review: `docs/architecture/wave-1-integration-review.md`

## Зафиксированные результаты

- Backend first-wave pytest: `70 passed, 1 skipped`.
- PWA Vitest: `2 passed`.
- Android build/test: `BLOCKED` из-за отсутствующего Gradle wrapper/local Gradle.
- API contract tests: `18 passed, 1 skipped`.
- OpenAPI Redocly lint: `PASS`.

## Release Blockers

- Backend runtime все еще in-memory для accounts/categories, DB-backed runtime wiring ожидает W2 evidence.
- Auth/session не смонтирован как production flow.
- Transactions, transfers и reports отсутствуют в runtime.
- Android build заблокирован Gradle.
- Live/device screenshots пока отсутствуют.

## W2 Placeholders

- DB runtime evidence: `MVP_EVIDENCE/test-runs/W2_DB_RUNTIME_EVIDENCE_TODO.md`
- Android build evidence: `MVP_EVIDENCE/test-runs/W2_ANDROID_BUILD_EVIDENCE_TODO.md`

## Правила заполнения

1. Не ставить `PASS` без фактического evidence-файла, test output, screenshot или review-ссылки.
2. Для `BLOCKED` указывать причину блокировки и следующий владелец/worker.
3. Не добавлять screenshots/results, если они не были реально получены.
4. Технические команды, пути, API names и test output можно оставлять на английском.
