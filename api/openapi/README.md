# OpenAPI contract

`api/openapi/openapi.yaml` is the canonical source of truth for mounted MVP API wire behavior.

Implementation must follow contract-first discipline:

- review OpenAPI before changing routes, DTO fields, enum values, pagination, errors, or auth requirements;
- generate PWA TypeScript and Android Kotlin clients from this contract, not from hand-written client types;
- compare backend route inventory and response schemas against this file in CI;
- run OpenAPI lint and contract/fuzz tests before release evidence is accepted;
- keep generated code outside this directory and never edit generated clients by hand.

MVP boundaries are hard-coded in the contract:

- `/api/v1` is the only MVP prefix;
- PWA uses secure cookie auth plus CSRF; Android uses opaque bearer auth;
- `sourceType` accepts only `manual`;
- `personal` data is owner-only;
- `shared` data is visible only to active members of the same `Household`;
- reports expose `personal`, `shared_family_report`, and `combined_viewer_overview`;
- reports, search, autocomplete, pagination, and cache materialization must filter visible rows before aggregation;
- no response may expose hidden counts, filtered-out counts, hidden facets, or inaccessible-resource diagnostics.

MVP auth surface:

- `POST /users` exposes public registration and returns the same runtime session
  shape as `POST /sessions`;
- user profile, memberships, password reset, household, invite, and broader
  account lifecycle APIs remain outside the mounted MVP contract.

Reserved post-MVP exclusions:

- no user profile, household, invite, membership, export, deletion-request, logout-all, standalone transfer, or explicit transaction void routes are exposed in the mounted MVP contract;
- no import endpoints;
- no bank API, bank connection, bank account sync, SMS import, push import, broker connection, external credential, card, IBAN/account-requisite, raw bank statement, or push-token endpoints;
- reserved source values such as `file_import`, `bank_api`, `sms`, and `push` are not accepted by MVP create/update flows.

Next validation should run a real OpenAPI 3.1 linter such as Redocly or Spectral, then codegen dry-runs for the TypeScript and Kotlin clients.
