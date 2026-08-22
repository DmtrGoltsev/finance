# Owner waiver: personal iOS HTTP sideload

**Owner:** Finance personal/family device owner  
**Effective date:** 2026-08-22  
**Mandatory review by:** 2026-11-22

## Narrow exception

The owner explicitly accepts one temporary transport-security exception: the native iOS target `FinanceAppPersonalHTTP`, installed only by personal sideload on the owner's or family's iPhone, may use exactly `http://45.10.110.42/finance-api`.

This is not permission for a public release, App Store build, TestFlight-like distribution, the ordinary `FinanceApp` target, or its `Release` configuration. Those surfaces remain HTTPS-only and have no personal ATS exception.

## Accepted risk

The owner accepts that this cleartext route can expose or permit modification of data in transit, including passwords, bearer tokens, financial data, and session/authentication traffic. A network observer or active man-in-the-middle can read, alter, replay, redirect, or impersonate the service. The exception does not make HTTP safe and must not be represented as a production security control.

## Automatic invalidation

This waiver is invalid immediately if the host, path, authentication scheme, target identity, bundle identifier, ownership/device scope, or distribution channel changes, or if HTTPS becomes available. Any such change requires a new security review and waiver before use. The waiver also expires unless it is explicitly reviewed by 2026-11-22.

## Enforced boundaries

- `FinanceAppPersonalHTTP` has bundle id `com.codex.FinanceApp.PersonalSideload`, a distinct display/product name, an exact URL allowlist, and an ATS exception for only `45.10.110.42` without subdomains.
- The personal target uses manual `Apple Development` signing only; its archive action is pinned to `PersonalSideloadHTTP`, so it cannot produce an App Store-signed/exportable artifact.
- CI builds and inspects Debug, Release, and PersonalSideloadHTTP plist outputs; it fails on identity/signing/archive drift or any personal HTTP value in the ordinary app outputs.
- The special XCTest configuration executes allowlist, denylist, final-response, and URLSession 3xx redirect checks.
