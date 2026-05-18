# Accounts/Categories Route Subset Freeze

- artifactVersion: 1
- status: frozen for first service slice
- sourceOfTruth: `api/openapi/openapi.yaml`
- relatedPlan: `docs/planning/wave-2-service-slice-plan.md`
- runtimeBaseline: `artifacts/evidence/api/backend-route-inventory.md`
- schemaChange: none

## Scope

The first service slice may mount only the existing `/health` route plus the approved accounts/categories subset under `/api/v1`.

No OpenAPI edits are required for this freeze. Implementation workers must treat the OpenAPI paths below as an allowlist, not as permission to mount adjacent route families.

## Intended mounted subset

Approved subset count: 16 operations.

| # | Method | Mounted path | OpenAPI source path | operationId |
| --- | --- | --- | --- | --- |
| 1 | GET | `/api/v1/accounts` | `/accounts` | `listAccounts` |
| 2 | POST | `/api/v1/accounts` | `/accounts` | `createAccount` |
| 3 | GET | `/api/v1/accounts/autocomplete` | `/accounts/autocomplete` | `autocompleteAccounts` |
| 4 | GET | `/api/v1/accounts/{accountId}` | `/accounts/{accountId}` | `getAccount` |
| 5 | PATCH | `/api/v1/accounts/{accountId}` | `/accounts/{accountId}` | `updateAccount` |
| 6 | DELETE | `/api/v1/accounts/{accountId}` | `/accounts/{accountId}` | `deleteAccount` |
| 7 | POST | `/api/v1/accounts/{accountId}/archive` | `/accounts/{accountId}/archive` | `archiveAccount` |
| 8 | POST | `/api/v1/accounts/{accountId}/restore` | `/accounts/{accountId}/restore` | `restoreAccount` |
| 9 | GET | `/api/v1/categories` | `/categories` | `listCategories` |
| 10 | POST | `/api/v1/categories` | `/categories` | `createCategory` |
| 11 | GET | `/api/v1/categories/autocomplete` | `/categories/autocomplete` | `autocompleteCategories` |
| 12 | GET | `/api/v1/categories/{categoryId}` | `/categories/{categoryId}` | `getCategory` |
| 13 | PATCH | `/api/v1/categories/{categoryId}` | `/categories/{categoryId}` | `updateCategory` |
| 14 | DELETE | `/api/v1/categories/{categoryId}` | `/categories/{categoryId}` | `deleteCategory` |
| 15 | POST | `/api/v1/categories/{categoryId}/archive` | `/categories/{categoryId}/archive` | `archiveCategory` |
| 16 | POST | `/api/v1/categories/{categoryId}/restore` | `/categories/{categoryId}/restore` | `restoreCategory` |

## Expected route inventory after slice

Schema-included runtime routes after this slice must be exactly:

| Method | Path |
| --- | --- |
| GET | `/health` |
| GET | `/api/v1/accounts` |
| POST | `/api/v1/accounts` |
| GET | `/api/v1/accounts/autocomplete` |
| GET | `/api/v1/accounts/{accountId}` |
| PATCH | `/api/v1/accounts/{accountId}` |
| DELETE | `/api/v1/accounts/{accountId}` |
| POST | `/api/v1/accounts/{accountId}/archive` |
| POST | `/api/v1/accounts/{accountId}/restore` |
| GET | `/api/v1/categories` |
| POST | `/api/v1/categories` |
| GET | `/api/v1/categories/autocomplete` |
| GET | `/api/v1/categories/{categoryId}` |
| PATCH | `/api/v1/categories/{categoryId}` |
| DELETE | `/api/v1/categories/{categoryId}` |
| POST | `/api/v1/categories/{categoryId}/archive` |
| POST | `/api/v1/categories/{categoryId}/restore` |

Framework documentation routes such as `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, and `/redoc` may continue to exist as non-schema application routes, but they are not part of the slice API surface.

There must be no mounted `/api/v1` routes outside the 16 approved accounts/categories operations.

## Excluded routes that must remain unmounted

Concrete OpenAPI operations excluded from this slice: 46 operations.

| Class | Method/path inventory | Notes |
| --- | --- | --- |
| Auth placeholder, users, sessions, password resets | `POST /api/v1/users`; `POST /api/v1/sessions`; `DELETE /api/v1/sessions`; `GET /api/v1/sessions/current`; `DELETE /api/v1/sessions/current`; `POST /api/v1/password-resets`; `POST /api/v1/password-resets/confirmations`; `GET /api/v1/users/me`; `PATCH /api/v1/users/me`; `GET /api/v1/users/me/memberships` | Auth boundary worker may add an injectable dependency/default-deny boundary only. It must not mount placeholder login/session routes or issue credentials in this slice. |
| Households | `GET /api/v1/households`; `POST /api/v1/households`; `GET /api/v1/households/{householdId}`; `PATCH /api/v1/households/{householdId}`; `POST /api/v1/households/{householdId}/archive`; `POST /api/v1/households/{householdId}/leave-requests` | Required DB/authz concepts may exist, but public household routes remain unmounted. |
| Invites | `GET /api/v1/households/{householdId}/invites`; `POST /api/v1/households/{householdId}/invites`; `GET /api/v1/invites/{inviteId}`; `POST /api/v1/invites/{inviteId}/accept`; `POST /api/v1/invites/{inviteId}/decline`; `POST /api/v1/invites/{inviteId}/revoke`; `POST /api/v1/invites/{inviteId}/resend` | No invite token or invite lifecycle surface in this slice. |
| Memberships | `GET /api/v1/households/{householdId}/memberships`; `GET /api/v1/memberships/{membershipId}`; `POST /api/v1/memberships/{membershipId}/revoke`; `POST /api/v1/memberships/{membershipId}/leave` | Membership tables/predicates may be used internally; membership APIs remain unmounted. |
| Transactions and transfers | `GET /api/v1/transactions`; `POST /api/v1/transactions`; `GET /api/v1/transactions/autocomplete`; `GET /api/v1/transactions/{transactionId}`; `PATCH /api/v1/transactions/{transactionId}`; `DELETE /api/v1/transactions/{transactionId}`; `POST /api/v1/transactions/{transactionId}/restore`; `POST /api/v1/transactions/{transactionId}/void` | Transfer behavior is excluded because transfers are represented by transaction routes and transfer DTO fields. |
| Reports | `GET /api/v1/reports/summary`; `GET /api/v1/reports/category-breakdown`; `GET /api/v1/reports/account-balances`; `GET /api/v1/reports/cash-flow`; `GET /api/v1/reports/transactions` | No aggregate, drill-down, or hidden-count-adjacent report route may be mounted. |
| Exports and privacy/account lifecycle | `GET /api/v1/exports`; `POST /api/v1/exports`; `GET /api/v1/exports/{exportId}`; `GET /api/v1/exports/{exportId}/files`; `POST /api/v1/users/me/deletion-requests`; `GET /api/v1/users/me/deletion-requests/{deletionRequestId}` | Export, account deletion/deactivation, privacy data flows, and leave-family request APIs remain excluded. |

Additional excluded route families, whether or not currently present in OpenAPI, must remain unmounted:

- `/api/v1/imports`, `/api/v1/import-jobs`, `/api/v1/files/imports`, and any import/upload/raw statement routes.
- `/api/v1/bank-connections`, `/api/v1/bank-accounts`, `/api/v1/bank-api/*`, and any route accepting bank credentials, card numbers, IBANs, SMS codes, or bank API secrets.
- `/api/v1/sms-imports`, `/api/v1/push-imports`, `/api/v1/notifications/push-tokens`, and any SMS/push ingestion or notification token routes.
- `/api/v1/broker-connections`, `/api/v1/external-credentials`, and any broker/external credential route.
- `/api/v1/debug/*`, `/api/v1/support/*`, admin/support bypass routes, or diagnostic routes that expose financial data or authz internals.

## Ownership for next workers

| Worker role | Owns | Must not own |
| --- | --- | --- |
| Migration worker | Minimum DB revisions needed for users, households, memberships, accounts, and categories; migration evidence. | Route mounting, auth placeholder, transactions/reports/transfers/import/export tables unless separately authorized. |
| Auth-boundary worker | Safe authenticated actor dependency/interface, default-deny behavior, test override pattern. | Production auth/session issuance, placeholder auth routes, cookies, bearer/refresh tokens, password reset, invite tokens. |
| Accounts worker | Accounts route module/service/repository/DTO mapping/tests for the 8 approved account operations only. | Categories implementation, route contract QA ownership, excluded route families. |
| Categories worker | Categories route module/service/repository/DTO mapping/tests for the 8 approved category operations only. | Accounts implementation, transaction usage counts, route contract QA ownership, excluded route families. |
| Route-contract QA worker | Runtime route inventory tests comparing mounted paths/methods to this allowlist and proving exclusions stay unmounted. | Feature implementation or broad OpenAPI rewrites. |
| Evidence worker | Fresh test, route inventory, migration, and no-schema-change evidence after implementation. | Changing implementation behavior to make evidence pass. |

## Definition of done for route-contract QA

- Runtime route inventory has `/health` plus exactly the 16 approved `/api/v1/accounts*` and `/api/v1/categories*` operations.
- No excluded OpenAPI operation or additional excluded route family is mounted under `/api/v1`.
- OpenAPI operationIds listed in this document continue to exist unchanged.
- Evidence records no OpenAPI schema change unless a separately approved contract defect is found.

## Go/Hold

Go for implementation workers limited to the approved accounts/categories route subset.

Hold for MVP release.

Hold for production auth/session routes and every excluded route class listed above.
