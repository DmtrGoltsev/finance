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
```

`psycopg` is required by the sync SQLAlchemy path because
`postgresql+asyncpg` is converted to `postgresql+psycopg` for migrations and
DB-backed runtime helpers.

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
