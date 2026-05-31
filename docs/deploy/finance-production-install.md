# Finance production install without Docker

Scope: Finance only. Do not change RocketFlow routes, services, databases, or
nginx locations. Finance is expected under `/finance/` with backend API under
`/finance-api/`.

## Backend environment

Use `/etc/finance/backend.env` or the service manager equivalent. Keep the
`FINANCE_BACKEND_*` prefix for all backend runtime settings.

```bash
FINANCE_BACKEND_ENVIRONMENT=production
FINANCE_BACKEND_DEBUG=false
FINANCE_BACKEND_DATABASE_URL=postgresql+asyncpg://finance_app:<secret>@127.0.0.1:5432/finance
FINANCE_BACKEND_DATABASE_MIGRATION_POLICY=external
FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE=db
FINANCE_BACKEND_CORS_ALLOWED_ORIGINS='["https://<public-host>"]'
FINANCE_BACKEND_AUTH_TOKEN_HASH_SECRET=<32+ byte secret from secret manager>
FINANCE_BACKEND_AUTH_COOKIE_PATH=/
FINANCE_BACKEND_AUTH_COOKIE_SECURE=true
FINANCE_BACKEND_AUTH_COOKIE_SAMESITE=lax
FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_ENABLED=true
FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_TESSERACT_CMD=/usr/bin/tesseract
FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_LANG=rus+eng
FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_MAX_UPLOAD_BYTES=8388608
FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_MAX_PIXELS=16000000
FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_TIMEOUT_SECONDS=8
```

`psycopg` is required by the sync SQLAlchemy path because
`postgresql+asyncpg` is converted to `postgresql+psycopg` for migrations and
DB-backed runtime helpers.

## Screenshot OCR runtime

PWA/iOS browser screenshot capture uses `POST /api/v1/capture-drafts/screenshot-ocr`
and requires self-hosted Tesseract on the backend host. Android OCR remains
on-device and does not upload screenshots.

Install the OS packages before enabling OCR:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
tesseract --list-langs
```

Expected language output includes `rus` and `eng`. If the binary is outside
`/usr/bin/tesseract`, set `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_TESSERACT_CMD`
to the absolute path.

Operational OCR checks:

- `curl -fsS http://127.0.0.1:8081/health` confirms the backend process, not the
  Tesseract binary.
- A small authenticated PNG/JPEG/WebP request to
  `/finance-api/api/v1/capture-drafts/screenshot-ocr` is the runtime diagnostic
  for OCR availability. `OCR_ENGINE_UNAVAILABLE` means the binary or language
  data is missing; `OCR_DISABLED` means the env flag is off; `OCR_TIMEOUT` means
  the image or host is too slow for the configured timeout.
- The endpoint accepts only PNG/JPEG/WebP, max upload bytes and decoded pixels
  from the `FINANCE_BACKEND_CAPTURE_SCREENSHOT_OCR_*` settings. HEIC and raw
  text/body payloads must be rejected.

Screenshots and raw OCR text are temporary request data only. They must not be
written to application logs, audit, backups, object storage, support artifacts,
or debug dumps. Category mappings store only normalized label hashes; raw labels
are transient request/response values for user confirmation.

If nginx fronts `/finance-api/`, set a body-size limit high enough for the OCR
upload cap and low enough to preserve the backend limit, for example:

```nginx
location /finance-api/ {
    client_max_body_size 8m;
    proxy_pass http://127.0.0.1:8081/;
}
```

## Frontend build

```bash
cd apps/web-pwa
VITE_BASE_PATH=/finance/ VITE_API_BASE_URL=/finance-api npm run build
```

Expected output properties:

- `index.html` references assets under `/finance/`.
- `manifest.webmanifest` has `start_url` and `scope` equal to `/finance/`.
- `manifest.webmanifest` icon URLs point under `/finance/`.
- service worker registration uses `/finance/sw.js` with scope `/finance/`.
- API calls use `/finance-api/api/v1/...`.

## Minimal QA provisioning

Do not run `app.dev_seed` in production or staging. It is process-local,
synthetic, and guarded against production-like environments.

After Alembic migrations are applied externally, create a minimal QA owner:

```bash
cd apps/backend
export FINANCE_BACKEND_PROVISION_PASSWORD='<operator-supplied one-time password>'
python -m app.ops.provision_initial_owner \
  --email qa-owner@example.com \
  --display-name 'Finance QA Owner' \
  --household-name 'Finance QA Household' \
  --confirm-production
unset FINANCE_BACKEND_PROVISION_PASSWORD
```

The command is idempotent for an existing active user and membership. It creates
only auth bootstrap data: user, household, active membership. It does not create
accounts, categories, transactions, imports, reports, or sessions, and it does
not print the password. To intentionally rotate the QA password and revoke active
sessions, rerun with `--rotate-password`.

## Verification

```bash
curl -fsS http://127.0.0.1:8081/health
curl -I http://127.0.0.1/finance/
curl -I http://127.0.0.1/finance/manifest.webmanifest
curl -I http://127.0.0.1/finance/sw.js
curl -I http://127.0.0.1/finance-api/health
```

Browser checks:

- open `/finance/`;
- manifest scope is `/finance/`;
- service worker scope is `/finance/`, not `/`;
- login uses `/finance-api/api/v1/sessions`;
- no request goes to old `/api/` and backend runtime uses only `FINANCE_BACKEND_*`
  configuration names.

Remaining production gate: do not enable/start the service until migrations,
secret injection, backend health, frontend build inspection, and QA login smoke
have passed.
