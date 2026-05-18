# Alembic Migrations README

This directory contains the Alembic environment skeleton for the SQLAlchemy metadata in
`apps/backend/src/app/db/`. Revision files should be generated or written under
`db/migrations/versions/` only when a migration task is explicitly approved.

Current approved revisions:

- `20260517_0001_accounts_categories_slice.py`: first service-slice prerequisites only.
  Creates `users`, `households`, `memberships`, `accounts`, and `categories`.
  It intentionally excludes transactions, reports, transfers, exports, password-reset,
  audit, outbox, and invite tables.
- `20260518_0002_auth_sessions.py`: hash-only auth/session persistence.
  Creates `sessions` for revocable bearer/PWA session records. It intentionally excludes
  password-reset tokens, audit events, refresh rotation endpoints, and logout-all hooks.
- `20260518_0003_accounts_categories_immutable_scope_triggers.py`: PostgreSQL guard
  triggers for immutable account ownership scope and category scope.

Recommended migration sequence:

1. Extensions and enum/check strategy.
2. Identity, households, memberships, invites.
3. Sessions and password reset tokens.
4. Accounts and categories with exactly-one-scope constraints.
5. Transactions with MVP transfer fields.
6. Export jobs, deletion requests, audit events.
7. Outbox events for cache/session/export invalidation.
8. Immutability and transfer same-scope triggers.
9. Seed/fixture support indexes only if approved.

Migration safety rules:

- Include downgrade/rollback notes in every revision that touches auth, membership, financial, export, deletion, audit, or outbox tables.
- Take an encrypted backup before production-like migration runs.
- Prefer forward fixes over destructive rollback once financial/session/audit data exists.
- Verify restore preserves `ownerUserId`, `householdId`, `ownershipType`, `categoryScope`, `membershipStatus`, `recordStatus`, `sourceType`, `version`, `createdAt`, and `updatedAt` semantics.
- Do not rely on DB constraints alone for authorization; backend predicates remain mandatory.
- Keep PostgreSQL trigger coverage in Alembic migration tests; SQLite metadata tests do not
  execute trigger bodies.

P0/P1 migration risks:

- Missing scope constraints can leak personal/shared data.
- Transfer same-scope validation cannot be a simple CHECK and needs service validation plus trigger or equivalent DB guard.
- Active membership indexes are security-critical for consistent authz behavior.
- Money precision/scale changes require explicit data migration and report/export regression evidence.
