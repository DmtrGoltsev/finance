# Finance production CI/CD runbook

Scope: Finance only. Do not change RocketFlow routes, services, databases, or
nginx locations from this runbook.

Live production facts used by the workflow design:

- backend service: `finance-backend.service`
- frontend nginx path: `/finance/ -> /var/www/finance/current/`
- backend nginx path: `/finance-api/ -> 127.0.0.1:8081/`
- current backend release observed before this CI/CD design:
  `/opt/finance/releases/20260612T045020Z-26b487d6`
- production database: `finance_prod`
- backend env file: `/etc/finance/backend.env`

## Workflows

Primary workflow:

- `.github/workflows/finance-hexcore-prod-deploy.yml`
- `push` to branch names containing `release`: CI, tests, builds, packaging,
  artifact upload, production frontend/backend deploy, automatic pre-migration
  DB backup evidence, Alembic upgrade to the single repository head, backend
  restart, and health checks.
- `workflow_dispatch`: same CI/package lanes, plus optional approved production
  deploy actions controlled by explicit inputs, exact migration revisions,
  operator backup proof, restart confirmation, and the GitHub `production`
  environment.

Rollback workflow:

- `.github/workflows/finance-prod-rollback.yml`
- manual only
- flips existing frontend and/or backend release symlinks
- never runs database rollback

## CI lanes

Frontend lane:

- uses Node.js 22
- runs `npm ci`
- runs `npm test`
- builds `apps/web-pwa` with `VITE_BASE_PATH=/finance/` and
  `VITE_API_BASE_URL=/finance-api`
- verifies `index.html`, `manifest.webmanifest`, `/finance/`, and `/finance-api`
  references
- packages a tar artifact containing `dist/`, `frontend.sha256`, and
  `release-manifest.txt`

Backend lane:

- uses Python 3.12
- installs `apps/backend[dev]`
- runs `ruff` against backend source/tests and `db/migrations`
- runs `pytest`
- builds a wheel
- packages a tar artifact containing the backend wheel, backend source,
  `alembic.ini`, `pyproject.toml`, and `db/migrations`
- includes `backend.sha256` and `release-manifest.txt`

## Release ids

If `release_id` is empty, the workflow generates:

```text
YYYYMMDDTHHMMSSZ-<8-char-git-sha>
```

Custom release ids may contain only letters, numbers, dot, underscore, and dash.

## Frontend deploy

Manual inputs:

- `deploy_frontend=true`
- `confirm_production_deploy=finance-production`

Required GitHub environment:

- `production`

Remote model:

- releases live under `/var/www/finance/releases/<release-id>`
- `/var/www/finance/current` must be a symlink
- deploy extracts the artifact into a new release directory
- deploy atomically flips `/var/www/finance/current` to the new release
- deploy refuses to overwrite a non-symlink `current` directory

Post-deploy checks run on the host with a retry window:

```bash
curl -fsS --max-time 10 http://127.0.0.1/finance/
curl -fsS --max-time 10 http://127.0.0.1/finance-api/health
```

## Backend deploy

Release branch push behavior:

- deploys the backend artifact
- derives the current Alembic revision from production
- derives the target revision from the staged release's single Alembic head
- creates a production DB backup under `/opt/finance/backups/postgres`
- writes backup evidence next to the dump without logging DB passwords
- runs `alembic upgrade <derived-target-revision>`
- restarts `finance-backend.service`

Manual inputs:

- `deploy_backend=true`
- `confirm_production_deploy=finance-production`
- `restart_backend=true` only when the operator intentionally wants a service
  restart
- `confirm_backend_restart=finance-backend.service` when restart is requested

Required GitHub environment:

- `production`

Remote model:

- releases live under `/opt/finance/releases/<release-id>`
- `/opt/finance/current` must be a symlink
- deploy extracts the backend artifact into the new release directory
- deploy inspects `python3.12`, `python3.11`, `python3`, and the current
  backend venv Python without logging secrets
- deploy creates `/opt/finance/releases/<release-id>/venv` from the first
  configured backend Python candidate that can create a venv and satisfies the
  backend package requirement, currently Python `>=3.12`
- deploy installs the packaged backend wheel into that virtual environment
- deploy atomically flips `/opt/finance/current` to the new release
- deploy refuses to overwrite a non-symlink `current` directory
- `systemctl restart finance-backend.service` runs only when both the restart
  input and confirmation input are present

Post-deploy checks run on the host with a retry window:

```bash
curl -fsS --max-time 10 http://127.0.0.1/finance-api/health
curl -fsS --max-time 10 http://127.0.0.1/finance/
```

## Migration gate

Migrations are part of the backend deploy path. They are disabled by default for
`workflow_dispatch` and enabled for release branch pushes. See
`docs/production/finance-db-migrations.md`.

For `workflow_dispatch`, the workflow runs Alembic only when all are true:

- `deploy_backend=true`
- `run_migrations=true`
- `expected_current_revision` is set to the exact current revision
- `target_revision` is set to the exact target revision, not `head`
- `backup_proof` identifies a real backup artifact or ticket
- `confirm_production_deploy=finance-production`
- the GitHub `production` environment is approved

The workflow sources `/etc/finance/backend.env` on the host for DB configuration.
No database password or DSN is stored in GitHub workflow inputs or repository
files.

For release branch pushes, `run_migrations=true` is resolved by the workflow.
The current revision is read from production, the target revision is read from
the staged release's single Alembic head, and a `pg_dump --format=custom` backup
plus `.sha256` and `.evidence.txt` files are created before Alembic upgrade.

## Rollback

Use `.github/workflows/finance-prod-rollback.yml`.

Frontend rollback inputs:

- `component=frontend` or `component=both`
- `frontend_release_id=<existing release id>`
- `confirm_rollback=finance-production-rollback`

Backend rollback inputs:

- `component=backend` or `component=both`
- `backend_release_id=<existing release id>`
- `restart_backend=true` when the backend process should be restarted
- `confirm_backend_restart=finance-backend.service` when restart is requested
- `confirm_rollback=finance-production-rollback`

Rollback flips only symlinks to existing release directories and then runs the
same local health checks. Database rollback is intentionally not automated.

## Definition of done

- CI lanes pass.
- Frontend and backend artifacts exist with checksums and manifests.
- Pinned SSH known hosts are configured through `HEXCORE_PROD_SSH_KNOWN_HOSTS`.
- Production deploy jobs require explicit manual inputs and `production`
  environment approval for `workflow_dispatch`; release branch pushes require
  the `production` environment and run the deploy path automatically.
- Manual migrations require exact revision inputs and backup evidence; release
  push migrations create backup evidence automatically before upgrade.
- Backend restart is gated by an explicit restart input and service-name
  confirmation.
- Post-deploy health checks pass for `/finance/` and `/finance-api/health`.
- Rollback workflow can point frontend/backend symlinks back to a known existing
  release without database changes.

## Required evidence

For a production deploy record, retain:

- GitHub run URL
- commit SHA
- release id
- frontend artifact checksum
- backend artifact checksum
- production environment approval
- migration input values, if migrations were run
- manual backup proof or automatic backup evidence, if migrations were run
- post-deploy health check result
- rollback candidate release ids

Do not copy secret values into evidence.

## Risks and escalation triggers

Escalate before continuing when:

- `/var/www/finance/current` or `/opt/finance/current` exists and is not a
  symlink
- the pinned host key does not match
- the current Alembic revision differs from `expected_current_revision`
- backup proof is missing or ambiguous
- release-push automatic backup creation fails
- `/finance-api/health` fails after a backend deploy or restart
- `/finance/` serves stale or missing assets after a frontend deploy
- the backend service does not actually consume `/opt/finance/current`
- an operator requests database rollback
