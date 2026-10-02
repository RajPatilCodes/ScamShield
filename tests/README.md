# Cross-system tests

This directory is reserved for future cross-system, API-contract, end-to-end, and security tests. It currently contains documentation only, not an implemented test suite.

Existing component tests remain in their original locations:

- `backend/tests/`: FastAPI authentication, text analysis/history, and upload/media tests.
- `mobile/test/`: Flutter API-service and widget tests.

Do not move or duplicate those suites merely to populate this directory.

## Execution boundary

No application tests were run during Phase 0. Repository inspection and staging are not evidence of passing application tests.

Backend `conftest.py` selects a file-backed test database and drops/recreates its tables. Flutter commands also write caches and build outputs. Establish an isolated, synthetic-data environment and inspect configuration before executing either suite. Never point tests at production, the existing local application database, or customer data.

The existing documented checks are `python -m pytest` from `backend/`, and `flutter analyze` / `flutter test` from `mobile/`, using the approved development environment. Their current toolchain compatibility and results remain unverified.

## Planned coverage

- Two-user and multi-role isolation for every private object, list, search, count, export, and download.
- Session expiry, refresh rotation, revocation, email verification, and account recovery.
- Strict write schemas, forbidden fields, idempotency, and optimistic concurrency.
- Assessment explanations and uncertainty, including benign near-matches and language limitations.
- Report lifecycle and owner-visible versus internal events.
- Evidence ownership, bounded intake, quarantine, isolated processing, and authorized previews.
- Consent, retention, exports, deletion, and queued-job/deletion races.
- Generic notifications, authorized deep links, and account-switch cache cleanup.
- Offline emergency guidance, accessibility, permissions, and Android/iOS lifecycle behavior.

Add these tests alongside the corresponding implementation phases. Do not fabricate coverage or replace failing checks with no-op checks.
