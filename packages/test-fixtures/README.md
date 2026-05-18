# Test Fixtures

This package contains runner-neutral fixture tooling for QA evidence work. It is
not production code and does not seed a database.

## Owner/Member/Other/Invited/Former v1

The initial loader skeleton supports the manifest at:

- `qa/fixtures/owner-member-other-invited-former-v1/fixtures.manifest.example.json`
- `qa/fixtures/owner-member-other-invited-former-v1/manifest.schema.json`

The loader performs lightweight manifest shape checks using only the Python
standard library, allocates deterministic synthetic ids from fixture labels, and
returns sanitized structures for future runners:

- `sanitizedLabelToIdMap`
- `fixtureGraphSummary`
- `evidenceManifest`
- `redactionScanSummary`

It intentionally does not:

- access a database;
- import the production application;
- generate or import API clients;
- create tokens, token hashes, passwords, raw request/response bodies, raw export
  contents, or production configuration.

## W3 TTR Contract Fixtures

The W3 transactions/transfers/reports preparation adds contract-only artifacts:

- `qa/fixtures/owner-member-other-invited-former-v1/canonical-uuid-graph.json`
- `qa/fixtures/owner-member-other-invited-former-v1/goldens/visibility-expected.json`
- `qa/fixtures/owner-member-other-invited-former-v1/goldens/report-expected.json`
- `qa/fixtures/owner-member-other-invited-former-v1/goldens/transfer-denials-expected.json`

Use `load_ttr_fixture_contracts(...)` to validate canonical UUID uniqueness,
canonical actor coverage, W3 enum boundaries, unmounted-route expectations and
golden visibility/report/transfer-denial labels. These files are not runtime
seeds and do not contain concrete financial values.

Full JSON Schema validation is a future TODO if a runner later owns adding a
`jsonschema` dependency. Until then, the skeleton validates the top-level shape,
canonical actor labels, core section types, evidence mapping, and safety flags.

## Running Tests

```powershell
python -m unittest discover -s packages/test-fixtures/tests
```
