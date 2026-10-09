# Cross-system tests

This directory is reserved for future cross-system, API-contract, end-to-end, and security tests. It currently contains documentation only, not an implemented test suite.

Existing component tests remain in their original locations:

- `backend/tests/`: FastAPI authentication, text analysis/history, and upload/media tests.
- `mobile/test/`: Flutter API-service and widget tests.

Do not move or duplicate those suites merely to populate this directory.

## Execution boundary

Phase 1 runs only component checks in isolated development environments. Backend tests use a temporary synthetic SQLite database and never use the local application database. Flutter commands write tool caches/build output; run them from the approved mobile environment. Never point tests at production or customer data.

The baseline checks are `python -m pytest` from `backend/`, and `flutter pub get --enforce-lockfile`, `flutter analyze`, and `flutter test` from `mobile/`. Actual results and unavailable-toolchain gaps are recorded in [`../docs/development-baseline.md`](../docs/development-baseline.md).

## Phase 1 verification results

Results below are from the verification run for this Phase 1 handoff:

| Check | Result |
| --- | --- |
| Backend locked environment | Passed with CPython 3.12.13 and `backend/requirements.lock`; 38 packages installed and `uv pip check` passed. |
| Backend tests | Passed: 39 tests, 2 deprecation warnings. |
| Flutter dependency resolution | Passed with Flutter 3.44.8/Dart 3.12.2 and `--enforce-lockfile`; `mobile/pubspec.lock` was unchanged. |
| Flutter analyzer | Passed: no issues found. |
| Flutter tests | Passed: all 8 tests. |
| Android wrapper/debug build | Passed: Gradle 9.1.0 wrapper check and debug APK build completed using Windows JBR 21.0.10. |
| CI workflow YAML | Passed static PyYAML parsing and required structure/pinned-action checks; dedicated YAML linters were unavailable. |
| Docker/Compose execution | Unavailable because Docker is not installed/connected in the current WSL 2 distro; the Compose file was statically parsed successfully. |

The default WSL Python 3.10.12 environment could not run pytest because the module is not installed and does not satisfy the locked dependency set. The supported Python 3.12 environment was used for the passing backend result. The direct WSL Flutter launcher also failed on CRLF shell-script line endings, so the available Windows Flutter launcher was used. See [`../docs/development-baseline.md`](../docs/development-baseline.md) for commands and exact limitations.

## Planned coverage for later phases

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

## Phase 3 verification

New backend tests cover consent/transient saving, two-user isolation, exact expiry, recent-auth binding/replay/revocation, private abuse buckets, JSONL exclusions, streamed rechecks, logical deletion, retry exhaustion/manual export/deletion retry, missing/stale authority activation blocking, authority-first commit interruption/reconciliation, reintroduced purged data, replacement integer IDs, unchanged terminal retention, post-lock retry deadlines, lifecycle replacement and populated migration preservation. Tests use synthetic disposable databases and separate synthetic authorities. The history regression setup now explicitly saves while its original assertions remain preserved.

```text
python -m pytest tests/test_privacy.py tests/test_privacy_lifecycle.py tests/test_privacy_jobs.py tests/test_recent_auth.py tests/test_privacy_rate_limits.py tests/test_migrations.py -q
python -m pytest -q
python -m pytest tests/test_privacy_postgresql.py -q
flutter analyze
flutter test test/privacy_test.dart test/privacy_transport_test.dart test/private_artifacts_test.dart
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

PostgreSQL tests require matching `PRIVACY_TEST_POSTGRES_URL` and `PRIVACY_TEST_POSTGRES_CONFIRM`, a loopback host, `postgresql+psycopg`, and a disposable database name beginning `phase3_test_`. Each run creates/drops its own random schema and exercises migration metadata, concurrent limits/grants, recovery/deletion ordering and global export slots. Missing service configuration produces explicit skips, not a passing PostgreSQL claim.

Mobile tests cover OFF saving, protected receipts, stale-response/401 isolation, late deletion success/timeout/transport failure across account switches, original/missing saved identity, bulk history invalidation/late-read fencing, product UI, incremental exports, per-consumption 24-hour picker expiry, delayed handoff deadlines, account cleanup, picker bindings and gallery-original preservation. Native copying still needs device execution. See `../docs/phase-3-privacy.md` for results and remaining gaps.
