# Finance production pipeline gate hardening

Run date: 2026-08-22 (Europe/Moscow)

Branch: `codex/prod-pipeline-gate-hardening-20260822`

Base SHA: `cd69581375be2f40e42771fa6be79d129b32873c`

Implementation SHA: `b043db83ebe7d04e020e42960ff7199a187ff7b8`

Result: **CI-ONLY PASS / PRODUCTION UNCHANGED**

This evidence is sanitized. It contains no SSH host, username, host key,
private key, database URL, password, token, cookie, or financial payload.

## Pipeline contract

- The trigger is restricted to `prod/release-*`.
- `production-package-gate` requires successful input validation plus both
  frontend and backend package jobs.
- Any production action requires a successful read-only `host-preflight` after
  the common package gate.
- Host preflight verifies current symlinks, active service wiring through
  `/opt/finance/current`, `pg_dump`, backup directory writability, at least 1
  GiB free, live Alembic revision lineage, and current release ids.
- Backend deployment must succeed before frontend deployment can start.
- A CI-only dispatch does not request the `production` environment, secrets, or
  host access.

## Local evidence

- workflow YAML parse: PASS;
- `actionlint` 1.7.12: PASS for deploy and rollback workflows;
- production workflow contract tests: 4 passed;
- backend Ruff: PASS;
- backend full suite: 317 passed, 6 skipped;
- backend wheel build: PASS;
- PWA: 69 tests passed and production build PASS;
- Alembic: one head `20260822_0019`; lineage from `20260618_0017` PASS;
- `git diff --check`: PASS.

## GitHub Actions CI-only evidence

Run: `https://github.com/DmtrGoltsev/finance/actions/runs/32576666832`

Exact run SHA: `b043db83ebe7d04e020e42960ff7199a187ff7b8`

- `validate-prod-inputs`: success;
- `prepare-release`: success;
- `frontend-ci-package`: success;
- `backend-ci-package`: success;
- `production-package-gate`: success;
- `host-preflight`: skipped;
- `deploy-backend`: skipped;
- `deploy-frontend`: skipped;
- GitHub deployments for the exact SHA: none.

Artifacts:

- `finance-frontend-ci-only-b043db8`, id `9476725173`, digest
  `sha256:621a1b93e1fd807f5b52c6e80aa43eb50deb14721fddf5f14e2f43b29440b123`;
- `finance-backend-ci-only-b043db8`, id `9476733332`, digest
  `sha256:cb7c4aaa0cb439bceab46f7399dad3c28a0707869961f2cdf100b10a9dcb07bd`.

## Non-results

- No `prod/release-*` branch was created or pushed.
- No production environment job ran.
- No SSH connection, backup, migration, symlink change, service restart, or
  production data mutation occurred.
- Host preflight implementation is statically and contract-tested; a real host
  preflight intentionally requires a separately authorized production action.
