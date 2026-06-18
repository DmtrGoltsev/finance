---
status: pending-final-qa
date: 2026-06-12
scope: date-only capture, payment accounts, Analysis, migration/API, deploy gate
sanitization: no raw OCR, screenshots, XML, UUIDs, tokens, cookies, passwords, or real financial data
---

# QA test plan: date-only capture and Analysis

This plan finalizes the sanitized QA coverage for the in-progress feature set. It is not a final PASS report and does not claim a commit hash. Evidence must remain sanitized: no raw OCR payloads, screenshots, UI XML, production financial data, UUIDs, tokens, cookies, passwords, or secret values.

## Status

Implementation is in progress and pending final QA plus commit. Release status remains blocked until the P0/P1 matrix below has evidence and the production deploy gate is explicitly passed.

## Test account metadata

| Environment | Safe alias / identifier | Purpose | Secret handling |
|---|---|---|---|
| Production QA | `finance.qa@local.test` | Owner-operated production smoke and authenticated QA flows only | Password value is never stored in KB or evidence. Out-of-band locator: `/etc/finance/qa-owner.env`, key `FINANCE_QA_PASSWORD`. |
| Development | `demo.owner@example.test` | Local/dev seeded flows, emulator/PWA development checks | No passwords, tokens, cookies, or sessions are stored in this plan. |

## P0 cases

| ID | Area | Case | Expected result | Required evidence |
|---|---|---|---|---|
| P0-DATE-ANDROID-01 | Android manual date picker | Create/edit a manual transaction with a date selected through the Android date picker, including month-boundary dates. | Transaction uses the selected date-only value for reporting; no timezone shift or previous/next-day drift. | Sanitized build/test output and manual note with route/screen names only. |
| P0-DATE-PWA-01 | PWA manual date picker | Create/edit a manual transaction through PWA date input with date-only value. | API receives/stores `transactionDate`; legacy timestamp is normalized consistently and reports use date-only boundaries. | Sanitized browser/API test output; no cookies or payload dumps. |
| P0-CAPTURE-01 | Capture confirmation edit amount/date | Edit both amount and date during capture confirmation before confirming a draft. | Confirmed transaction uses edited amount and edited date; original draft values do not leak into the transaction. | Sanitized backend/Android/PWA test result naming fields only, no OCR text. |
| P0-PAYMENT-01 | Payment account flag/filter | Mark an account as payment account and use expense account selection. | Expense creation/capture confirmation shows/selects only valid payment accounts; non-payment investment/asset accounts are excluded. | Unit/API result and sanitized UI note. |
| P0-ANALYSIS-01 | Analysis month switcher/category aggregation | Switch Analysis between adjacent months with repeated category expenses. | Category aggregation is month-boundary correct and does not mix transactions from other months. | Backend report test result and sanitized UI/manual note. |
| P0-ANALYSIS-02 | Analysis investment history | Validate investment history after broker/investment asset changes. | Investment history reflects current linked investment categories/accounts without stale or duplicate totals. | Sanitized report/API test result; no account IDs. |
| P0-MIGRATION-01 | Backend migration/API | Apply migration from previous head on representative schema and run API contract checks. | Date-only fields, payment account flag, balance snapshots/report contracts are present and backwards-compatible where intended. | Alembic before/after revision names, test command summary, OpenAPI parse/contract summary. |
| P0-PROD-GATE-01 | Production deploy gate | Before release, verify migration, service health, static/PWA reachability, Android prod base, and authenticated smoke using QA alias. | Gate is explicit PASS/FAIL; no release claim without authenticated smoke or accepted waiver. | Sanitized deploy checklist; no secrets/session material. |
| P0-EMULATOR-01 | Emulator QA | Install fresh APK on selected emulator, clear local app data, run login and critical date/capture/Analysis paths. | Selected serial is explicit; app opens correct build; no stale serial/run confusion. | Sanitized harness report with serial and APK hash only. |
| P0-BROKER-01 | Broker investment regression | Re-run `Брокер -> Инвестиция -> Сохранить` after new date/payment/report changes. | Save still creates/links investment category and Analysis investment totals remain correct. | Sanitized quick QA/harness result; no raw payloads or real account data. |

## P1 cases

| ID | Area | Case | Expected result | Required evidence |
|---|---|---|---|---|
| P1-DATE-ANDROID-02 | Android date picker | Reopen existing transaction after app restart. | Date picker shows persisted date-only value. | Sanitized emulator note. |
| P1-DATE-PWA-02 | PWA date picker | Refresh PWA after create/edit. | UI displays persisted date-only value without locale parsing drift. | Sanitized browser test note. |
| P1-CAPTURE-02 | Capture confirmation | Confirm draft after editing only date, only amount, and neither field. | Partial edits are respected; unchanged fields remain unchanged. | Backend/API test summary. |
| P1-PAYMENT-02 | Payment account flag/filter | Toggle payment flag off for an account previously used in expenses. | Historical transactions remain readable; new expense selection excludes the account. | Unit/API result and manual note. |
| P1-ANALYSIS-03 | Analysis month switcher | Switch months repeatedly and return to current month. | Loading state, selected month, totals, category rows, and investment history remain consistent. | Sanitized UI note or test output. |
| P1-ANALYSIS-04 | Category aggregation | Multiple categories with same display label in different scopes. | Aggregation respects scope/visibility and does not merge inaccessible data. | Backend report test summary. |
| P1-MIGRATION-02 | Rollback/readiness | Confirm migration has documented rollback/backup gate before prod apply. | Release operator has backup and rollback procedure before applying migration. | Sanitized checklist entry. |
| P1-EMULATOR-02 | Emulator QA | Verify Android/PWA date input with non-English locale settings where practical. | Formatting remains user-friendly while API values remain date-only. | Sanitized environment note. |

## Execution order

1. Backend migration/API contract tests.
2. Android and PWA unit/build checks.
3. Emulator QA for date picker, capture confirmation, payment account filtering, Analysis, and broker regression.
4. Production deploy gate with authenticated QA account alias and explicit secret-free evidence.
5. KB/evidence closure only after final QA and commit are complete.

## Definition of done

- All P0 cases have PASS evidence or an explicit accepted waiver.
- P1 failures are triaged with owner-visible risk and follow-up.
- Secret-pattern scan passes on changed documentation and generated evidence planned for staging.
- Final KB status is updated from `pending-final-qa` only after final QA and commit evidence exists.
