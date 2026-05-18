# Owner/Member/Other/Invited/Former Fixture Set v1

## Purpose

This directory defines the runner-neutral QA fixture manifest for the Wave 2 privacy and authorization matrix after ADR-0001 selected the repository and evidence layout.

It is a specification skeleton only. It does not create application seed data, automated tests, runner-specific reports, credentials, tokens, or production-like logs.

## Source Documents

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/testing/wave-2-fixture-evidence-matrix.md`
- `docs/testing/qa-endpoint-traceability.md`

ADR-aligned paths:

- fixture set: `qa/fixtures/owner-member-other-invited-former-v1/`
- release evidence root: `artifacts/evidence/`
- generated/shared fixture packages, if later needed: `packages/test-fixtures/`

## Canonical Actors

All future loaders and runners must preserve these labels in metadata, even if generated ids differ per test run.

| Label | Role | Baseline |
| --- | --- | --- |
| `owner_a` | Owner A | Active owner/creator in `hh_ab`; owns personal A data |
| `member_b` | Member B | Active member in `hh_ab`; owns personal B data |
| `other_c` | Other C | Authenticated user outside `hh_ab`; active in `hh_c` |
| `invited_ab` | Invited | Pending invite to `hh_ab`; no active financial access |
| `former_ab` | Former | Previously active in `hh_ab`; now `left` or `revoked` |

## Fixture Domains

The manifest schema covers:

- actors and synthetic identity labels;
- households and memberships;
- accounts, categories, transactions and transfers;
- report modes, report periods and visible-account expectations;
- sessions, invite token states and lifecycle fixtures;
- privacy, export, delete, leave, cache and offline fixtures;
- golden neutral-error groups and no-hidden-count snapshots;
- evidence mapping to ADR directories under `artifacts/evidence/**`.

## Fixture Loader Spec Skeleton

A future fixture loader should implement these phases:

1. `validate_manifest`: validate `fixtures.manifest.json` against `manifest.schema.json`.
2. `allocate_synthetic_ids`: generate opaque test ids while retaining canonical labels.
3. `seed_graph`: create actors, households, memberships, accounts, categories, transactions and transfers.
4. `seed_security_state`: create sessions, invite states, stale session references and revoked/expired handles.
5. `seed_privacy_state`: create export, delete, leave, cache and offline fixture references.
6. `emit_loader_map`: write a sanitized label-to-id map for runners, with no tokens, secrets, raw financial bodies or log amounts.
7. `emit_evidence_manifest`: write runner-neutral evidence metadata under `artifacts/evidence/<bucket>/`.

The loader must be deterministic for labels and relationships but may generate different opaque ids per isolated run.

## Evidence Buckets

Each scenario in the manifest maps to one or more ADR evidence buckets:

- `artifacts/evidence/api/`
- `artifacts/evidence/authz/`
- `artifacts/evidence/reports/`
- `artifacts/evidence/transfers/`
- `artifacts/evidence/privacy/`
- `artifacts/evidence/client/`
- `artifacts/evidence/security/`
- `artifacts/evidence/backups/`
- `artifacts/evidence/dependencies/`

Evidence metadata may include synthetic labels, scenario ids, release gates, endpoint surfaces and normalized status. It must not include real personal data, secrets, plaintext tokens, token hashes, passwords, raw financial payloads, production config, or unsanitized logs.

## Files

- `manifest.schema.json`: JSON Schema for future fixture manifests.
- `fixtures.manifest.example.json`: useful skeleton example covering Owner A, Member B, Other C, Invited and Former.
- `canonical-uuid-graph.json`: W3 TTR contract graph with stable UUID labels
  for actors, households, memberships, accounts, categories, planned
  transactions, transfers and reports.
- `goldens/visibility-expected.json`: expected transaction visibility and
  neutral-denial cases for future runtime tests.
- `goldens/report-expected.json`: expected report mode account inclusion,
  exclusion and no-hidden-count cases.
- `goldens/transfer-denials-expected.json`: expected transfer denial envelopes
  and no-write/no-report-trace obligations.

## Definition Of Done For This Skeleton

- Files align with ADR-0001 paths.
- The schema and example cover the canonical actor matrix at a useful skeleton level.
- Evidence mapping uses `artifacts/evidence/**`.
- No automated tests or production code are introduced.
