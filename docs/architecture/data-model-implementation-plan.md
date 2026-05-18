# Data Model, Migrations, and Seeds Implementation Plan

Status: Wave 2 implementation plan for PostgreSQL 16, SQLAlchemy 2.x, and Alembic.

Scope: planning only. This document intentionally does not create production Python code, SQLAlchemy models, or Alembic revision files.

Source documents:

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/access-model.md`
- `docs/architecture/backend-authz-predicates.md`
- `docs/architecture/report-api-contracts.md`
- `docs/architecture/transfer-api-contract.md`
- `docs/testing/wave-2-fixture-evidence-matrix.md`

## Design stance

PostgreSQL stores durable shape, scope, state, audit, session, export, deletion, and cache invalidation facts. Application authz predicates remain the MVP source of visibility decisions. Database constraints make invalid or dangerous shapes hard to persist, but they do not replace deny-by-default backend predicates or release evidence.

Column naming convention:

- Database columns should use snake_case.
- SQLAlchemy/Pydantic/API mapping may expose canonical camelCase names such as `ownerUserId`, `householdId`, `ownershipType`, `categoryScope`, `membershipStatus`, `recordStatus`, `sourceType`, `createdAt`, and `updatedAt`.
- Public ids are UUIDs or opaque strings and must not encode sequence, owner, household, or scope.

Money storage:

- Store financial values as PostgreSQL `numeric`, never `float`, `double precision`, or JSON numbers.
- Recommended MVP storage: `numeric(20,4)` for account balances and transaction amounts, with DTO serialization as decimal strings.
- Enforce positive transaction/transfer amount where applicable; represent income/expense direction by `transaction_type`, not by negative amounts.
- Currency is uppercase ISO 4217 text, checked by shape and by account compatibility rules.

## Table plan

### `users`

Purpose: authenticated product users and account lifecycle.

Key columns:

- `id` UUID primary key.
- `email_normalized` text unique, nullable only if another login identifier is later selected.
- `password_hash` text, Argon2id preferred.
- `display_name` text.
- `auth_status` text: `active`, `deactivated`.
- `record_status` text: `active`, `deleted` for soft lifecycle.
- `session_version` bigint default `1`.
- `created_at`, `updated_at`, `deactivated_at`, `deleted_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Unique index on `email_normalized` where `record_status <> 'deleted'`.
- Check `auth_status in ('active', 'deactivated')`.
- Check `record_status in ('active', 'deleted')`.
- Index `users(auth_status, record_status)`.

Privacy notes:

- User rows are not household-visible by default. API DTOs must expose only minimal profile fields to active household members.
- Email, password hash, security fields, and reset/session state must never appear in shared profile DTOs, logs, or audit details.

### `households`

Purpose: shared family finance scope.

Key columns:

- `id` UUID primary key.
- `name` text.
- `created_by_user_id` UUID foreign key to `users(id)`.
- `status` text: `active`, `archived`.
- `record_status` text: `active`, `deleted`.
- `membership_version` bigint default `1`.
- `created_at`, `updated_at`, `archived_at`, `deleted_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check `status in ('active', 'archived')`.
- Check `record_status in ('active', 'deleted')`.
- Index `households(created_by_user_id)`.
- Index `households(status, record_status)`.

Privacy notes:

- Household existence is visible only through active membership or verified invite context.
- `membership_version` is incremented on invite/membership changes and is part of report/cache/session invalidation.

### `memberships`

Purpose: user participation state in a household.

Key columns:

- `id` UUID primary key.
- `household_id` UUID not null foreign key.
- `user_id` UUID not null foreign key.
- `membership_status` text: `invited`, `active`, `left`, `revoked`.
- `invited_by_user_id` UUID nullable foreign key.
- `invited_at`, `joined_at`, `ended_at`.
- `created_at`, `updated_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check `membership_status in ('invited', 'active', 'left', 'revoked')`.
- Unique partial index: one active membership per `(household_id, user_id)` where `membership_status = 'active'`.
- Partial index for active membership lookup: `(user_id, household_id)` where `membership_status = 'active'`.
- Partial index for household active roster: `(household_id, user_id)` where `membership_status = 'active'`.
- MVP max two active members per household cannot be implemented by a simple CHECK; enforce in service transaction and optionally a deferred constraint trigger.

Privacy notes:

- `active` is the only status that grants shared financial access.
- `invited`, `left`, and `revoked` grant no shared accounts, transactions, reports, exports, search, autocomplete, or cache access.

### `invites`

Purpose: one-time token-bound household invitation lifecycle.

Key columns:

- `id` UUID primary key.
- `household_id` UUID not null foreign key.
- `invited_user_id` UUID nullable foreign key for registered invitees.
- `invited_email_hash` text nullable for email invite lookup without plaintext disclosure.
- `token_hash` text not null unique.
- `invite_status` text: `pending`, `accepted`, `declined`, `revoked`, `expired`.
- `created_by_user_id` UUID not null foreign key.
- `accepted_by_user_id` UUID nullable foreign key.
- `expires_at`, `accepted_at`, `declined_at`, `revoked_at`.
- `created_at`, `updated_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check status enum.
- Unique partial index on `token_hash` where `invite_status = 'pending'`.
- Partial index `(household_id, invite_status)` for pending/revocation lookup.
- Index `(invited_user_id, invite_status)` where `invited_user_id is not null`.

Privacy notes:

- Store invite tokens only as hashes.
- Invite verification can reveal only minimal verified invite context and never shared financial rows before membership is active.

### `accounts`

Purpose: personal and shared money/asset containers.

Key columns:

- `id` UUID primary key.
- `name` text.
- `account_type` text: `cash`, `bank`, `deposit`, `brokerage`.
- `ownership_type` text: `personal`, `shared`.
- `owner_user_id` UUID nullable foreign key; canonical `ownerUserId`.
- `household_id` UUID nullable foreign key; canonical `householdId`.
- `currency` char(3) not null.
- `initial_balance_amount` numeric(20,4) not null default `0`.
- `current_balance_amount` numeric(20,4) nullable if persisted projection is selected.
- `record_status` text: `active`, `archived`, `deleted`.
- `created_by_user_id` UUID not null foreign key.
- `created_at`, `updated_at`, `archived_at`, `deleted_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check `ownership_type in ('personal', 'shared')`.
- Check exactly one owner by scope:
  - personal requires `owner_user_id is not null and household_id is null`;
  - shared requires `household_id is not null and owner_user_id is null`.
- Check `record_status in ('active', 'archived', 'deleted')`.
- Check `currency = upper(currency)` and length 3.
- Index `(owner_user_id, record_status)` for personal lists.
- Index `(household_id, record_status)` for shared lists.
- Composite index `(ownership_type, owner_user_id, record_status)`.
- Composite index `(ownership_type, household_id, record_status)`.
- Changing `ownership_type`, `owner_user_id`, or `household_id` is forbidden in MVP after insert; enforce in service layer and add a DB update trigger before release migration if direct SQL writes are possible.

Privacy notes:

- Account visibility is derived from this table plus active membership.
- Reports must resolve `visibleAccountIds` before aggregation, sorting, pagination, balances, and cache materialization.

### `categories`

Purpose: income/expense categories scoped to a user or household.

Key columns:

- `id` UUID primary key.
- `name` text.
- `category_type` text: `income`, `expense`.
- `category_scope` text: `personal`, `household`; canonical `categoryScope`.
- `owner_user_id` UUID nullable foreign key.
- `household_id` UUID nullable foreign key.
- `icon_key` text nullable for system icon catalog.
- `record_status` text: `active`, `archived`, `deleted`.
- `created_by_user_id` UUID not null foreign key.
- `created_at`, `updated_at`, `archived_at`, `deleted_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check `category_scope in ('personal', 'household')`.
- Check exactly one owner by scope:
  - personal requires `owner_user_id is not null and household_id is null`;
  - household requires `household_id is not null and owner_user_id is null`.
- Check `category_type in ('income', 'expense')`.
- Check `record_status in ('active', 'archived', 'deleted')`.
- Index `(owner_user_id, category_type, record_status)`.
- Index `(household_id, category_type, record_status)`.
- Unique partial index may be added on normalized name per scope for active rows if Product wants name uniqueness; do not use global uniqueness because it leaks/couples scopes.

Privacy notes:

- Personal categories of another user must not appear in category list, autocomplete, report breakdown, usage counts, or transaction validation details.
- Household categories can be used only for the same household shared scope, except explicitly allowed system/null categories.

### `transactions`

Purpose: manual financial events. MVP transfer is represented as a single logical transaction with transfer fields.

Key columns:

- `id` UUID primary key.
- `transaction_type` text: `income`, `expense`, `transfer`, `brokerage`.
- `account_id` UUID not null foreign key.
- `counterparty_account_id` UUID nullable foreign key for `transfer`.
- `category_id` UUID nullable foreign key.
- `amount` numeric(20,4) not null.
- `currency` char(3) not null.
- `occurred_at` timestamptz not null.
- `description` text nullable.
- `source_type` text not null default `manual`; canonical `sourceType`.
- `transfer_scope` text nullable: `personal_same_owner`, `household_same_household`.
- `transfer_status` text nullable: `posted`, `voided`.
- `record_status` text: `active`, `deleted`.
- `created_by_user_id` UUID not null foreign key.
- `last_edited_by_user_id` UUID not null foreign key.
- `created_at`, `updated_at`, `deleted_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check `transaction_type in ('income', 'expense', 'transfer', 'brokerage')`.
- Check `source_type = 'manual'` for MVP.
- Check `amount > 0`.
- Check `currency = upper(currency)` and length 3.
- Check transfer field shape:
  - transfer requires `counterparty_account_id is not null`, `counterparty_account_id <> account_id`, `category_id is null`, `transfer_scope is not null`, and `transfer_status in ('posted', 'voided')`;
  - non-transfer requires `counterparty_account_id is null`, `transfer_scope is null`, `transfer_status is null`;
  - income/expense requires `category_id is not null`.
- Check `record_status in ('active', 'deleted')`.
- Index `(account_id, occurred_at desc, record_status)`.
- Index `(category_id, occurred_at desc)` where `category_id is not null`.
- Index `(counterparty_account_id)` where `counterparty_account_id is not null`.
- Index `(created_by_user_id, occurred_at desc)`.
- Index `(source_type)`.
- Optional text search index only after confirming it is always applied after visible account filtering.

Transfer same-scope check placement:

- Primary placement: backend transaction service uses `canUseTransferScope` after resolving both account rows in a single database transaction and before any write.
- DB placement: add a PostgreSQL constraint trigger on insert/update of transfer fields to verify the two account rows still have same owner/same household scope and same currency. A plain CHECK cannot compare referenced rows.
- Error mapping remains in application code so hidden side details are not exposed.

Privacy notes:

- Transaction visibility inherits from `account_id`.
- Transfer reads must be allowed only when the logical transfer is same-scope and visible to the actor.
- Logs and audit must not include `amount`, `description`, account/category names, raw request/response body, or hidden-side diagnostics.

### `sessions`

Purpose: PWA cookie sessions and Android opaque token session records.

Key columns:

- `id` UUID primary key.
- `user_id` UUID not null foreign key.
- `session_token_hash` text nullable unique.
- `refresh_token_hash` text nullable unique.
- `transport` text: `cookie`, `android_bearer`.
- `session_version` bigint not null.
- `csrf_token_hash` text nullable for cookie sessions.
- `status` text: `active`, `revoked`, `expired`.
- `created_at`, `last_seen_at`, `expires_at`, `revoked_at`.
- `revoked_reason` text nullable.
- `version` bigint default `1`.

Constraints and indexes:

- Check `transport in ('cookie', 'android_bearer')`.
- Check `status in ('active', 'revoked', 'expired')`.
- At least one token hash present.
- Partial index `(user_id, status, expires_at)` where `status = 'active'`.
- Index `(session_version)`.

Privacy notes:

- Store only token hashes.
- Password reset, logout, account deletion/deactivation, and membership loss must revoke or narrow relevant sessions.

### `password_reset_tokens`

Purpose: one-time reset flow.

Key columns:

- `id` UUID primary key.
- `user_id` UUID nullable foreign key to preserve neutral request behavior.
- `email_hash` text not null.
- `token_hash` text not null unique.
- `status` text: `pending`, `used`, `expired`, `revoked`.
- `created_at`, `expires_at`, `used_at`, `revoked_at`.
- `request_ip_hash` text nullable.

Constraints and indexes:

- Check status enum.
- Unique partial index on `token_hash` where `status = 'pending'`.
- Index `(email_hash, status, created_at)`.

Privacy notes:

- Never store or log plaintext reset token.
- Reset request responses remain account-neutral.

### `export_jobs`

Purpose: protected asynchronous export lifecycle.

Key columns:

- `id` UUID primary key.
- `requested_by_user_id` UUID not null foreign key.
- `export_type` text not null.
- `scope_type` text: `personal`, `household`, `combined`.
- `owner_user_id` UUID nullable.
- `household_id` UUID nullable.
- `membership_version_at_request` bigint nullable.
- `status` text: `queued`, `running`, `ready`, `failed`, `expired`, `revoked`.
- `storage_key` text nullable.
- `file_hash` text nullable.
- `ready_at`, `expires_at`, `revoked_at`.
- `created_at`, `updated_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check status enum.
- Check exactly one or valid combined scope:
  - personal export has `owner_user_id = requested_by_user_id` and no household;
  - household export has household and no owner;
  - combined export has both viewer owner and household.
- Partial index `(requested_by_user_id, status, created_at desc)`.
- Index `(household_id, status)` where `household_id is not null`.
- Index `(expires_at)` where `status = 'ready'`.

Privacy notes:

- Export content must be generated from the same visible row predicates as API list/report.
- Former members cannot retain shared data through old export files; membership loss revokes affected ready files.

### `deletion_requests`

Purpose: account deletion/deactivation workflow tracking.

Key columns:

- `id` UUID primary key.
- `requested_by_user_id` UUID not null foreign key.
- `target_user_id` UUID not null foreign key.
- `request_status` text: `pending`, `approved`, `completed`, `cancelled`, `rejected`.
- `requested_at`, `approved_at`, `completed_at`, `cancelled_at`.
- `fresh_auth_at` timestamptz nullable.
- `reason_code` text nullable.
- `created_at`, `updated_at`.
- `version` bigint default `1`.

Constraints and indexes:

- Check `requested_by_user_id = target_user_id` for MVP self-only deletion.
- Check request status enum.
- Index `(target_user_id, request_status, created_at desc)`.

Privacy notes:

- Deletion/deactivation must revoke sessions, exports, and caches.
- Shared history must not reveal deleted user's personal profile/security fields.

### `audit_events`

Purpose: append-only sanitized audit trail.

Key columns:

- `id` UUID primary key.
- `occurred_at` timestamptz not null.
- `actor_user_id` UUID nullable.
- `system_actor` text nullable.
- `action` text not null.
- `target_type` text nullable.
- `target_id` UUID nullable.
- `scope_type` text nullable: `personal`, `household`, `system`.
- `owner_user_id` UUID nullable.
- `household_id` UUID nullable.
- `result` text: `allow`, `deny`, `state-deny`, `error`.
- `request_id` text nullable.
- `reason_code` text nullable.
- `metadata_safe` jsonb not null default `{}`.

Constraints and indexes:

- Check result enum.
- Check scope shape when scope is personal or household.
- Index `(actor_user_id, occurred_at desc)`.
- Index `(scope_type, owner_user_id, occurred_at desc)`.
- Index `(scope_type, household_id, occurred_at desc)`.
- Index `(request_id)`.

Privacy notes:

- Do not store amounts, balances, report totals, descriptions, account/category names, plaintext emails, tokens, token hashes unless strictly needed, secrets, raw financial payloads, stack traces, or SQL text.
- Denied hidden-resource events must not enrich caller-supplied ids with hidden metadata.

### `outbox_events`

Purpose: reliable cache/session/export invalidation and async side effects.

Key columns:

- `id` UUID primary key.
- `event_type` text not null.
- `aggregate_type` text not null.
- `aggregate_id` UUID not null.
- `scope_type` text nullable.
- `owner_user_id` UUID nullable.
- `household_id` UUID nullable.
- `membership_version` bigint nullable.
- `payload_safe` jsonb not null default `{}`.
- `status` text: `pending`, `processing`, `processed`, `failed`, `dead`.
- `created_at`, `available_at`, `processed_at`.
- `attempt_count` integer not null default `0`.

Constraints and indexes:

- Check status enum.
- Index `(status, available_at, created_at)`.
- Index `(event_type, created_at)`.
- Index `(owner_user_id, created_at)` and `(household_id, created_at)` for invalidation tracing.

Privacy notes:

- Use for membership/invite changes, account/category/transaction mutations, export revocation, session revocation, and report/search/cache invalidation.
- Payloads contain ids and versions only, not financial values or user-entered text.

## Cross-table constraints and privacy indexes

Required privacy constraints:

- Every scoped account/category row has exactly one scope owner:
  - personal: `owner_user_id` present, `household_id` absent;
  - shared/household: `household_id` present, `owner_user_id` absent.
- Every transaction has a primary `account_id`; visibility is never derived from `created_by_user_id`.
- Transfer same-scope is enforced by service predicate and DB trigger because it depends on two account rows.
- `ownership_type` cannot change in MVP after account creation.
- `category_scope` cannot change in MVP after category creation unless a future Product/Security decision adds explicit migration semantics.
- `source_type = 'manual'` is the only accepted MVP transaction source.
- Money uses `numeric`, not floating point.

Required lookup indexes:

- `memberships(user_id, household_id)` where active for authz checks.
- `memberships(household_id, user_id)` where active for shared roster checks.
- `accounts(owner_user_id, record_status)` for personal account resolution.
- `accounts(household_id, record_status)` for shared report/list resolution.
- `categories(owner_user_id, category_type, record_status)`.
- `categories(household_id, category_type, record_status)`.
- `transactions(account_id, occurred_at desc, record_status)` for filter-before-aggregate.
- `export_jobs(requested_by_user_id, status, created_at desc)`.
- `outbox_events(status, available_at, created_at)` for invalidation workers.

## Alembic migration sequence

Recommended revision order:

1. `0001_extensions_and_enums`
   - Enable `pgcrypto` if UUID generation is done in DB.
   - Define enum strategy. Prefer text + CHECK constraints for early MVP flexibility unless team commits to PostgreSQL enum migration discipline.
2. `0002_identity_households_memberships_invites`
   - Create `users`, `households`, `memberships`, `invites`.
   - Add active membership indexes and invite token uniqueness.
3. `0003_auth_sessions_reset_tokens`
   - Create `sessions` and `password_reset_tokens`.
   - Add token hash uniqueness and active-session indexes.
4. `0004_financial_scopes_accounts_categories`
   - Create `accounts` and `categories`.
   - Add exactly-one-scope constraints, status checks, and visibility indexes.
5. `0005_transactions_and_transfer_fields`
   - Create `transactions` with `counterparty_account_id`, `transfer_scope`, and `transfer_status`.
   - Add transfer shape checks and transaction indexes.
   - Add DB trigger plan for transfer same-scope if implementation accepts trigger SQL in Alembic.
6. `0006_exports_deletion_audit`
   - Create `export_jobs`, `deletion_requests`, and `audit_events`.
7. `0007_outbox_invalidation`
   - Create `outbox_events`.
   - Wire initial event types for membership, invite, session, export, account, category, and transaction invalidation.
8. `0008_immutability_triggers`
   - Add DB triggers for no `ownership_type`/scope mutation and optional no `category_scope` mutation.
   - Add transfer same-scope trigger if not included in `0005`.
9. `0009_seed_fixture_support_indexes`
   - Add any non-production helper indexes needed for stable fixture lookup by synthetic labels only if those labels live in seed-only metadata tables. Do not add production columns solely for tests without team approval.

Rollback and backup notes:

- Migrations touching auth, sessions, membership, accounts, categories, transactions, transfers, exports, deletion, audit, or outbox require rollback notes in the Alembic revision message.
- Before production-like application, capture an encrypted PostgreSQL backup and record evidence under `artifacts/evidence/backups/`.
- Restore drill must verify that personal ownership and household boundaries survive restore.
- Destructive rollback of tables containing financial/session/audit data is not acceptable in production. Prefer forward-fix migrations after backup.
- Trigger migrations must include downgrade behavior and proof that disabled triggers cannot leave invalid transfer or ownership rows.
- Any migration changing `numeric` precision/scale, transfer shape, active membership indexes, or visibility scope columns is P0/P1-sensitive and requires explicit QA/security evidence.

## Seed and fixture loader mapping

The seed loader should live under `db/seeds/` and must remain distinct from production app code. It should insert synthetic data only into local/test databases and should be idempotent by fixture label.

Canonical actors:

| Fixture label | User role | Required state |
| --- | --- | --- |
| `owner_a` | Owner A | active user, active member of `hh_ab`, owns personal A data |
| `member_b` | Member B | active user, active member of `hh_ab`, owns personal B data |
| `other_c` | Other C | active user outside `hh_ab`, active in `hh_c` |
| `invited_ab` | Invited | active user or invite recipient with `invited` membership/invite to `hh_ab`, no financial access |
| `former_ab` | Former | active user with `left` or `revoked` membership in `hh_ab`, own personal data only |

Required graph mapping:

- Households: `hh_ab`, `hh_c`.
- Memberships: `mem_a_ab_active`, `mem_b_ab_active`, `mem_invited_ab_invited`, `mem_former_ab_left`, `mem_c_c_active`.
- Accounts:
  - A personal: `acc_a_cash`, `acc_a_savings`, `acc_a_usd`.
  - B personal: `acc_b_cash`, `acc_b_savings`.
  - AB shared: `acc_ab_cash`, `acc_ab_savings`, `acc_ab_usd`.
  - C shared: `acc_c_shared`, `acc_c_shared_2`.
- Categories:
  - A personal: `cat_a_income`, `cat_a_food`.
  - B personal: `cat_b_income`, `cat_b_food`.
  - AB household: `cat_ab_groceries`, `cat_ab_salary`.
  - C household: `cat_c_foreign`.
  - Uncategorized is represented by `category_id = null`, not a real cross-scope category row.
- Transactions:
  - A personal income/expense.
  - B personal income/expense.
  - AB shared income/expense and uncategorized expense.
  - C foreign shared expense.
  - Archived/deleted or voided controls.
- Transfers:
  - Allowed: `trf_a_personal_same_owner`, `trf_b_personal_same_owner`, `trf_ab_shared_same_household_by_a`, `trf_ab_shared_same_household_by_b`.
  - Denied probes are scenario inputs and should not create persisted successful rows: personal-to-shared, shared-to-personal, cross-user personal, cross-household shared, invited shared, former restore, missing counterparty, visible cross-currency.
- Sessions: active sessions for A, B, C, Invited, Former plus revoked/expired/reset variants.
- Invites: pending, accepted, declined, revoked, expired, resend variants with token hashes only.
- Exports/deletion/leave/cache fixtures: create enough rows to prove former export denial, old export revocation, self-only deletion request, and cache invalidation outbox events.

Seed evidence requirements:

- Fixture metadata must preserve stable labels for evidence.
- Synthetic ids may vary, but output manifests must map labels to ids.
- No real emails, passwords, bank details, tokens, secrets, production config, raw statements, or external credentials.
- Passwords and tokens in fixtures must be synthetic and hashed where stored.
- Seeded logs/audit must be sanitized and must not contain amounts, descriptions, account/category names, or token values.

## P0/P1 data risks

P0 risks:

- Personal rows can leak if `owner_user_id`/`household_id` exactly-one-scope constraints are missing or bypassed.
- Report aggregation can leak if `transactions` are aggregated before `visibleAccountIds` filtering.
- Transfer can leak or corrupt balances if same-scope validation is only UI-side, if a hidden counterparty gives different errors, or if one side is written without the other.
- Invited or Former users can regain shared access through stale sessions, report/export caches, old cursors, or old export files.
- Logs/audit/outbox payloads can leak amounts, descriptions, account/category names, emails, tokens, or hidden-side diagnostics.
- Floating point money storage can corrupt financial values and break auditability.

P1 risks:

- MVP max two active household members requires transactional service validation or a trigger; a plain unique index is insufficient.
- Exact rate limits and export TTL remain Product/Security decisions; table columns support enforcement but do not close the decision.
- Persisted `current_balance_amount` is optional and, if selected, requires atomic transaction/update/void/restore handling and concurrency tests.
- PostgreSQL enum vs text CHECK choice affects later migration complexity.
- DB RLS is not the MVP authz source; any later RLS adoption must be defense-in-depth and must not reduce predicate tests.
- Seed fixture labels must not bleed into production schema unless a clear test-only mechanism is chosen.

## Definition of done for implementation

- Alembic migrations create the tables, constraints, indexes, and triggers described above.
- SQLAlchemy models preserve canonical scope/state/version fields and do not accept client-supplied owner/scope values as authority.
- Backend predicates use active membership and owner filters consistently for list, detail, search, autocomplete, report, export, debug-like surfaces, and cache materialization.
- Fixture loader creates Owner A, Member B, Other C, Invited, Former graph and emits a label-to-id manifest.
- Tests prove exactly-one-scope constraints, active membership lookup, immutable ownership, sourceType manual-only, decimal money storage, transfer same-scope, no partial writes, and filter-before-aggregate.
- Backup/restore evidence proves personal ownership and household separation after restore.
