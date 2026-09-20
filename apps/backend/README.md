# Backend Workspace

Ownership: backend workers assigned by the orchestrator only.

Current contents:

- FastAPI application under `src/app/`.
- Auth, session, CSRF/CORS, rate limiting, and reusable authz predicate modules.
- SQLAlchemy database access aligned with Alembic migrations.
- Accounts, categories, transactions, transfers, reports, capture drafts, category OCR mappings, and server-side screenshot OCR runtime.
- Pytest unit, integration, contract, privacy, and security tests.

Production deploy work is outside this workspace README. Keep backend changes
scoped to the assigned feature or fix.

## Implemented Surface

This workspace contains the current FastAPI backend:

- Python 3.12 package metadata in `pyproject.toml`.
- FastAPI app factory in `src/app/main.py`.
- Operational `/health` endpoint and `/api/v1` feature router.
- Pydantic settings with `FINANCE_BACKEND_` environment variable prefix and local-only safe defaults.
- SQLAlchemy database access and Alembic migration alignment.
- Auth/session, account/category, transaction/transfer, report, capture-draft, and screenshot OCR coverage.

No file import/report-preview flow, bank API ingestion, broker API ingestion,
SMS/push import pipeline, SMS/push/notification interception, external
credential handling, card data, IBAN/account requisites, or raw statement flows
are implemented in the MVP backend.

Privacy invariants remain MVP blockers for future endpoints:

- Personal data is owner-only.
- Shared data is visible only to active members of the same `Household`.
- Reports, exports, search, autocomplete, counts, cache materialization, pagination, and aggregation must filter visible rows before returning or aggregating data.
- Hidden resources must use neutral responses and must not expose hidden counts, hidden facets, or diagnostic metadata.
- Logs, audit, telemetry, crash reports, exports, caches, and client state must not disclose hidden financial data or secrets.
- Screenshot OCR external category labels are transient request/response values
  only. Draft and transaction descriptions must stay label-free.

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
When a database URL and `FINANCE_BACKEND_AUTH_TOKEN_HASH_SECRET` are configured,
`POST /api/v1/users` creates an active user and returns the same session response
shape as login. Android bearer registration returns `accessToken`, `tokenType`,
`expiresAt`, and `actor`; PWA cookie registration returns `transport`,
`csrfToken`, `expiresAt`, and `actor`.

## Screenshot OCR Runtime

`POST /api/v1/capture-drafts/screenshot-ocr` uses self-hosted Tesseract via
Pillow/pytesseract. Install the OS Tesseract binary and Russian/English language
packs on hosts that enable the endpoint. The Python test suite fakes the OCR
adapter and does not require the binary.

Debian/Ubuntu package names:

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
tesseract --list-langs
```

Key settings:

- `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_ENABLED`
- `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_TESSERACT_CMD`
- `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_LANG`
- `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_MAX_UPLOAD_BYTES`
- `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_MAX_PIXELS`
- `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_TIMEOUT_SECONDS`

The endpoint accepts temporary PNG/JPEG/WebP uploads only. It does not persist
screenshots or raw OCR text; category mappings store only normalized label hashes.
Raw category labels are transient request/response values for user confirmation
only. Health `/health` proves the backend process is up; an authenticated
`POST /api/v1/capture-drafts/screenshot-ocr` smoke with a small PNG/JPEG/WebP is
the runtime diagnostic for Tesseract availability and language data.

## Production QA Bootstrap

Do not run `app.dev_seed` in production-like environments. For a minimal QA login,
run the idempotent auth-only provisioning command after migrations have completed.
It creates only a user, household, and active membership; it does not create
accounts, categories, transactions, sessions, imports, or reports.

```powershell
$env:FINANCE_BACKEND_PROVISION_PASSWORD = "<operator-supplied one-time password>"
.\.venv\Scripts\python.exe -m app.ops.provision_initial_owner `
  --email qa-owner@example.com `
  --display-name "Finance QA Owner" `
  --household-name "Finance QA Household" `
  --confirm-production
Remove-Item Env:\FINANCE_BACKEND_PROVISION_PASSWORD
```

For production-like environments, the command requires explicit
`FINANCE_BACKEND_DATABASE_URL`, `FINANCE_BACKEND_DATABASE_MIGRATION_POLICY=external`,
DB repository mode, `FINANCE_BACKEND_AUTH_TOKEN_HASH_SECRET`, and
`--confirm-production`. It never prints the password.

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

Minimal registration smoke for DB-backed local runtime:

```powershell
$registration = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/users `
  -ContentType 'application/json' `
  -Body '{"email":"new.owner@example.test","password":"correct horse battery staple","displayName":"New Owner","transport":"android_bearer"}'

$headers = @{ Authorization = "Bearer $($registration.accessToken)" }
Invoke-RestMethod http://127.0.0.1:8000/api/v1/sessions/current -Headers $headers
```

Local Vite PWA origins `http://127.0.0.1:5174` and `http://127.0.0.1:5173` are allowed by CORS only outside production-like environments. Production-like environments use only explicit `FINANCE_BACKEND_CORS_ALLOWED_ORIGINS`.

## Каталог инструментов MOEX

После применения миграции `20260920_0022` таблица `moex_instruments` пуста.
Перед анализом оператор обновляет нужные инструменты из официального MOEX ISS:

```powershell
python -m app.ops.refresh_moex_catalog --secid GAZP --secid SBER
```

Команда запускается из `apps/backend` с установленным backend и обычными настройками
подключения к БД. Для production/staging дополнительно требуется `--confirm-production`.
Команда не должна запускаться в production без разрешения на изменение этого окружения.

- Источник фиксирован: `https://iss.moex.com/iss/securities/{SECID}.json`, раздел `description`.
- За один запуск обновляется от 1 до 500 уникальных SECID. Полная загрузка биржи не нужна.
- В БД сохраняются только проверенные SECID, ISIN и время получения. Обновление пачки атомарно;
  неуспешный запрос не продлевает срок актуальности. Более старое обновление не заменяет новое.
- Срок актуальности записи составляет 24 часа. До его истечения нужно повторить команду
  либо вызвать `refresh_catalog(session, secids)` из доверенного внутреннего процесса.
  Автоматическое расписание в этой доработке не создаётся.
- Неизвестная, неоднозначная, просроченная или несовпадающая пара блокирует создание задания.
  Проверка не обращается в сеть из пользовательского запроса. Ошибка: `INVALID_RECOMMENDATION_PAYLOAD`.
- Если известен только ISIN, сначала нужно определить соответствующий SECID по официальному
  справочнику. Несколько SECID на один ISIN требуют явного выбора SECID.
- Подключение проверяет публичность всех DNS-адресов, закрепляет проверенный IP и проверяет
  TLS-сертификат для `iss.moex.com`. Прокси окружения и редиректы не используются.
  Тайм-аут сетевых операций: 10 секунд, максимальный ответ: 1 МиБ.

Проверка без реальной сети:

```powershell
python -m pytest tests/investments tests/api/test_openapi_mvp_manual_first_contract.py -q
```

Канонический контракт остаётся в `api/openapi/openapi.yaml`. Инвестиционный раздел описывает
реальные входные значения Pydantic: десятичные числа принимаются строкой или числом,
а в ответах сериализуются строкой. Значения по умолчанию политики и денежных остатков сохранены.
Рекурсивный тест `test_openapi_exhaustive.py` сравнивает все достижимые запросы и успешные ответы,
включая вложенные схемы, обязательность, возможность `null`, типы, ограничения, значения
по умолчанию, тело callback и HMAC-заголовки. Аннотации для чтения человеком не сравниваются.
Новая публичная инвестиционная модель также обязана попасть в эту проверку.
Проверка не подменяет runtime-схемы содержимым YAML и не обновляет YAML автоматически.
