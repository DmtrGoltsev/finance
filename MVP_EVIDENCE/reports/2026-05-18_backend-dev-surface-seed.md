# Backend dev surface seed evidence

Дата: 2026-05-18  
Worker: `BACKEND-DEV-SURFACE-SEED`

## Итог

Backend dev surface подготовлен для live PWA/Android integration:

- стандартный backend запускается через `app.main:app`;
- dev-only seeded runtime запускается через `app.dev_seed:app`;
- локальные PWA origins `http://127.0.0.1:5174` и `http://127.0.0.1:5173` разрешены CORS только вне `prod`/`production`/`staging`;
- production-like окружения не получают dev CORS origins по умолчанию;
- seeded runtime содержит только синтетические demo-only данные.

## URL/status

Запущен seeded backend:

- URL: `http://127.0.0.1:8000`
- Process PID: `35280`
- Log stderr: `MVP_EVIDENCE/test-runs/backend-dev-surface-uvicorn.err.log`
- Log stdout: `MVP_EVIDENCE/test-runs/backend-dev-surface-uvicorn.out.log`

Порт проверен через `Get-NetTCPConnection`; слушает `127.0.0.1:8000`.

## Dev-only actor

- Email: `demo.owner@example.test`
- Password: `demo-password-only`
- User ID: `11111111-1111-4111-8111-111111111111`
- Household ID: `22222222-2222-4222-8222-222222222222`
- Personal account ID: `33333333-3333-4333-8333-333333333333`
- Shared account ID: `44444444-4444-4444-8444-444444444444`

Данные синтетические, не являются реальными финансовыми данными. Токены dev-only и выдаются только in-memory seeded runtime.

## Smoke commands/results

Тесты:

```powershell
.\.venv\Scripts\ruff.exe check src/app/main.py src/app/config/settings.py src/app/dev_seed.py tests/test_dev_surface.py
```

Результат: `All checks passed!`

```powershell
.\.venv\Scripts\pytest.exe tests/test_health.py tests/test_dev_surface.py
```

Результат: `5 passed, 1 warning`.

Live HTTP smoke:

- `GET /health`: `200`, body `{"status":"ok"}`
- `OPTIONS /health` with `Origin: http://127.0.0.1:5174`: `200`, `Access-Control-Allow-Origin: http://127.0.0.1:5174`
- `POST /api/v1/sessions`: `201`, `tokenType=Bearer`
- `GET /api/v1/sessions/current`: actor user ID `11111111-1111-4111-8111-111111111111`
- `GET /api/v1/accounts`: `2` items
- `GET /api/v1/categories`: `3` items
- `GET /api/v1/transactions`: `2` items
- `GET /api/v1/reports/summary?...currency=USD`: income `250.0000`, expense `69.7500`

## Blockers/notes for PWA/Android workers

- Use seeded base URL `http://127.0.0.1:8000` for desktop/browser clients.
- Android emulator may need host mapping such as `http://10.0.2.2:8000`; backend is currently bound to `127.0.0.1`, so emulator access may require restart with `--host 0.0.0.0` if local security policy permits.
- Auth routes are currently `include_in_schema=False`, but live endpoints exist at `/api/v1/sessions` and `/api/v1/sessions/current`.
- Standard `app.main:app` remains default-deny for auth; use `app.dev_seed:app` for seeded live integration.
