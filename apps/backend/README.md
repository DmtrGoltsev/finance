# Backend Workspace

Ownership: backend workers assigned by the orchestrator only.

Expected future contents:

- FastAPI application under `src/app/`.
- Auth, session, CSRF/CORS, and reusable authz predicate modules.
- SQLAlchemy database access aligned with Alembic migrations.
- Pytest unit, integration, contract, and security tests.
- Evidence-producing test commands for API, authz, reports, transfers, privacy, and security gates.

Do not add dependency manifests or production code here until a backend worker receives explicit ownership.

## Minimal Scaffold

This workspace now contains the initial FastAPI scaffold for Wave 2 backend work:

- Python 3.12 package metadata in `pyproject.toml`.
- FastAPI app factory in `src/app/main.py`.
- Operational `/health` endpoint only.
- Empty `/api/v1` router placeholder for future auth and feature modules.
- Pydantic settings with `FINANCE_BACKEND_` environment variable prefix and local-only safe defaults.
- SQLAlchemy async engine/sessionmaker placeholder for PostgreSQL access.
- Basic pytest coverage for app import and health response.

No financial feature endpoints, auth/authz implementation, domain models, migrations, seed data, bank integrations, imports, SMS/push integrations, broker integrations, external credential handling, card data, IBAN/account requisites, or raw statement flows are implemented in this scaffold.

Privacy invariants remain MVP blockers for future endpoints:

- Personal data is owner-only.
- Shared data is visible only to active members of the same `Household`.
- Reports, exports, search, autocomplete, counts, cache materialization, pagination, and aggregation must filter visible rows before returning or aggregating data.
- Hidden resources must use neutral responses and must not expose hidden counts, hidden facets, or diagnostic metadata.
- Logs, audit, telemetry, crash reports, exports, caches, and client state must not disclose hidden financial data or secrets.

## Local Backend Run

From `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

Healthcheck:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The standard `app.main:app` runtime remains default-deny for auth unless real runtime secrets and stores are wired.

## Seeded Dev Surface

For live PWA/Android integration demos only, run the dev-only seeded app:

```powershell
.\.venv\Scripts\uvicorn.exe app.dev_seed:app --host 127.0.0.1 --port 8000 --reload
```

Seed actor:

- Email: `demo.owner@example.test`
- Password: `demo-password-only`
- User ID: `11111111-1111-4111-8111-111111111111`
- Household ID: `22222222-2222-4222-8222-222222222222`

The seeded app uses process-local in-memory stores with synthetic demo-only accounts, categories, transactions, and report data. It refuses to start in `prod`, `production`, or `staging`.

Minimal authenticated smoke:

```powershell
$login = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/sessions `
  -ContentType 'application/json' `
  -Body '{"email":"demo.owner@example.test","password":"demo-password-only","transport":"android_bearer"}'

$headers = @{ Authorization = "Bearer $($login.accessToken)" }
Invoke-RestMethod http://127.0.0.1:8000/api/v1/sessions/current -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/api/v1/accounts -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/reports/summary?reportMode=combined_viewer_overview&householdId=22222222-2222-4222-8222-222222222222&currency=USD" -Headers $headers
```

Local Vite PWA origins `http://127.0.0.1:5174` and `http://127.0.0.1:5173` are allowed by CORS only outside production-like environments. Production-like environments use only explicit `FINANCE_BACKEND_CORS_ALLOWED_ORIGINS`.
