# Wave 1 pre-flight drift check

## Status

**Go** for W1-01 canonical vocabulary/enums.

Wave 0 remains in a Go state for Wave 1 contracts. P1-01 and P1-02 are closed in product/current-status/domain/access/security/privacy/testing/review documents, and no P0/P1 drift was found across the checked sources.

## Checked documents

- `docs/product-mvp.md`
- `docs/current-status.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/access-model.md`
- `docs/security/security-baseline.md`
- `docs/compliance/privacy-baseline.md`
- `docs/testing/access-security-scenarios.md`
- `docs/architecture/architecture-wave-0-review.md`

## Findings

- **P1-01 closed:** personal data remains private. Personal accounts, operations, categories and aggregates of another family member are not disclosed through lists, reports, search, categories, transfers, API errors, logs or audit.
- **P1-02 closed:** report modes are separated. `shared family report` includes only shared household accounts/operations/categories; `combined viewer overview` includes shared household data plus personal data of the current viewer only.
- MVP scope is consistent: manual account/operation/category entry is in scope; Excel/CSV/file import, bank API, SMS import, push import, bank/broker credentials, tax analytics and investment recommendations are post-MVP/out of scope.
- Personal/shared visibility is consistent: personal belongs to `User` and is owner-only; shared/household data belongs to `Household`/family space and is visible only to active members of that same household.
- Transfer policy is consistent for MVP contracts: personal<->shared transfers are forbidden. Allowed transfers are same-scope only: personal->personal for the same owner and shared->shared within the same household for an active member.
- QA scenarios match report modes: AS-REP-02 and AS-REP-04 cover `shared family report` and `combined viewer overview`; release gate RG-06 requires filtering before aggregation and excludes another member's personal data.

## P0/P1 blockers

- P0: none found.
- P1: none found.
- P1-01: closed.
- P1-02: closed.

## Non-blocking drift and risks

- Canonical vocabulary still needs W1-01 decisions: `Household` vs `FamilySpace`, `Operation` vs `Transaction`, and final membership status enum names such as `left`, `revoked`, `removed`.
- Product wording still lists "transfers" as a general MVP operation type, while access/testing narrow the contract to same-scope transfers and reject personal<->shared. This is non-blocking if W1-01/W1 contracts encode same-scope transfer enums, validation and `TRANSFER_SCOPE_NOT_SUPPORTED`.
- Security/privacy mention split visibility or prohibition for personal<->shared transfers; architecture/access/testing choose prohibition for MVP. This is non-blocking because the safer MVP decision is already reflected in access gates.
- Post-MVP/escalation topics remain outside W1-01 scope: SaaS/self-hosted, jurisdiction, formal privacy policy, retention/deletion SLA, field-level encryption, 2FA/passkeys, production secret manager, bank/API/import integrations, and family roles beyond two active members.
- Design decisions still needed later: balance calculation contract, minimal currency behavior, former-member historical access, and whether custom icons imply file storage/moderation.

## Decision for W1-01

W1-01 can start. The canonical vocabulary/enums work should use the current Wave 0 invariants as fixed inputs:

- `ownershipType`: personal/shared, exactly one per account.
- `reportMode`: `shared_family_report` and `combined_viewer_overview`.
- `sourceType`: `manual` for MVP; import/API sources deferred.
- transfer scope: same-owner personal->personal and same-household shared->shared only; personal<->shared rejected.
- membership: active membership is required for shared visibility; invited/former/revoked users do not see shared data.

Required evidence for W1-01 completion should include traceability from each enum/mode to access predicates and QA release gates, especially RG-03, RG-04 and RG-06.
