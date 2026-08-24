# Finance production database migrations

Scope: production Alembic migration gate for Finance. The production database is
`finance_prod`. Runtime DB secrets live on the host in `/etc/finance/backend.env`;
they must not be copied into GitHub, workflow inputs, logs, pull requests, or
deployment notes.

## Current workflow behavior

The production CI/CD workflow runs migrations only inside the backend deploy job
and only after the backend artifact is staged and a backend virtual environment
is created with a host Python interpreter that satisfies the backend package
requirement, currently Python `>=3.12`.

For release branch pushes, the workflow:

- deploys the backend path automatically;
- reads the current production revision with `alembic current`;
- derives the target revision from the staged release's single `alembic heads`
  result;
- creates a host-side `pg_dump --format=custom` backup under
  `/opt/finance/backups/postgres`;
- writes `.sha256` and `.evidence.txt` files next to the backup dump;
- runs `alembic upgrade <derived-target-revision>`;
- restarts `finance-backend.service`.

For `workflow_dispatch`, required inputs are still:

- `deploy_backend=true`
- `run_migrations=true`
- `expected_current_revision=<exact current revision>`
- `target_revision=<exact target revision>`
- `backup_proof=<backup artifact id or ticket>`
- `confirm_production_deploy=finance-production`

Required approval:

- GitHub `production` environment approval

The workflow refuses `target_revision=head`; use an exact revision such as
`20260612_0015`.

## Host-side configuration

The workflow sources:

```text
/etc/finance/backend.env
```

The env file must provide production runtime settings, including
`FINANCE_BACKEND_DATABASE_URL`, without printing values. Alembic loads the DB URL
through backend settings in `db/migrations/env.py`.

Do not add DB DSNs, database passwords, auth token secrets, cookie secrets, or
operator one-time passwords to GitHub secrets for this workflow.

## Gate sequence

The backend deploy job performs this sequence:

1. Download and verify the backend artifact checksum.
2. Copy the artifact to the host using pinned SSH host-key verification.
3. Extract to `/opt/finance/releases/<release-id>`.
4. Inspect host Python runtime availability without logging secrets, then build
   `/opt/finance/releases/<release-id>/venv` with the first compatible
   configured candidate.
5. Install the packaged backend wheel.
6. Create the stable `bin/finance-backend` service wrapper for the release.
7. If `run_migrations=true`, source `/etc/finance/backend.env`.
8. Run `alembic current`.
9. For release branch pushes, derive the target from a single `alembic heads`
   result; for manual dispatch, use the exact `target_revision` input.
10. Compare the actual current revision to the expected value. On release branch
   push, the expected value is the production revision just read by the
   workflow; on manual dispatch, it is the exact operator input.
11. For release branch pushes, create automatic backup evidence before upgrade.
12. Run `alembic upgrade <target_revision>`.
13. Verify `alembic current` equals `target_revision`.
14. Flip `/opt/finance/current` to the release.
15. Restart `finance-backend.service` automatically for release branch pushes,
    or only when the manual restart input is explicitly enabled and confirmed.
16. Run `/finance-api/health` and `/finance/` health checks.

If any migration check fails, the workflow exits before the backend symlink flip.

## Backup proof

For manual dispatch, `backup_proof` must identify a real backup artifact, backup
run, storage object, or operations ticket created before the migration run. It is
evidence metadata, not a secret.

For release branch pushes, no `backup_proof` input exists. The workflow creates
the backup itself on HexCore before Alembic upgrade. It reads the production DB
URL from `/etc/finance/backend.env`, converts it to `pg_dump` environment
variables and a temporary `.pgpass` file, and removes that temporary file after
the dump. The workflow logs only backup path, SHA256, and evidence path.

Minimum operator evidence:

- backup completion timestamp
- backup storage location or ticket id
- database name, expected to be `finance_prod`
- restore owner or escalation contact
- retention confirmation

## Rollback policy

Database rollback is disabled in the GitHub rollback workflow. The rollback
workflow only flips frontend/backend symlinks.

Prefer forward fixes once financial, auth, session, report, or audit-adjacent
data exists. A destructive or reverse database operation requires a separate
explicit approval path, DBA/operator ownership, restore evidence, and a written
impact assessment.

## Operator preflight

Before enabling `run_migrations=true`, confirm:

- the target revision file is present in the backend artifact
- migration tests passed in CI
- `expected_current_revision` is from a fresh host-side check
- backup proof exists and is not a placeholder
- the migration does not require a coordinated app outage beyond the planned
  backend restart
- the service can read `/etc/finance/backend.env`
- the staged release is the release intended for the migration

For release branch push migrations, also confirm `pg_dump` is installed on
HexCore and the deploy user can create `/opt/finance/backups/postgres`.

## Escalation triggers

Stop and escalate when:

- `alembic current` returns a revision other than the expected value
- multiple heads are detected
- manual backup proof is missing, stale, or cannot be restored by the operator
- automatic release-push backup creation or checksum creation fails
- the migration contains destructive table/column operations
- auth, session, household membership, ownership scope, money precision, or
  report semantics change
- `/finance-api/health` fails after migration or restart
