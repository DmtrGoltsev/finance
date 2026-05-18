# Seeds and Fixtures README

This directory is reserved for future local/test seed assets. No production seed loader code is created in this planning task.

Canonical fixture actors:

- `owner_a`: Owner A, active in Household AB, owns personal A data.
- `member_b`: Member B, active in Household AB, owns personal B data.
- `other_c`: Other C, outside Household AB and active in Household C.
- `invited_ab`: pending invite to Household AB, no shared financial access.
- `former_ab`: former AB member with `left` or `revoked` membership, own personal access only.

Required fixture groups:

- Households: `hh_ab`, `hh_c`.
- Memberships: active A/B in AB, invited AB, former AB, active C in C.
- Accounts: personal A/B, shared AB, shared C, plus same-currency transfer pairs and optional USD grouping controls.
- Categories: personal A/B, household AB, household C, and null uncategorized transaction coverage.
- Transactions: A personal, B personal, AB shared, C shared, archived/deleted controls.
- Transfers: allowed same-owner personal and same-household shared rows; denied transfer scenarios must not persist successful rows.
- Sessions, password resets, invites, exports, deletion requests, leave/cache invalidation, and audit/outbox controls.

Seed loader expectations:

- Idempotent by fixture label.
- Emits a label-to-id manifest for evidence.
- Uses synthetic data only.
- Stores only hashed tokens/passwords.
- Does not insert real emails, secrets, bank details, raw statements, production config, or external credentials.
- Does not create logs/audit/outbox payloads containing amounts, descriptions, account/category names, token values, or hidden-side diagnostics.

Primary evidence mapping:

- Report fixtures prove `shared_family_report` and `combined_viewer_overview` filter by visible accounts before aggregation.
- Transfer fixtures prove `personal_same_owner`, `household_same_household`, unsupported-scope denial, hidden-side neutrality, atomicity, and concurrency.
- Invited/Former fixtures prove no shared financial access through old ids, sessions, cursors, exports, caches, or offline snapshots.
