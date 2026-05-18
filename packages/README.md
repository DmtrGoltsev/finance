# Packages Workspace

Ownership: generated-client and QA fixture workers assigned by the orchestrator only.

Expected future contents:

- `generated/web-api-client/` derived from `api/openapi/openapi.yaml`.
- `generated/android-api-client/` derived from `api/openapi/openapi.yaml`.
- `test-fixtures/` shared by backend, API, client, and QA evidence tests.

Generated code must not be hand-edited. Do not add package manifests or generated outputs until the responsible worker and generator are assigned.
