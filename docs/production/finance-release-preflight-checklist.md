# Finance release preflight checklist

Scope: read-only production readiness checks before running the Finance
production CI/CD workflow. Do not deploy, migrate, restart services, create
backups, or run authenticated production smoke until the blockers below are
closed and the operator has approval.

## Release set

Include these files in the release commit before expecting GitHub Actions to
show the deploy and rollback workflows:

- `.github/workflows/finance-hexcore-prod-deploy.yml`
- `.github/workflows/finance-prod-rollback.yml`
- `docs/production/finance-cicd-runbook.md`
- `docs/production/finance-db-migrations.md`
- `docs/production/finance-secrets-and-host-key.md`
- `docs/production/finance-release-preflight-checklist.md`

The deploy workflows must remain free of hardcoded production host keys,
private keys, passwords, database URLs, QA passwords, and token values. Pinned
SSH trust must use `StrictHostKeyChecking=yes`.

## GitHub environment gate

Required read-only checks:

```bash
gh workflow list --all
gh api repos/<owner>/<repo>/environments/production \
  --jq '{name: .name, protection_rules: .protection_rules, deployment_branch_policy: .deployment_branch_policy}'
gh secret list --env production
```

Expected result:

- deploy and rollback workflows are visible in `gh workflow list`;
- the `production` environment exists;
- reviewer approval is configured on the environment;
- environment secrets are present by name only:
  - `HEXCORE_PROD_SSH_HOST`
  - `HEXCORE_PROD_SSH_USER`
  - `HEXCORE_PROD_SSH_PRIVATE_KEY`
  - `HEXCORE_PROD_SSH_KNOWN_HOSTS`
  - `HEXCORE_PROD_SSH_PORT`, optional when SSH uses port `22`

Do not print or copy secret values.

## Public health gate

Allowed read-only public checks:

```bash
curl -fsS --max-time 10 http://<public-host>/finance-api/health
curl -sS -o /dev/null -w 'status=%{http_code} content_type=%{content_type}\n' \
  --max-time 10 http://<public-host>/finance/
```

Expected result:

- API health returns HTTP 200 and a non-secret health body;
- frontend returns HTTP 200.

## Host-side read-only gate

Run this only through an approved, pinned SSH path. Do not use
`StrictHostKeyChecking=no`, trust-on-first-use, or ad hoc credentials.

```bash
ssh <pinned-prod-ssh> 'set -euo pipefail
  echo "backend_current=$(readlink -f /opt/finance/current)"
  echo "frontend_current=$(readlink -f /var/www/finance/current)"
  test -L /opt/finance/current
  test -L /var/www/finance/current
  systemctl is-active finance-backend.service
  systemctl show finance-backend.service \
    -p FragmentPath -p ExecStart -p WorkingDirectory -p MainPID --no-pager
'
```

Expected result:

- `/opt/finance/current` is a symlink to a release directory;
- `/var/www/finance/current` is a symlink to a release directory;
- `finance-backend.service` is active;
- service wiring clearly starts the backend from the current release path or an
  approved wrapper that resolves that path.

## Alembic read-only gate

Run only after the host-side read-only gate proves service wiring and only with
host-side environment configuration. The command must not print environment
values.

```bash
ssh <pinned-prod-ssh> 'set -euo pipefail
  release_dir="$(readlink -f /opt/finance/current)"
  test -d "${release_dir}/package/apps/backend"
  test -x "${release_dir}/venv/bin/python"
  test -f /etc/finance/backend.env
  set -a
  . /etc/finance/backend.env
  set +a
  cd "${release_dir}/package/apps/backend"
  "${release_dir}/venv/bin/python" -m alembic -c alembic.ini current
'
```

Expected result:

- output is a concrete current revision;
- if migrations will run, this exact value is used as
  `expected_current_revision`;
- if production is currently at `20260612_0015` and the release includes
  `20260614_0016` and `20260618_0017`, the migration target is the exact
  revision `20260618_0017`, not `head`.

## Backup and restore gate

`backup_proof` must identify a real backup artifact, backup job, storage object,
or operations ticket. A historical backup path is not enough for a fresh
migration gate unless Operations confirms it is the intended current proof.

Minimum read-only evidence:

```bash
ssh <pinned-prod-ssh> 'set -euo pipefail
  find /var/backups/finance -maxdepth 1 -type f -name "finance_prod*.dump" \
    -printf "%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n" | sort | tail -n 5
'
```

Required operator evidence:

- backup completion timestamp;
- backup storage location or ticket id;
- database name, expected to be `finance_prod`;
- retention confirmation;
- restore owner or escalation contact;
- restore drill evidence or explicit approved waiver.

Do not run `pg_dump`, `pg_restore`, backup jobs, restore jobs, or cleanup from
this preflight unless a separate approved runbook and operator approval exist.

## Deploy inputs after approval

When all preflight gates are closed, use the GitHub Actions workflow instead of
manual host commands:

```text
workflow: .github/workflows/finance-hexcore-prod-deploy.yml
deploy_frontend: true or false
deploy_backend: true or false
run_migrations: true only with fresh alembic and backup proof
expected_current_revision: exact fresh host-side revision
target_revision: exact target revision, never head
backup_proof: real backup artifact/ticket id
restart_backend: true only when an approved restart is intended
confirm_production_deploy: finance-production
confirm_backend_restart: finance-backend.service, only when restart_backend=true
environment: production
```
