# Native iOS: Mac handoff and physical iPhone install

## Source of truth

- Repository: `DmtrGoltsev/finance`
- Branch: `codex/ios-native-current-parity-20260822`
- Verified commit: `a5a332093587fc2467383686cca089877d03f90e`
- Native target: `apps/ios`
- Minimum deployment target: iOS 17.0
- CI reference: `https://github.com/DmtrGoltsev/finance/actions/runs/32563222674`

`apps/web-pwa/ios` is the legacy Capacitor wrapper. It is not the target native
application and must not be used for the native iPhone handoff.

## Prerequisites on the Mac

1. Install a current Xcode compatible with the project. CI passed with Xcode 16.4.
2. Install Xcode command-line tools and accept the Xcode license.
3. Install XcodeGen:

```bash
brew install xcodegen
```

4. Sign in to the owner-approved Apple Developer or Personal Team in Xcode.
5. Connect the iPhone by cable, trust the Mac and enable Developer Mode on the
   device when iOS requests it.

## Checkout and project generation

```bash
git clone git@github.com:DmtrGoltsev/finance.git
cd finance
git checkout codex/ios-native-current-parity-20260822
git pull --ff-only
git rev-parse HEAD
cd apps/ios
xcodegen generate
open FinanceApp.xcodeproj
```

The expected `git rev-parse HEAD` for this handoff is
`a5a332093587fc2467383686cca089877d03f90e`.

## Production API requirement

Release builds require the user-defined build setting
`FINANCE_RELEASE_API_BASE_URL` with an absolute trusted HTTPS URL, for example:

```text
https://finance.example.com/finance-api
```

The value must not be localhost, a debug endpoint or plain HTTP. Do not enable
`NSAllowsArbitraryLoads` and do not add a broad ATS exception to bypass this gate.

Acceptable production options:

1. Preferred: an owned domain/subdomain with a publicly trusted TLS certificate
   and automated renewal.
2. Alternative: a publicly trusted short-lived Let's Encrypt IP-address
   certificate, with explicit renewal monitoring and the IP present in the
   certificate SAN.

Until one of these endpoints is configured and reachable, native iOS production
login is blocked by design. The existing plain HTTP IP is not sufficient.

## Owner-only personal HTTP sideload exception

This is a separate, temporary development-install path, not a replacement for
the HTTPS release requirement above. It is allowed only while the explicit
[owner waiver](security/ios-personal-http-waiver-2026-08-22.md) remains valid:

- select target and scheme `FinanceAppPersonalHTTP`, not `FinanceApp`;
- use configuration `PersonalSideloadHTTP` and the exact built-in endpoint
  `http://45.10.110.42/finance-api`;
- keep bundle id `com.codex.FinanceApp.PersonalSideload`, display name
  `Finance Personal HTTP`, and manual `Apple Development` signing;
- install only onto the owner or family iPhone through a connected Xcode device
  run. XcodeGen emits a structural archive action for every scheme, but this
  target is deliberately excluded from `buildForArchiving` and has no export
  path;
- never use this target for App Store, TestFlight, public distribution, or the
  normal `FinanceApp` Release configuration.

The accepted residual risk is substantial: plaintext traffic can expose or be
modified by a network observer, including passwords, bearer tokens and
financial data. The exception expires unless reviewed by 2026-11-22 and is
invalid immediately if the host, path, authentication, identity, device scope,
distribution channel or HTTPS availability changes.

## Signing and bundle identifier

In Xcode, select the `FinanceApp` target, then `Signing & Capabilities`:

1. Enable automatic signing.
2. Choose the owner-approved Team.
3. Replace `com.codex.FinanceApp` with a unique owner-controlled bundle ID when
   the current identifier is unavailable to that Team.
4. Apply the corresponding bundle ID updates to test targets if Xcode requests it.
5. Set `FINANCE_RELEASE_API_BASE_URL` for the Release configuration only.

Do not commit Apple account data, signing certificates, provisioning profiles,
team identifiers or local API secrets.

## Build and test

From `apps/ios`, the reproducible command-line gates are:

```bash
xcodegen generate
xcodebuild build \
  -project FinanceApp.xcodeproj \
  -scheme FinanceApp \
  -configuration Debug \
  -destination 'generic/platform=iOS' \
  CODE_SIGNING_ALLOWED=NO

xcodebuild build \
  -project FinanceApp.xcodeproj \
  -scheme FinanceApp \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  CODE_SIGNING_ALLOWED=NO \
  FINANCE_RELEASE_API_BASE_URL='https://<trusted-host>/finance-api'
```

Run the `FinanceApp` scheme tests on an available iPhone simulator. The verified
final CI baseline is 77 XCTest plus 1 launch UI test with zero failures. The
same run also passed the backend `ios_bearer`/migration gate with 63 tests,
Ruff and one Alembic head `20260822_0019`. The full local backend suite passed
with 313 tests and 6 skips. Final independent code review verdict is APPROVE.

## Install on a physical iPhone without App Store

1. In Xcode, select the connected iPhone as the run destination.
2. Select the owner-approved Team and unique bundle ID.
3. Set the trusted HTTPS Release API URL.
4. Use `Product -> Clean Build Folder`, then `Product -> Run`.
5. If iOS asks, trust the developer identity under device management settings.
6. Complete the physical-device QA checklist before treating the build as ready.

A free Personal Team can impose short provisioning validity and device limits.
Use the paid developer team when stable long-lived installation is required.

## Required physical-device acceptance

- Register or sign in with the persistent production QA account locator documented
  in Obsidian; retrieve its password only from the owner-managed secret store.
- Confirm one-time login persists through force quit and relaunch; the password
  itself is not stored by the app.
- Confirm logout invalidates the bearer session and makes data from the previous
  account inaccessible. Account-scoped local recovery data must never be visible
  to another user.
- Confirm categories show `Категории расходов` and expose no finance mode selector.
- Exercise manual income, expense, transfer, date selection, category search,
  payment-account filtering, assets, investment transfer analytics and month switch.
- Exercise offline create/edit/delete, relaunch, manual sync and server convergence.
- Confirm concurrent 401 responses perform one refresh and retry each request at
  most once; a second 401 clears the current session; 403 preserves identity and
  pending work.
- Confirm screenshot OCR is online-only and no image/raw OCR payload enters local
  storage, pending sync, logs or evidence.

## Known limitations

- Windows cannot perform Apple signing or physical-device installation.
- The successful integrated CI build used a non-production placeholder HTTPS URL only to
  prove Release compilation. It does not prove production connectivity.
- Actual production login remains blocked until the trusted HTTPS endpoint is
  chosen and configured.
- Backend migrations through `20260822_0019` are CI-tested but were not deployed
  to production by this iOS QA/documentation wave. Production preflight found
  `protection_rules=[]`; local branch
  `prod/release-finance-ios-backend-20260822` is not pushed, production DB is
  still `20260618_0017`, health is HTTP 200, and trusted HTTPS/FQDN is absent.
- Backend/PWA compatibility types may still contain legacy household vocabulary;
  native product UI and reachable API behavior are personal-only.

