# Wave 2 implementation plan

Дата: 2026-05-17  
Роль автора: delegated subagent-planner  
Статус: implementation planning artifact, не исполнительская реализация

## 1. Executive decision

**Класс сложности:** high / высокий.

Обоснование: Wave 2 переводит контрактный пакет Wave 1 в план поставки финансового MVP с приватными personal-данными, shared household-данными, двумя report modes, same-scope transfers, export/delete/leave privacy flows и release evidence. Это не xhigh на уровне планирования, потому что платежей, bank credentials, SMS/push/imports и public launch в MVP нет. Но отдельные worker-задачи по authz, reports, transfers, privacy release gates, backups/restore и logs/secrets должны получать xhigh, если затрагивают критичные данные, release blockers или повторные failures.

**Go/Hold для запуска worker wave:**

- **Go** для ограниченной Wave 2 worker wave: stack decision, repo layout, implementation tickets, test fixture design, OpenAPI/backend contract skeleton, authz predicate design, QA evidence harness planning.
- **Hold** для полноценной feature implementation wave до закрытия P1 planning blocker: выбранный стек, repo layout, auth/session strategy, DB/migration approach, test runner и ownership-директории не зафиксированы в reviewed docs.
- **Hold** для MVP release до прохождения evidence gates из security/privacy/QA checklist.

## 2. Inputs treated as source of truth

План основан на:

- `docs/product-mvp.md`
- `docs/current-status.md`
- `docs/architecture/wave-1-integration-review.md`
- `docs/architecture/canonical-api-vocabulary.md`
- `docs/architecture/backend-api-contracts.md`
- `docs/architecture/backend-authz-predicates.md`
- `docs/architecture/report-api-contracts.md`
- `docs/architecture/transfer-api-contract.md`
- `docs/security/security-release-checklist.md`
- `docs/compliance/privacy-flows-mvp.md`
- `docs/architecture/client-state-contracts.md`
- `docs/testing/qa-endpoint-traceability.md`

Fixed invariants for all Wave 2 workers:

- MVP is manual-entry only; no import/API/SMS/push/bank credentials.
- Personal accounts, transactions, categories, aggregates, exports, reports, logs and errors are owner-only.
- Shared data is visible only to active members of the same `Household`.
- `shared_family_report` includes only shared household rows.
- `combined_viewer_overview` includes shared household rows plus current viewer personal rows only.
- Reports, exports, search, autocomplete, pagination, cache and materialization filter visible rows before aggregation/count/sort/facet.
- Transfers are same-scope only: `personal_same_owner` and `household_same_household`; personal<->shared is denied.
- Missing and inaccessible resources use neutral user-facing responses.
- No hidden counts, hidden facets, hidden placeholders, foreign personal badges or "partially hidden" copy.

## 3. P0/P1 blockers

### P0 blockers

None found in Wave 1 architecture package for starting implementation planning.

Any worker finding direct or indirect leakage of another member's personal data, aggregation before visible filtering, unsupported transfer allow, stale former-member shared access, token/secret/plaintext credential leakage, unsafe logs, missing restore capability, or out-of-scope import/bank/SMS/push surface must stop and escalate as P0.

### P1 planning blockers

**P1-B01: implementation stack and repo layout are not selected.**

The reviewed docs intentionally do not choose backend framework, DB, migration tool, auth/session transport, PWA stack, Android stack, test runner, secret manager, deployment target, backup mechanism or exact directory structure. Worker agents must not invent this silently.

Safe next decision variants:

- **Variant A: API/backend-first closed MVP.** Choose backend framework, DB, migration/test stack, auth/session strategy, OpenAPI generation and contract tests first; deliver PWA/Android after stable API predicates.
- **Variant B: PWA-first with backend contract skeleton.** Choose a web/PWA stack and backend stack together; implement PWA against generated/openapi client and test doubles while backend predicates land.
- **Variant C: monorepo contract-first.** Choose repo layout with shared OpenAPI/schema/test fixtures and separate backend, PWA and Android workspaces; start with generated DTOs and shared QA fixtures.

Required decision record before broad implementation:

- backend language/framework and ORM/query strategy;
- database and migration tooling;
- auth/session model for PWA and Android, including CSRF/CORS strategy;
- test runners for unit, API integration, security, client snapshots and mobile/PWA cache tests;
- OpenAPI/schema source of truth location;
- secret/config and backup/restore approach for closed MVP;
- repo ownership map and CI evidence artifact locations.

**P1-B02: exact rate limit values and export file TTL are not fixed.**

Contracts require rate limits for login/register/reset/invite and short-lived protected export files. Workers may implement configurable defaults only after Product/Security approval, and must produce test evidence.

**P1-B03: deletion/retention/backups/public-launch policy is not legally finalized.**

Closed MVP can implement safe engineering defaults. Public release, SaaS/self-hosted commitment, jurisdiction, formal retention/deletion SLA, backup deletion promise and shared history ownership require Product/Legal/Security/Operations signoff.

## 4. Wave 2 task list

| ID | Task | Recommended role | Reasoning level | Reasoning rationale | Ownership |
| --- | --- | --- | --- | --- | --- |
| W2-00 | Stack and repo layout decision record | Tech lead / architect | high | Cross-cutting decision; prevents conflicting worker edits | `docs/architecture/decision-records/`, repo root config docs only |
| W2-01 | Implementation ticket decomposition from Wave 1 contracts | Delivery planner | high | Converts contracts into isolated worker backlog and evidence gates | `docs/planning/`, issue/backlog artifacts only |
| W2-02 | Canonical OpenAPI/schema skeleton | Backend API architect | high | Wire names/enums/errors must remain canonical | `api/`, `openapi/`, `schemas/` after stack decision |
| W2-03 | Data model and migrations plan | Backend data engineer | high | Ownership/scope fields affect every authz predicate | `db/`, `migrations/`, `docs/architecture/data-model-*` |
| W2-04 | Auth/session/reset/invite foundation | Security backend engineer | xhigh | Sessions, tokens, rate limits, CSRF/CORS and neutral auth errors are release blockers | backend auth/session modules only |
| W2-05 | Reusable authz predicate layer | Security backend engineer | xhigh | Central privacy boundary for list/detail/search/report/export/debug | backend access/authz modules and tests only |
| W2-06 | Household, membership and invite flows | Backend feature engineer | high | Active membership controls shared visibility and cache invalidation | backend household/invite/membership modules |
| W2-07 | Accounts and categories implementation | Backend feature engineer | high | Personal/shared scope and category usage can leak data | backend account/category modules |
| W2-08 | Transactions income/expense/brokerage implementation | Backend feature engineer | high | Inherits account scope; referenced-id neutrality required | backend transaction modules excluding transfer-specific code |
| W2-09 | Transfer implementation | Backend feature engineer + security reviewer | xhigh | Same-scope validation, hidden-side neutrality, atomicity and concurrency are release gates | backend transfer/transaction modules, balance/projection tests |
| W2-10 | Report implementation | Backend/report engineer + security reviewer | xhigh | Filter-before-aggregate, drill-down equivalence and cache keys are P0-sensitive | backend report modules and report tests |
| W2-11 | Export/delete/leave privacy flows | Privacy backend engineer | xhigh | Export scope, former-member denial and deletion semantics are privacy release gates | backend export/privacy/account-deletion/leave modules |
| W2-12 | Cache/session invalidation design and implementation | Platform/security engineer | xhigh | Former-member stale access is a P0 risk | backend cache/session modules; client cache contracts |
| W2-13 | PWA state implementation | Frontend/PWA engineer | high | Client must not expose hidden placeholders/counts or stale shared snapshots | PWA app directory only |
| W2-14 | Android state implementation | Android engineer | high | Same privacy state model, local storage and back stack cleanup | Android app directory only |
| W2-15 | QA fixture and automated API/security test harness | QA automation engineer | high | All RG/TR/PF gates need repeatable evidence | `tests/`, `qa/fixtures/`, evidence output dirs |
| W2-16 | Client snapshot/cache/offline tests | QA client engineer | high | UI copy/cache can leak hidden data | PWA/Android test dirs only |
| W2-17 | Logs/audit/secret/dependency evidence | Security QA / DevSecOps | xhigh | Required release evidence for tokens, logs, secrets, CVEs | `security/`, `ci/`, evidence dirs; no product code unless agreed |
| W2-18 | Backup/restore and tenant-boundary evidence | Operations engineer | xhigh | Restore failure or unsafe backup blocks release | ops/deployment/backup docs and evidence dirs |
| W2-19 | Integration review after implementation wave | Integration reviewer | high | Must verify no drift, no missing gates, no ownership conflicts | `docs/architecture/wave-2-integration-review.md` |

## 5. Dependencies

Hard sequence dependencies:

1. W2-00 must precede code implementation tasks W2-02..W2-18.
2. W2-01 can start after this plan and should be updated after W2-00.
3. W2-02 and W2-03 precede most backend feature implementation.
4. W2-04 and W2-05 precede or gate W2-06..W2-12.
5. W2-06 precedes reliable shared account/report/export/leave behavior.
6. W2-07 precedes W2-08, W2-09 and W2-10 for account/category references.
7. W2-08 precedes W2-09 transfer lifecycle and W2-10 report drill-down.
8. W2-10 depends on W2-05, W2-07, W2-08 and W2-09 for transfer report safety.
9. W2-11 depends on W2-05, W2-06, W2-07, W2-08 and W2-10 for export equivalence.
10. W2-12 depends on W2-04, W2-05 and W2-06, then gates W2-10, W2-11, W2-13 and W2-14.
11. W2-13 and W2-14 depend on W2-02 API schemas and should not invent endpoint behavior.
12. W2-15 starts early with fixtures, then expands as endpoints land.
13. W2-17 and W2-18 can start planning early, but release evidence is final only after implementation and deployment config exist.
14. W2-19 runs after worker implementation and evidence collection.

Parallelizable groups:

- W2-00 and W2-01 can run in parallel if one owner writes the final decision record and the other writes tickets.
- After W2-00, W2-02, W2-03, W2-15, W2-17 planning and W2-18 planning can run in parallel.
- After W2-04/W2-05 skeletons exist, W2-06, W2-07 and QA fixture expansion can run in parallel with strict module ownership.
- W2-13 and W2-14 can run in parallel after schema/client contracts exist.
- W2-16 can run in parallel with W2-13/W2-14 after state names and test hooks are agreed.

Sequential or review-gated tasks:

- W2-05 authz predicate layer must be reviewed before financial endpoint workers merge.
- W2-09 transfer and W2-10 report require security review before integration.
- W2-11 privacy flows require Product/Security/Privacy review before release evidence is considered valid.
- W2-12 cache/session invalidation must be proven before former-member, report/export and client cache gates close.
- W2-19 integration review must happen after evidence, not before.

## 6. Ownership rules for limited subagents

Until W2-00 fixes the real repo layout, use conceptual ownership and avoid touching shared files outside assigned boundaries.

Worker boundaries:

- **Backend API worker:** OpenAPI/schema and API route/controller files only; no authz predicate implementation unless explicitly assigned.
- **Authz worker:** central predicate/access layer and its tests only; no feature route business logic except adapter hooks.
- **Data/migration worker:** schema/migrations/seed fixtures only; no API handlers.
- **Feature workers:** own module plus module-specific tests; no global auth/session/cache changes.
- **Report worker:** report resolver/aggregation/cache code and report tests; no account/transaction mutation code.
- **Transfer worker:** transfer validation/lifecycle/balance atomicity tests; no report aggregation except transfer-specific fixtures.
- **Client workers:** PWA or Android directories only; no backend contract edits except generated clients from approved schema.
- **QA worker:** tests/fixtures/evidence harness only; no production code changes unless orchestrator explicitly escalates a testability hook.
- **Security evidence worker:** CI/security scan/log/audit evidence artifacts only; no feature behavior changes.
- **Ops worker:** deployment/backup/restore docs/config only; no app code.

Shared-file protocol:

- Canonical docs under `docs/architecture/*contracts*.md`, `docs/security/*`, `docs/compliance/*`, and `docs/testing/*` are read-only for implementation workers unless the orchestrator assigns a documentation-update task.
- Any change to API names/enums/errors, report modes, transfer scope or personal/shared visibility requires architect/security/privacy escalation.
- Generated files must have one owner per generator. Workers should not hand-edit generated DTO/client code.
- Test fixture names and actor matrix must be centrally owned by QA to avoid drift.

## 7. Definition of Done for Wave 2

Wave 2 implementation planning is done when:

- P1-B01 stack/repo decision is recorded or the worker wave remains explicitly limited to planning/skeleton work.
- Implementation backlog maps every endpoint surface to owner, predicates, tests and evidence.
- OpenAPI/schema source of truth uses canonical names and values: `Household`, `Transaction`, `reportMode`, `ownershipType`, `scope`, `sourceType = manual`.
- Authz predicates are assigned as reusable server-side gates for list/detail/search/autocomplete/report/export/debug-like paths.
- Report work is planned around one `visibleAccountIds` resolver and filter-before-aggregate proof.
- Transfer work is planned around same-scope allow, unsupported-scope deny, hidden-side neutrality and atomic writes.
- Client work is planned around Android/PWA shared state contracts, no hidden placeholders/counts, neutral errors and cache/offline cleanup.
- QA has fixture matrix for Owner A, Member B, Other C, Invited and Former with personal/shared/foreign data.
- Evidence plan covers RG-01..RG-12, TR-RG-01..10 and PF-RG-01..12.
- Security evidence plan covers auth/session/reset/invite/rate limits, CSRF/CORS, logs/audit, secrets, dependencies, out-of-scope scans, backups and restore.
- Release remains Hold until all P0/P1 gates have concrete passing evidence.

## 8. Required evidence by workstream

Backend/API:

- OpenAPI or equivalent schema diff proving canonical routes, DTO fields, enum values and error codes.
- Route inventory proving no import, bank API, SMS/push, broker/external credentials or raw statement endpoints.
- `sourceType = manual` accepted and post-MVP source types rejected in create/update flows.

Auth/session/security:

- Automated tests for registration/login/reset neutral responses.
- Session revocation tests for logout, logout all, password reset, leave/revoke and account deactivation.
- Rate-limit evidence for login, registration, reset, invite/resend.
- CSRF/CORS config and negative tests if cookie auth is selected.

Authz/financial data:

- A/B/C/Invited/Former matrix for accounts, transactions and categories across list/detail/search/autocomplete.
- Missing vs inaccessible golden responses.
- Predicate equivalence: detail rows match list/search/autocomplete/report/export visibility.

Reports:

- `visibleAccountIds` proof before aggregation.
- Both report modes tested for A and B.
- No hidden counts/facets/schema snapshots.
- Drill-down detail equivalence.
- Report cache key and invalidation evidence.

Transfers:

- TR-RG-01..10 evidence.
- Golden responses for personal<->shared, cross-user personal and cross-household shared denials.
- Atomicity and concurrency tests proving no partial writes or half-applied balances.
- Log/audit scan for hidden-side safety.

Privacy:

- Export diff against visible lists/reports.
- Former-member export exclusion and old export file invalidation.
- Delete/deactivate self-only and no personal data exposure to remaining member.
- Leave-family invalidation for sessions, access caches, reports, exports, search/autocomplete, client snapshots and cursors.
- Export file protected storage and TTL evidence.

Client:

- Android and PWA snapshots for no foreign-personal placeholders, hidden counts, member financial badges or forbidden report/transfer options.
- Logout/session-expired/back-stack cleanup proof.
- Leave/revoke/offline snapshot cleanup proof.
- `combined_viewer_overview` cache cannot be reused across viewers.

Security/Ops:

- Log/audit samples or scans showing no amounts, balances, descriptions, account/category names, plaintext tokens, passwords, secrets or raw financial payloads.
- Secret scan for repo, bundles/images and docs.
- Dependency/SBOM scan with no unaccepted critical/high auth/crypto/session/parser/ORM/web framework CVEs.
- Encrypted backup proof, isolated backup access, restore test on separate environment and tenant-boundary verification.

## 9. Risks and escalation triggers

Primary implementation risks:

- Report joins or aggregates before resolving visible accounts.
- `combined_viewer_overview` cache keyed only by `householdId`.
- Transfer hidden counterparty leaks through error details, logs, timing or validation diagnostics.
- Transfer balance/projection updates are not atomic.
- Search/autocomplete exposes hidden matches, facets, min/max, counts or cursor metadata.
- Former member retains shared data through stale sessions, report/export cache, offline snapshots or old cursors.
- Client empty/error copy implies hidden data exists.
- Debug/support/internal jobs bypass predicates or log raw payloads.
- Out-of-scope import/bank/SMS/push/broker credential surfaces appear.

Escalate immediately if:

- product asks to show another member's personal account, transaction, category, report, aggregate, balance, export or free text;
- product asks to allow personal<->shared, cross-user personal or cross-household shared transfer;
- former members need historical shared access;
- family model expands beyond two active members or introduces roles/children/delegated access;
- support/admin/debug tooling needs financial values or hidden data;
- public launch, SaaS/self-hosted, jurisdiction, formal retention/deletion SLA, backup deletion promise, 2FA/passkeys or production secret manager becomes part of MVP;
- restore fails, backup boundaries are unsafe, or tenant separation after restore is not proven;
- repeated QA failures occur in authz predicates, report aggregation, transfer atomicity/neutrality, cache invalidation, logs or privacy flows.

## 10. Recommended execution order

1. W2-00: choose stack, repo layout, auth/session strategy, DB/migrations, test runners, evidence artifact paths.
2. W2-01: create implementation backlog with isolated ownership and evidence gates.
3. W2-02 + W2-03 + W2-15: create schema/data/test-fixture foundations in parallel.
4. W2-04 + W2-05: implement auth/session and reusable authz predicates before financial features.
5. W2-06 + W2-07: household/membership/invite, accounts and categories.
6. W2-08: base transactions and referenced-id neutrality.
7. W2-09: transfers with atomicity/concurrency and hidden-side evidence.
8. W2-10: reports with `visibleAccountIds` and filter-before-aggregate evidence.
9. W2-11 + W2-12: export/delete/leave privacy flows and cache/session invalidation.
10. W2-13 + W2-14 + W2-16: PWA/Android state, cache/offline and snapshots.
11. W2-17 + W2-18: logs/secrets/dependency/backup/restore evidence.
12. W2-19: integration review and Go/Hold release decision.

## 11. First 5 tasks for the orchestrator

1. Assign W2-00 to an architect with high reasoning and explicit output: stack/repo/auth/DB/test/evidence decision record.
2. Assign W2-01 to a delivery planner with high reasoning to turn this plan into limited, non-overlapping worker tickets.
3. Assign W2-15 to QA automation with high reasoning to create the A/B/C/Invited/Former fixture and evidence matrix before feature code.
4. Assign W2-02 to API/backend architecture with high reasoning after W2-00 starts, limited to canonical schema/OpenAPI skeleton.
5. Assign W2-05 to security backend with xhigh reasoning after W2-00/W2-02 boundaries are clear, limited to reusable predicates and predicate tests.
