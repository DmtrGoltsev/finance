# Database README

This directory contains PostgreSQL database assets for the selected stack:

- PostgreSQL 16
- SQLAlchemy 2.x
- Alembic

Current status: SQLAlchemy/Alembic skeleton only. The declarative metadata lives under
`apps/backend/src/app/db/`, and Alembic is wired to that metadata from `db/migrations/env.py`.
No production migration revision files have been generated yet.

Authoritative implementation plan:

- `docs/architecture/data-model-implementation-plan.md`

Required subdirectories:

- `db/migrations/` for Alembic environment files and future revision files.
- `db/seeds/` for local/test fixture loader planning and future seed assets.

Database invariants to preserve:

- Scoped financial rows use exactly one owner scope: `ownerUserId` for personal or `householdId` for shared/household.
- `ownershipType` and `categoryScope` are immutable in MVP unless a future Product/Security decision changes this.
- Active household access is always resolved through `membershipStatus = active`.
- `sourceType = manual` is the only MVP transaction source.
- Transfers are same-scope only: `personal_same_owner` or `household_same_household`.
- Money is stored as decimal-safe PostgreSQL `numeric`, never floating point.
- Logs, audit, outbox payloads, exports, and cache metadata must not contain hidden financial values or token material.

Operational notes:

- Migrations touching financial/auth/session/membership data require rollback notes and fresh backup evidence before production-like use.
- Restore drills must prove personal ownership and household boundaries remain intact.
- Seed data must be synthetic and must map to Owner A, Member B, Other C, Invited, and Former fixtures.
