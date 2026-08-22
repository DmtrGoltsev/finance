# Native iOS handoff

## Standard app

Use scheme `FinanceApp` for normal development and release work. Its bundle id is `com.codex.FinanceApp`; Debug may use the local loopback API, while Release requires an HTTPS `FINANCE_RELEASE_API_BASE_URL`. Do not select the personal sideload target for App Store, public, or release distribution.

## Personal HTTP sideload

`FinanceAppPersonalHTTP` is a separate, temporary personal-device target. It has product/display name `Finance Personal HTTP`, bundle id `com.codex.FinanceApp.PersonalSideload`, the `PersonalSideloadHTTP` configuration, and manual `Apple Development` signing. Configure a development team/profile in Xcode before installing it on the owner/family iPhone.

The scheme's archive action is pinned to `PersonalSideloadHTTP` and manual `Apple Development` signing, so it has no App Store export path. It permits only `http://45.10.110.42/finance-api`; redirect, host, path, authority, and final-response escapes are rejected. Its scope and accepted cleartext/MITM/password/token/financial-data risks are recorded in [the owner waiver](../../docs/security/ios-personal-http-waiver-2026-08-22.md), which must be reviewed by 2026-11-22 and becomes invalid on host/path/auth/identity changes or HTTPS availability.

Run `FinanceAppPersonalHTTP` on a connected iPhone only after confirming this waiver remains valid. CI executes the special XCTest configuration and checks its built plist, signing settings, bundle identity, and absent archive/export action.
