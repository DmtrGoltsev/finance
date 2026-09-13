# Native iOS: Mac handoff and physical iPhone install

## Source of truth

- Repository: `DmtrGoltsev/finance`
- Immutable release branch:
  `prod/release-finance-ios-current-parity-20260823-db7ebdd`
- Expected deployed code SHA:
  `db7ebdd41a35018ae59e1fc4f5c5e38f0ed37de6`
- Required governance ancestor: `4e1ef36724f804d648f2ea385da5259688915325`
- Required pipeline ancestor: `6d3f4e3cdb1ed7b333879603789d1ca9a1bb080c`
- Required iOS security ancestor: `744a422c5d012149f6c0051dcaf291623fd9a19c`
- Native target: `apps/ios`
- Minimum deployment target: iOS 17.0
- Security worker CI references:
  `https://github.com/DmtrGoltsev/finance/actions/runs/32601960992` and
  `https://github.com/DmtrGoltsev/finance/actions/runs/32602392746`
- Final iOS CI:
  `https://github.com/DmtrGoltsev/finance/actions/runs/32603535573`
- Self-contained copy-paste prompt for Codex on a new Mac:
  [ios-native-mac-codex-install-prompt.md](ios-native-mac-codex-install-prompt.md)

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
git fetch --prune origin
git checkout --detach origin/prod/release-finance-ios-current-parity-20260823-db7ebdd
EXPECTED_SHA="db7ebdd41a35018ae59e1fc4f5c5e38f0ed37de6"
test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"
git merge-base --is-ancestor 4e1ef36724f804d648f2ea385da5259688915325 HEAD
git merge-base --is-ancestor 6d3f4e3cdb1ed7b333879603789d1ca9a1bb080c HEAD
git merge-base --is-ancestor 744a422c5d012149f6c0051dcaf291623fd9a19c HEAD
cd apps/ios
xcodegen generate
open FinanceApp.xcodeproj
```

Stop if HEAD differs from the immutable `EXPECTED_SHA`, if the remote release
branch no longer resolves to it, or if any required ancestor check fails. Final
integration proof is iOS run `32603535573` on this exact SHA.

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

For the normal HTTPS release, select the `FinanceApp` target, then
`Signing & Capabilities`:

1. Enable automatic signing.
2. Choose the owner-approved Team.
3. Replace `com.codex.FinanceApp` with a unique owner-controlled bundle ID when
   the current identifier is unavailable to that Team.
4. Apply the corresponding bundle ID updates to test targets if Xcode requests it.
5. Set `FINANCE_RELEASE_API_BASE_URL` for the Release configuration only.

Do not commit Apple account data, signing certificates, provisioning profiles,
team identifiers or local API secrets.

For the owner-waived HTTP install, select `FinanceAppPersonalHTTP`. Preserve its
separate bundle id `com.codex.FinanceApp.PersonalSideload`, product/display name,
manual `Apple Development` signing and no-archive policy. Configure only the
local development Team/profile required by Xcode. Do not change it back to the
normal app identity and do not create an archive, IPA export, TestFlight or App
Store distribution path.

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

Run both the `FinanceApp` and `FinanceAppPersonalHTTP` scheme tests on an
available iPhone simulator. The security worker CI passed the normal XCTest/UI
suite and 10 dedicated personal transport tests, including a real `URLSession`
3xx redirect rejection. It also passed backend `ios_bearer`/migration gates,
Ruff, one Alembic head `20260822_0019`, built plist isolation, separate bundle
identity, manual development signing settings and no-archive/no-export checks.
The same gates must pass on the exact fetched integration head before signing.

## Install on a physical iPhone without App Store

1. In Xcode, select the connected iPhone as the run destination.
2. For the approved temporary HTTP path, select scheme
   `FinanceAppPersonalHTTP`; do not select the ordinary `FinanceApp` Release.
3. Configure only the owner-approved local development Team/profile while
   preserving the separate personal bundle id and manual Apple Development
   signing.
4. Confirm the waiver is still valid and the built plist contains only
   `http://45.10.110.42/finance-api` plus the exact IP ATS exception.
5. Use `Product -> Clean Build Folder`, then `Product -> Run`; do not Archive.
6. If iOS asks, trust the developer identity under device management settings.
7. Complete the physical-device QA checklist before treating the build as ready.

When a trusted HTTPS endpoint becomes available, use the normal `FinanceApp`
target and Release configuration instead, set `FINANCE_RELEASE_API_BASE_URL`,
and retain the ordinary HTTPS-only ATS policy.

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
- The ordinary Release build uses a non-production placeholder HTTPS URL in CI
  only to prove compilation. It does not prove production connectivity.
- The separate owner-waived personal target can use the exact production HTTP
  IP/path, but no signed build, physical install or production login has been
  proven by repository CI.
- Backend/PWA source `db7ebdd...` was deployed by GitHub Actions run
  `32604838031`. Production DB is `20260822_0019`; backup, service health,
  frontend assets and sanitized auth/read-only smoke passed. This server proof
  does not prove iPhone signing, installation or device behavior.
- Backend/PWA compatibility types may still contain legacy household vocabulary;
  native product UI and reachable API behavior are personal-only.
