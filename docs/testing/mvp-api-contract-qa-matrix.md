# MVP API contract QA matrix

Дата: 2026-05-18

## Статус

OpenAPI `api/openapi/openapi.yaml` синхронизирован с фактически смонтированной closed-MVP runtime surface. Контракт больше не публикует post-MVP routes как клиентское ожидание: registration/profile, households, invites, memberships, exports, deletion requests, standalone transfers, logout-all и explicit transaction void отсутствуют в `paths`.

## Смонтированная контрактная поверхность

| Область | Routes | QA expectation |
| --- | --- | --- |
| Sessions | `POST /api/v1/sessions`, `GET /api/v1/sessions/current`, `DELETE /api/v1/sessions/current` | Только login/current/logout-current. `DELETE /api/v1/sessions` не публикуется до безопасного logout-all/revocation-all. |
| Accounts | `GET/POST /api/v1/accounts`, `GET/PATCH/DELETE /api/v1/accounts/{accountId}`, `POST /api/v1/accounts/{accountId}/archive`, `POST /api/v1/accounts/{accountId}/restore`, `GET /api/v1/accounts/autocomplete` | Personal owner-only, shared active-household-member only, no hidden counts. |
| Categories | `GET/POST /api/v1/categories`, `GET/PATCH/DELETE /api/v1/categories/{categoryId}`, `POST /api/v1/categories/{categoryId}/archive`, `POST /api/v1/categories/{categoryId}/restore`, `GET /api/v1/categories/autocomplete` | Personal categories owner-only; household categories active-member only. |
| Transactions | `GET/POST /api/v1/transactions`, `GET/PATCH/DELETE /api/v1/transactions/{transactionId}`, `POST /api/v1/transactions/{transactionId}/restore`, `GET /api/v1/transactions/autocomplete` | Transaction visibility inherits account visibility; referenced ids rejected safely. `DELETE` is the implemented soft-delete/void-equivalent path for transfers. |
| Transfers | `transactionType=transfer` through `/api/v1/transactions*` only | Same-scope transfers only: `personal_same_owner`, `household_same_household`. No `/api/v1/transfers`; no `/api/v1/transactions/{transactionId}/void`. |
| Reports | `GET /api/v1/reports/summary`, `category-breakdown`, `account-balances`, `cash-flow`, `transactions` | Exactly two modes: `shared_family_report`, `combined_viewer_overview`; filter visible rows before aggregation and before drill-down pagination. |
| Error envelope | Canonical top-level `error` with `code`, `message`, `requestId`, optional safe `details` | Missing and inaccessible resources remain neutral and must not expose object names, amounts, owners, stack traces, SQL or raw payloads. |

## Исключено из mounted MVP

| Family | Excluded routes/examples |
| --- | --- |
| Users/profile/privacy | `/api/v1/users`, `/api/v1/users/me`, `/api/v1/users/me/deletion-requests*` |
| Password reset/logout-all | `/api/v1/password-resets*`, `DELETE /api/v1/sessions` |
| Households/invites/memberships | `/api/v1/households*`, `/api/v1/invites*`, `/api/v1/memberships*` |
| Transfers standalone/void | `/api/v1/transfers*`, `/api/v1/transactions/{transactionId}/void` |
| Exports | `/api/v1/exports*` |
| Imports/files/bank/full SMS/push/broker | `/api/v1/imports*`, `/api/v1/import-jobs*`, `/api/v1/files/imports*`, `/api/v1/bank-*`, `/api/v1/sms-imports*`, `/api/v1/push-imports*`, `/api/v1/broker-connections*`, `/api/v1/external-credentials*`, `/api/v1/notifications/push-tokens*` |
| Debug/support bypass | User-facing debug/support routes that bypass visible-scope predicates and redaction |

Reserved post-MVP `sourceType` vocabulary such as `file_import`, `bank_api`, `sms` and `push` remains rejected by direct transaction create/update flows. Capture drafts must use a separate user-confirmed lifecycle: user-initiated OCR from a selected screenshot, Android on-device OCR without screenshot upload, PWA/iOS browser temporary upload to self-hosted backend OCR, no SMS/push/notification interception, no persistent screenshot/raw OCR/raw SMS/push/notification body server-side storage, structured draft with `idempotencyKey`/`evidenceHash`, and transaction creation only after user confirm/edit.

## Contract guards

| Guard | Evidence target |
| --- | --- |
| Exact OpenAPI path set | `apps/backend/tests/api/test_openapi_mvp_manual_first_contract.py` asserts the mounted MVP `paths` set exactly. |
| Runtime route inventory | `apps/backend/tests/api/test_accounts_categories_route_contract.py` and `test_w3_ttr_contract_guards.py` assert mounted runtime routes and excluded route families. |
| Enum boundaries | `SourceType=manual`, two `ReportMode` values, and two same-scope `TransferScope` values are test-guarded. |
| Report mode semantics | Reports must resolve visible accounts/categories before totals, balances, cash-flow buckets and drill-down rows. |
| Transfer semantics | Transfer create/update/delete/restore remains inside `/transactions`; unsupported scope or hidden side must deny safely and atomically. |

## Remaining frontend/mobile gaps

| Owner | Gap |
| --- | --- |
| PWA | Regenerate or verify TypeScript API client from the synced OpenAPI; remove assumptions about user/profile/household/export/standalone transfer/void routes. |
| Android | Regenerate or verify Kotlin API client from the synced OpenAPI; keep report modes and transfer scopes fixed to the canonical enum sets. |
| QA | Keep fixture graph/report route status aligned with the now-mounted report runtime; older notes that reports are unmounted are stale evidence, not current contract truth. |

## Done criteria for this contract wave

- OpenAPI `paths` exactly match sessions, accounts, categories, transactions and reports mounted for closed MVP.
- `/api/v1/transfers` and `/api/v1/transactions/{transactionId}/void` are absent.
- `SourceType`, `ReportMode`, `TransferScope` and `ReportBucket` match runtime MVP boundaries.
- Contract tests prove route inventory, operation IDs and excluded families.
- Redocly lint and focused API contract tests pass, with any frontend/mobile regeneration gap recorded.
