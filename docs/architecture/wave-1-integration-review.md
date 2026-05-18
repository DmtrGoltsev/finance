# Wave 1 integration review

## Executive summary

Recommendation: **Go for implementation planning / Hold for MVP release until evidence gates pass**.

Wave 1 architecture documents are consistent with the MVP product invariants:

- MVP is manual-entry only: no import, bank API, SMS, push, bank credentials, broker credentials, or external financial-source dependencies.
- `personal` remains private: accounts, transactions, categories, balances, aggregates, free text, reports, exports, placeholders, hidden counts, logs, audit, cache and errors must not disclose another household member's personal data.
- Report modes are explicit and correct: `shared_family_report` uses only shared household rows; `combined_viewer_overview` uses shared household rows plus personal rows of `viewerUserId == currentUserId`.
- Reports require filter-before-aggregate: visible account/category/transaction scope is resolved before `COUNT`, `SUM`, `GROUP BY`, balances, trends, facets, pagination, drill-down, export, cache or materialization.
- Transfers are same-scope only: `personal_same_owner` and `household_same_household`; personal<->shared, cross-user personal and cross-household shared transfers are rejected.
- Neutral errors and no-hidden-count rules are consistently carried through backend, report, transfer, client and QA contracts.

No open P0/P1 architecture drift was found. The package is ready to hand off to implementation planning, but not to release implementation without the required test, review, log, cache, backup, secret and traceability evidence.

## Reviewed docs

- `docs/product-mvp.md`
- `docs/current-status.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/access-model.md`
- `docs/security/security-baseline.md`
- `docs/compliance/privacy-baseline.md`
- `docs/testing/access-security-scenarios.md`
- `docs/architecture/architecture-wave-0-review.md`
- `docs/architecture/wave-1-preflight-drift-check.md`
- `docs/architecture/canonical-api-vocabulary.md`
- `docs/architecture/backend-api-contracts.md`
- `docs/architecture/backend-authz-predicates.md`
- `docs/architecture/report-api-contracts.md`
- `docs/architecture/transfer-api-contract.md`
- `docs/security/security-release-checklist.md`
- `docs/compliance/privacy-flows-mvp.md`
- `docs/architecture/client-state-contracts.md`
- `docs/testing/qa-endpoint-traceability.md`

## Consistency findings

- **Canonical vocabulary:** Wave 1 chooses `Household`, `Transaction`, `Membership`, `Invite`, `Report`, `TransactionType`, `OwnershipType`, `CategoryScope`, `ReportMode`, `TransferScope`, `RecordStatus` and `SourceType`. Wave 0 synonyms such as `FamilySpace`, `Operation`, `shared family report`, `combined viewer overview` and `removed` are mapped to canonical API terms.
- **API/authz consistency:** Backend contracts and predicates use deny-by-default, server-side `currentUserId`, active membership for shared scope, owner-only personal scope, neutral direct-id/reference errors and equivalent list/detail/search/autocomplete/report/export predicates.
- **Report consistency:** `report-api-contracts.md`, `backend-api-contracts.md`, `backend-authz-predicates.md`, `client-state-contracts.md` and QA traceability all require the same two report modes, the same visible-account resolution and the same no-other-member-personal rule.
- **Transfer consistency:** Access, backend, authz, transfer, client and QA docs agree that same-owner personal transfers and same-household shared transfers are allowed, while personal<->shared, cross-user personal and cross-household shared transfers are denied with safe canonical behavior.
- **Security/privacy consistency:** Security and privacy baselines, release checklist and privacy flows align on auth/session/reset/invite controls, active-membership gating, export visible-at-generation scope, delete-self-only behavior, former-member shared-access denial by default, logging minimization and secret/backup evidence.
- **Client consistency:** Android/PWA state contracts mirror backend rules: no foreign-personal placeholders, hidden counts, member financial badges, cross-viewer `combined_viewer_overview` cache reuse, stale shared snapshots after leave/revoke, or forbidden transfer/report options.
- **QA consistency:** `access-security-scenarios.md` and `qa-endpoint-traceability.md` connect AS/NEG/SEC/PRIV scenarios, RG-01..RG-12, report gates, transfer gates and privacy gates to endpoint surfaces and required evidence.

## Conflicts/drift

- **No P0/P1 drift found.**
- Security/privacy Wave 0 language still mentions "split visibility or prohibition" for personal<->shared transfers. Wave 1 resolves this by choosing prohibition for MVP; any split-visibility design is post-MVP/escalation.
- A few prose references still use legacy labels such as "shared family report" and "combined viewer overview". This is non-blocking because canonical API values are defined as `shared_family_report` and `combined_viewer_overview`, and legacy labels are explicitly mapped.
- Product text still describes "transfers" as an MVP operation type in general terms. The API/authz/QA contract narrows this to same-scope transfers only, which is safe and now explicit.
- Security-baseline acceptance wording about `personal -> shared` not revealing personal details should be treated as historical split-visibility context, not as permission to implement mixed-scope transfers in MVP.

## P0/P1 blockers

- **P0:** none found in the reviewed architecture/package.
- **P1:** none found in the reviewed architecture/package.
- **Closed P1-01:** personal-only visibility is confirmed as an MVP invariant.
- **Closed P1-02:** report modes are separated and canonicalized.

Release classification remains strict: any implementation that leaks another member's personal data, aggregates before access filtering, permits personal<->shared transfer without approved split visibility, exposes hidden counts, skips neutral errors, or bypasses authz/cache invalidation becomes a P0/P1 release blocker under the release checklist.

## Non-blocking risks

- Report cache or materialized report design can leak viewer personal rows if `combined_viewer_overview` is keyed only by `householdId`.
- Category breakdowns, search facets, sorting, min/max balances or usage counters can leak hidden personal data if computed before visible-row filtering.
- Client empty/error copy can accidentally imply hidden data exists.
- PWA service worker, Android local storage, back stack, cursors or offline snapshots can retain shared data after membership leave/revoke.
- Export/delete/leave family semantics remain sensitive and require product/privacy signoff before public launch.
- Former-member historical shared access is denied by default; any product change here needs Product/Security/Privacy escalation.
- Public launch, SaaS/self-hosted commitment, jurisdiction, formal privacy policy, retention SLA, support/admin tooling, roles beyond two active members and import/bank integrations remain out of current MVP scope.

## Evidence gaps

Required before MVP release:

- Automated API/security test output for AS-*, NEG-*, SEC-* and PRIV-* scenarios using Owner A, Member B, Other C, Invited and Former fixtures.
- RG-01..RG-12 evidence, including RG-03/RG-04 transfer checks and RG-06 report filter-before-aggregate checks.
- Report evidence: `visibleAccountIds` proof before aggregation, both report modes tested, no hidden counts/facets snapshots, drill-down/detail equivalence, cache key and invalidation proof.
- Transfer evidence: TR-RG-01..10, hidden-side golden errors, same-scope allow, unsupported-scope deny, atomicity/concurrency and log safety.
- Authz evidence mapping endpoint surfaces to predicates for accounts, transactions, categories, reports, transfers, exports, households, memberships and invites.
- Client evidence: Android/PWA snapshots for no hidden placeholders/counts, neutral errors, forbidden report/transfer options and cache/offline cleanup after logout/leave/revoke.
- Security evidence: auth/session/reset/invite/rate-limit tests, CSRF/CORS evidence, secret scans, dependency/SBOM checks, sanitized log/audit samples, encrypted backup/restore proof and tenant-boundary restore verification.
- Privacy evidence: export diff against visible lists/reports, former-member export exclusion, delete-self-only proof, leave-family invalidation and protected export file lifecycle.
- Out-of-scope evidence: route/schema/config/source scan proving imports, bank API, SMS/push, bank credentials and external financial-source storage are absent or rejected.

## Go/Hold recommendation

**Go** to implementation planning for backend API, authz predicates, report implementation, transfer implementation, client state planning and QA automation.

**Hold** for MVP release until all required evidence is collected and all P0/P1 release gates are closed. Engineering cannot waive public-launch privacy/legal gates alone.

## Required next wave tasks

1. Create implementation tickets from canonical contracts, preserving `Household`, `Transaction`, `reportMode`, `ownershipType`, `scope`, `sourceType = manual` and canonical error codes.
2. Implement backend authz predicates as reusable server-side gates for list/detail/search/autocomplete/report/export, with deny-by-default behavior.
3. Implement Report API around a shared `visibleAccountIds` resolver and prove filter-before-aggregate in code review and integration tests.
4. Implement Transfer API as `transactionType = transfer`, allowing only `personal_same_owner` and `household_same_household`.
5. Build neutral error/golden response tests for missing vs inaccessible ids, hidden counterparty, hidden category/account filters and former/invited member access.
6. Design cache/session invalidation for membership changes, logout, password reset, invite accept/revoke, account/category/transaction mutations and report/export caches.
7. Build client state tests for Android/PWA selectors, empty/error states, offline cache, back stack and report/transfer mode visibility.
8. Wire QA traceability so every endpoint surface has mapped predicates, scenarios, release gates and evidence artifacts.
9. Run security/privacy release evidence collection early: logs, audit, secrets, backups, restore, dependency scan, export/delete/leave flows and out-of-scope route/schema scans.

## Handoff to implementation planning

Implementation planning should treat these as fixed invariants:

- personal data is owner-only and never disclosed to another household member, directly or indirectly;
- shared data is visible only to active members of the same `Household`;
- `shared_family_report` is shared-only;
- `combined_viewer_overview` is shared household plus current viewer personal only;
- every aggregate/export/cache/report/drill-down filters visible rows before computation;
- same-scope transfers only;
- missing and inaccessible resources use neutral response shapes;
- no hidden counts, hidden facets, "partially hidden" messages or foreign-personal placeholders;
- any deviation requires Product/Security/Privacy escalation before implementation continues.

Definition of done for Wave 1 integration review is met: all listed inputs were checked, P0/P1 status is explicit, Go/Hold is explicit, residual risks and evidence gaps are explicit, and next-wave handoff is ready for implementation planning.
