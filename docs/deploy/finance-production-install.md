# Finance production install without Docker

Scope: Finance only. Do not change RocketFlow routes, services, databases, or
nginx locations. Finance is expected under `/finance/` with backend API under
`/finance-api/`.

## Release deployment

GitHub Actions is the primary production CI/CD path. The workflow is
`.github/workflows/finance-hexcore-prod-deploy.yml`.

An explicit push by repository owner `DmtrGoltsev` to `prod/release-*` is the
production authorization and runs the CI/package/deploy path:

- frontend: Node.js 22, `npm ci`, `npm test`, production PWA build, artifact
  checksum, and manifest;
- backend: Python 3.12, `apps/backend[dev]`, `ruff`, `pytest`, wheel build,
  migration-inclusive artifact, checksum, and manifest.

Manual `workflow_dispatch` remains available and is gated by explicit inputs
and the GitHub `production` environment. Under the approved Finance solo-owner
waiver, the environment has no Required reviewer; selected deployment branches
allow only `prod/release-*`. Frontend releases deploy to
`/var/www/finance/releases/<release-id>` and atomically flip
`/var/www/finance/current`. Backend releases deploy to
`/opt/finance/releases/<release-id>` and atomically flip `/opt/finance/current`.

Required GitHub secrets are `HEXCORE_PROD_SSH_HOST`, `HEXCORE_PROD_SSH_USER`,
`HEXCORE_PROD_SSH_PRIVATE_KEY`, and `HEXCORE_PROD_SSH_KNOWN_HOSTS`.
`HEXCORE_PROD_SSH_PORT` is optional and defaults to `22` when unset. Workflows
use pinned host-key verification with `StrictHostKeyChecking=yes`; do not use
`StrictHostKeyChecking=no` or trust-on-first-use host keys for production.

For manual dispatch, backend migrations are disabled by default. A production
Alembic upgrade runs only when `deploy_backend=true`, `run_migrations=true`,
exact revision inputs, backup proof, production confirmation, and owner
authorization are all present. Release-branch pushes derive the current and
target revisions and create backup evidence automatically before upgrade.
The workflow sources `/etc/finance/backend.env` on the host; DB secrets are not
stored in GitHub.

Backend restart is disabled by default and requires `restart_backend=true`,
`confirm_backend_restart=finance-backend.service`, and environment approval.

Manual rollback is available in
`.github/workflows/finance-prod-rollback.yml`; it flips frontend/backend
symlinks to existing release directories and does not perform DB rollback.

Runbooks:

- `docs/production/finance-cicd-runbook.md`
- `docs/production/finance-db-migrations.md`
- `docs/production/finance-secrets-and-host-key.md`

Direct SSH/SCP upload, installation, migration, restart, or release switching on
HexCore is prohibited, including as an emergency fallback. Restore GitHub
Actions or use the approved rollback workflow. SSH/SCP may run only from the
approved workflows with `StrictHostKeyChecking=yes` and the pinned environment
host key.

## Backend environment

Use `/etc/finance/backend.env` or the service manager equivalent. Keep the
`FINANCE_BACKEND_*` prefix for all backend runtime settings.

```bash
FINANCE_BACKEND_ENVIRONMENT=production
FINANCE_BACKEND_DEBUG=false
FINANCE_BACKEND_DATABASE_URL='<host-side production DSN from secret manager>'
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

Remaining production gate: do not enable/start/restart the service until
migrations, secret injection, backend health, frontend build inspection, and QA
login smoke have passed. In CI/CD, `finance-backend.service` restart is allowed
only through the explicit restart input, service-name confirmation, and the
GitHub `production` environment. The solo-owner waiver removes only the reviewer
click and does not relax these controls.
