# Loader Notes

Worker: W2-15B

Scope: Python fixture loader skeleton for `owner-member-other-invited-former-v1`.

## Implemented

- Standard-library manifest loading from JSON.
- Lightweight shape validation for required top-level sections, canonical actor
  labels, safety flags, loader outputs and evidence buckets.
- W3 TTR contract loading for `canonical-uuid-graph.json` and golden
  visibility/report/transfer-denial expectations.
- Canonical UUID validation for Owner A, Member B, Other C, Invited and Former,
  including personal/shared accounts, categories, planned transactions,
  same-scope transfers and report cases.
- Contract enum guards for `sourceType = manual`, report modes
  `shared_family_report` / `combined_viewer_overview`, and transfer scopes
  `personal_same_owner` / `household_same_household`.
- Deterministic synthetic ids generated from fixture labels using UUIDv5 plus a
  short SHA-256 checksum.
- Sanitized output skeletons:
  - `sanitizedLabelToIdMap`
  - `fixtureGraphSummary`
  - `evidenceManifest`
  - `redactionScanSummary`
- Sanitization guard that rejects forbidden log/evidence keys for tokens, token
  hashes, passwords, raw bodies, amounts/balances, account/category names,
  secrets and production config.
- `unittest` coverage that parses `fixtures.manifest.example.json`.

## Explicit Non-Goals

- No DB seed execution.
- No production application imports.
- No generated client imports.
- No token, token hash, password, real personal data, raw financial body, raw
  export content, amount log, account name log or category name log output.
- No runtime transaction/report routes or transfer resource are mounted by these
  fixtures.

## TODO

- Add full JSON Schema validation only when a future runner owns a `jsonschema`
  dependency decision.
- Connect the skeleton outputs to the eventual W2 runner after stack/CI choices
  are finalized.
- Add DB seed implementation in a separate owned task, after the DB skeleton and
  seed strategy are ready.
