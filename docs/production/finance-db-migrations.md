# Finance production database migrations

Scope: production Alembic migration gate for Finance. The production database is
`finance_prod`. Runtime DB secrets live on the host in `/etc/finance/backend.env`;
they must not be copied into GitHub, workflow inputs, logs, pull requests, or
deployment notes.

## Current workflow behavior

The production CI/CD workflow runs migrations only inside the backend deploy job
and only after the backend artifact is staged and its Python 3.12 virtual
environment is created.

Required inputs:

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
4. Build `/opt/finance/releases/<release-id>/venv`.
5. Install the packaged backend wheel.
6. If `run_migrations=true`, source `/etc/finance/backend.env`.
7. Run `alembic current`.
8. Compare the actual current revision to `expected_current_revision`.
9. Run `alembic upgrade <target_revision>`.
10. Verify `alembic current` equals `target_revision`.
11. Flip `/opt/finance/current` to the release.
12. Restart `finance-backend.service` only when the restart input is explicitly
    enabled and confirmed.
13. Run `/finance-api/health` and `/finance/` health checks.

If any migration check fails, the workflow exits before the backend symlink flip.

## Backup proof

`backup_proof` must identify a real backup artifact, backup run, storage object,
or operations ticket created before the migration run. It is evidence metadata,
not a secret.

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

## Escalation triggers

Stop and escalate when:

- `alembic current` returns a revision other than the expected value
- multiple heads are detected
- backup proof is missing, stale, or cannot be restored by the operator
- the migration contains destructive table/column operations
- auth, session, household membership, ownership scope, money precision, or
  report semantics change
- `/finance-api/health` fails after migration or restart
