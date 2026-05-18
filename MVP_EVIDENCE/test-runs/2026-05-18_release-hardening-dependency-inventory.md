# Release hardening dependency inventory

Generated: 2026-05-18

Method: no new dependency/security tools installed. Inventory is derived from existing `package-lock.json`, backend `.venv` `pip list`, and Gradle wrapper dependency output.

## PWA

- Package: @finance/web-pwa@0.1.0
- Lockfile version: 3
- Lock package entries excluding root: 212
- npm audit vulnerabilities: total=0, critical=0, high=0, moderate=0, low=0
- npm audit dependency metadata: total=212, prod=67, dev=94, optional=52, peer=8

## Backend

- Package: finance-backend
- Manifest: `apps/backend/pyproject.toml`
- Existing venv installed packages: 38
- pip-audit: unavailable in existing `.venv`; exact blocker saved in `2026-05-18_release-hardening-backend-pip-audit.txt`.

## Android

- Project: FinanceMvpAndroid
- Resolved debug runtime unique coordinates: 155
- Gradle dependency graph: `2026-05-18_release-hardening-android-debugRuntimeClasspath.txt`
- Dependency insight captured for `androidx.security:security-crypto:1.1.0` and `com.google.crypto.tink:tink-android:1.8.0`.

Machine-readable inventory: `2026-05-18_release-hardening-dependency-inventory.json`.
