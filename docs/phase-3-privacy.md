# Phase 3: privacy and ownership

Implementation record starting at `1ae5ad4`. No commit/push is authorized or performed. Phase 0/1/2 historical records and the protected authentication/scoring/media/upload implementations remain preserved. Verification uses synthetic disposable resources only.

## Implemented boundary

`/analysis/analyze` retains its scoring response and is transient. Explicit `save:true` through `/v1/privacy/analyses` requires current purpose-specific versioned product consent. Legacy analysis rows are marked `legacy_no_retroactive_consent`; migration does not manufacture a receipt or renew the original retention clock. List/search/count/detail/export enforce owner/lifecycle/generation, deletion markers and expiry.

Privacy endpoints add consent, recent authentication, saved detail/delete, export jobs/content, bulk/account deletion and receipt-authorized status. Strict schemas reject ownership/lifecycle/expiry/deletion/authorization overrides. Wrong-owner IDs return 404. Idempotency is principal/operation/request-bound and conflicting reuse fails. Raw content is not duplicated in idempotency storage. Independent authority identity/revision/content checks block missing/stale restoration state before authentication/private activation or maintenance. Trusted reconciliation imports lifecycle/deletion intent, including reopening satisfied purge intent for reintroduced data. Job workers recheck state and eligibility deadlines after locking/refetching.

Recent-auth grants reuse existing password verification; five-minute single use is bound to owner/session/lifecycle/revision/action/target. Refresh issuance is not human authentication. Existing logout/recovery/revocation invalidates grants through current-state checks. Export creation/download have separate grants. Bulk/account deletion requires confirmation; individual deletion and ordinary consent withdrawal do not.

Logical deletion is immediate, physical purge retryable. Account deletion has no cancellation/grace, restricts access and revokes sessions atomically, and never reopens an account after failure. New registrations have new lifecycle identities. New explicitly saved data after bulk deletion uses a later data generation and is not erased by old work.

Export is versioned UTF-8 JSONL: manifest, allowlisted owner account/analysis/consent/session/audit records, completion marker. Passwords, hashes, tokens, credential digests and other-user data are excluded. Both server and mobile stream bounded data; the complete export is not buffered. JSONL/byte-count completion is verified before Android document handoff. User-saved copies are outside subsequent cleanup.

Audit has an event allowlist and opaque references, excluding submitted content, credentials, emails, filenames, request bodies and credential digests. Private validation/unexpected errors and controlled Uvicorn access logs are redacted; private responses/errors are no-store. External logging is unresolved.

## Approved Section M configuration

Every setting is an explicit `PrivacySettings` field with a `PRIVACY_` environment override. Baseline values are owner-approved inputs, not guessed production policies.

| Field | Approved value |
| --- | --- |
| `analysis_days` | 90 |
| `export_hours`, `artifact_hours` | 24 each |
| `consent_days` | 730 fixed days |
| `audit_days` | 365 fixed days |
| `status_days` | 30 after completion/failure |
| `marker_min_days` | 30 minimum; unresolved markers retained until deletion/restoration fencing is satisfied |
| `recent_auth_seconds` | 300 |
| `rate_window_seconds` | 900 |
| `reauth_limit` | 5 failed attempts/account+IP |
| `export_create_limit` | 3 requests/account+IP |
| `export_read_limit` | 10 shared download/status requests/account+IP |
| `deletion_limit` | 3 requests/account+IP |
| `receipt_limit` | 10 requests/account+IP |
| `retry_initial_seconds`, `retry_max_seconds` | 60; 3600 |
| `automatic_retries` | 5, exponential backoff; manual retry available |
| `maintenance_hour_utc`, `maintenance_minute_utc` | 2; 0 |
| `poll_seconds` | 300 while running |
| `batch_size` | 100 |
| `export_max_bytes` | 100,000,000 (100 MB, not 100 MiB) |
| `account_export_jobs`, `global_export_jobs` | 1; 2 |

The corrective restoration integration adds the explicit string input `PRIVACY_AUTHORITY_PATH`, default unset. API startup never creates an authority. Its location/independent infrastructure must be configured; no numeric setting or external backup-retention policy is added or changed. Revision 0003 includes the local checkpoint table through the existing privacy-table metadata migration.

Timezone-naive legacy timestamps use UTC only when existing schema/documentation establishes that meaning or explicit resolution supplies it. Otherwise migration fails safely. Originals are preserved. Calendar-year arithmetic is not used. Existing Phase 2 abuse limits are unchanged; receipt lookups without a binding use the same approved lookup limit in a shared unbound scope.

## Mobile and preservation

Profile privacy controls, OFF-by-default scan choice, saved-result deletion, separate password confirmation, saved-data purge status and signed-out deletion status are integrated. Access stays memory-only; passwords/grants are not persisted. Protected privacy storage is separate from the untouched Phase 2 credential store. SessionController adds only a read-only generation getter. API retries/late responses enforce generation identity before and after credential acquisition. Uncertain mutations retain memory-only idempotency keys for explicit retry; keys are cleared on account transitions. New registrations do not reuse an earlier deletion receipt.

App-owned temporary artifacts have owner and 24-hour expiry metadata enforced at consumption, not only cleanup. Picker upload checks before submission and every stream chunk; preview expiry removes the selection. Native handoff carries the original owner/deadline and checks metadata/time before opening/writing, each bounded write and completion, including after document-picker delay. Startup cleans previous-account files before restoration; cleanup failure gates private requests/UI until retry. Switching cancels native handoff and removes old files. Picker recovery needs matching API/owner/session binding and never deletes gallery originals. An explicit display filename preserves the existing media MIME/extension semantics when bytes come from an opaque app-owned temporary copy.

### Corrective findings resolved

1. Restoration is fail-closed against the independently configured authority; missing/stale/empty local fencing and interrupted authority-first commits cannot activate private access/jobs. Bootstrap and trusted reconciliation are explicit maintenance commands.
2. Account-deletion success, timeout and transport-error handling rechecks initiating owner/session/generation before invalidation. Late Account A outcomes preserve Account B credentials.
3. History returns stable identity with the original saved result. Individual deletion never resolves a stale integer ID to substitute its current occupant's key. Missing identity fails safely; bulk deletion invalidates cached identities and pending reads, then reloads on returning from controls.
4. App-managed artifact expiry is enforced on use, picker streaming and delayed native copying; explicit user-saved copies remain outside cleanup.
5. Terminal timestamps/status expiry are immutable once first assigned. Staging expiry/cancellation and manual export retry do not renew the original 30-day status window.
6. Workers recheck persisted `next_attempt_at` after owner/job locking and refresh. Deterministic SQLite coverage passes; an additional real PostgreSQL interleaving regression is guarded/skipped without a disposable service.
7. `--retry-job` supports retained failed exports, preserving original retry accounting, source boundary and deadlines while safely rebuilding bounded staging. Deletion retry retains account restriction and budget, including after status expiry.

The two PostgreSQL transaction-scoped processing slots remain the global concurrency mechanism. Queued/ready records are not counted as concurrently running jobs; the existing slot regression remains guarded. Approved export exclusions still concern credential/account metadata; owner-saved analysis text is exported as saved.

The only dependency change promotes already-locked `path_provider` 2.1.6 to direct. No unrelated locked versions or backend dependencies are changed. Native handoff/Keystore/backup needs real-device checks; the implementation does not create an iOS target.

## Exact source record

New files (33):

```text
backend/app/privacy_config.py
backend/app/ownership.py
backend/app/privacy_models.py
backend/app/privacy_schemas.py
backend/app/privacy.py
backend/app/recent_auth.py
backend/app/privacy_rate_limits.py
backend/app/audit.py
backend/app/privacy_jobs.py
backend/app/privacy_maintenance.py
backend/app/privacy_logging.py
backend/app/routes/privacy.py
backend/migrations/versions/0003_privacy_and_ownership.py
backend/tests/privacy_helpers.py
backend/tests/test_privacy.py
backend/tests/test_privacy_lifecycle.py
backend/tests/test_privacy_jobs.py
backend/tests/test_recent_auth.py
backend/tests/test_privacy_rate_limits.py
backend/tests/test_privacy_postgresql.py
mobile/lib/models/privacy.dart
mobile/lib/services/privacy_service.dart
mobile/lib/services/privacy_store.dart
mobile/lib/services/private_artifacts.dart
mobile/lib/screens/privacy_screen.dart
mobile/lib/screens/recent_auth_screen.dart
mobile/lib/screens/deletion_status_screen.dart
mobile/test/privacy_fixtures.dart
mobile/test/privacy_test.dart
mobile/test/privacy_transport_test.dart
mobile/test/private_artifacts_test.dart
docs/phase-3-privacy.md
docs/privacy-operations.md
```

Modified files (23):

```text
backend/app/models.py
backend/app/main.py
backend/app/routes/analysis.py
backend/tests/conftest.py
backend/tests/test_api.py
backend/tests/test_migrations.py
mobile/lib/models/auth_session.dart
mobile/lib/services/session_controller.dart
mobile/lib/services/api_service.dart
mobile/lib/models/scan_result.dart
mobile/lib/main.dart
mobile/lib/screens/home_screen.dart
mobile/lib/screens/scan_screen.dart
mobile/lib/screens/result_screen.dart
mobile/android/app/src/main/kotlin/com/example/scamshield_mobile/MainActivity.kt
mobile/pubspec.yaml
mobile/pubspec.lock
README.md
PRIVACY.md
SECURITY.md
docs/api-contracts.md
mobile/README.md
tests/README.md
```

All other tracked files remain untouched. Existing authentication/session/password/recovery/rate-limit/email/config/database/schema implementations, prior migrations, scoring/media/upload processors/tests, preserved mobile auth/session tests, infrastructure, historical records and later-phase modules are outside this change. Existing history test assertions are preserved; setup explicitly consents/saves. Migration tests verify original fields and populated credential tables.

## Verification and remaining gaps

Verification used CPython 3.12.13 at `/tmp/omnirush/phase2-verification-venv/bin/python` and Windows Flutter 3.44.8/Dart 3.12.2 via `cmd.exe /c D:\flutter\bin\flutter.bat`. The temporary environment disappeared across resumed sessions and was recreated from the unchanged hash-locked requirements (42 packages); compatibility check passed. No backend dependency declarations or global tooling configuration were changed.

| Check | Result |
| --- | --- |
| Focused privacy/retention/grants/limits/migration suite | 46 passed; final focused run 30.94 seconds |
| Full backend regression | 149 passed, 7 PostgreSQL-specific tests explicitly skipped; final run 145.72 seconds |
| PostgreSQL-specific invocation | 7 skipped; disposable PostgreSQL unavailable |
| SQLite migration tests | 11 passed, including fresh/adopted/populated Phase 2 preservation, orphan/malformed rejection and protected targets |
| Flutter analyzer | No issues found |
| Focused privacy/transport/artifact tests | 27 passed |
| Full Flutter regression | 60 passed |
| Android debug APK | Built successfully; final build 164.6 seconds |
| Synthetic CLI migration | `alembic upgrade head` completed successfully; `alembic current` confirmed `0003 (head)` |
| Maintenance CLI | `--init-authority`, `--dry-run`, `--once`, `--reconcile-authority` completed on the disposable migrated database/independent synthetic authority |
| Exact scope audit | 33 new + 23 modified, no outside-allowlist paths |
| Preservation | All 76 other tracked files byte-identical to HEAD, including every Phase 2 preservation-boundary file |
| Whitespace | `git diff --check` passed |

Executed from `backend/`:

```text
/tmp/omnirush/phase2-verification-venv/bin/python -m pytest tests/test_privacy.py tests/test_privacy_lifecycle.py tests/test_privacy_jobs.py tests/test_recent_auth.py tests/test_privacy_rate_limits.py tests/test_migrations.py -q
/tmp/omnirush/phase2-verification-venv/bin/python -m pytest -q
/tmp/omnirush/phase2-verification-venv/bin/python -m pytest tests/test_privacy_postgresql.py -q
```

Executed from `mobile/` through the Windows launcher:

```text
flutter pub get --enforce-lockfile
flutter analyze
flutter test test/privacy_test.dart test/privacy_transport_test.dart test/private_artifacts_test.dart
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Final resumed analyzer/test/build commands also used `--no-pub` after dependencies were resolved, preserving the lockfile and avoiding repeated resolution:

```text
flutter analyze --no-pub
flutter test --no-pub test/privacy_test.dart test/privacy_transport_test.dart test/private_artifacts_test.dart
flutter test --no-pub
flutter build apk --no-pub --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Temporary environment recovery and dependency verification:

```text
uv venv /tmp/omnirush/phase2-verification-venv --python 3.12.13
uv pip install --python /tmp/omnirush/phase2-verification-venv/bin/python --require-hashes -r requirements.lock
uv pip check --python /tmp/omnirush/phase2-verification-venv/bin/python
```

CLI smoke used explicit synthetic authentication settings, `EMAIL_ADAPTER=capture`, `ENVIRONMENT=test`, and disposable databases under `/tmp/omnirush`, with identical `DATABASE_URL`/`MIGRATION_DATABASE_URL`. The corrective target was created with `mktemp -d /tmp/omnirush/phase3-fixes.XXXXXX` and database name `synthetic.db`; `PRIVACY_AUTHORITY_PATH` designated its separate `synthetic.db.authority`. Commands were:

```text
python -m alembic upgrade head
python -m alembic current
python -m app.privacy_maintenance --init-authority
python -m app.privacy_maintenance --dry-run
python -m app.privacy_maintenance --once
python -m app.privacy_maintenance --reconcile-authority
```

No protected local database or Compose volume was queried/migrated. Schema version/metadata and actual purge/export/retry behavior are additionally exercised in disposable tests. The synthetic authority does not select any production storage/backup policy.

Git checks used `git diff --check`, status/diff inspection, and a read-only audit at `/tmp/omnirush/phase3_scope_audit.py` invoking `git diff --name-only HEAD`, `git ls-files --others --exclude-standard`, `git ls-tree -r HEAD`, and `git hash-object --no-filters --stdin-paths`. The audit compares exact new/modified sets and original blob hashes of every other tracked file, confirms no staged/deleted/renamed paths and checks whitespace for all new files via `git diff --no-index --check /dev/null <path>`. Lockfile diff changes only `path_provider`'s direct/transitive classification. Final compatibility recheck: `uv pip check --python /tmp/omnirush/phase2-verification-venv/bin/python`, 42 packages compatible.

### Failures/warnings resolved or remaining

- Early compatibility check: 77 authentication/session/API/migration tests passed. Expanded populated migration testing then found a deferred SQLite FK-counter failure at commit (34 passes/1 failure). The final graph validation/counter reset fixed it; the preservation test was retained and passed.
- One Flutter analyzer attempt reported an unused import in a new test; removed. Final analyzer, suites and build pass.
- Early Python environment probe found no pip module. After session resumption removed the temporary environment, uv recreated it and installed the unchanged locked set successfully. Attempts to use the missing path failed before tests ran.
- Resumed Flutter analyzer/build and a chained backend regression exceeded their tool timeouts under the slower environment. Independent retries with longer timeouts passed. No passing result is inferred from a timed-out command.
- WSL Docker integration is unavailable; Windows Docker's Linux-engine pipe is absent. No disposable PostgreSQL URL/service was available. Seven integration tests cover migrations/metadata, rate/grant races, recovery/deletion ordering, stale lifecycle work, global export slots and post-lock deadline postponement, but remain unverified rather than claimed passing.
- Corrective analyzer first reported one `prefer_const_declarations` info in a regression test; fixed, final analyzer clean. The first temporary scope auditor incorrectly treated normal no-index addition exit 1 as an error; corrected its exit-bit handling, then all new-file whitespace checks passed with no source whitespace change needed.
- Existing Starlette/AnyIO BlockingPortal deprecation remains. Final locked pub resolution reported 28 newer versions outside constraints; selected dependency versions remain unchanged. No unrelated upgrades were made.
- Physical Android Keystore/backup/process-death/document-provider execution, live SMTP, production scheduling and external restore/processor orchestration were not exercised. Native code compiles in the debug APK; component tests do not certify native devices.

See `privacy-operations.md` for migration, maintenance, retry and guarded PostgreSQL setup. A skipped test is not a successful integration result. APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`. HEAD remains `1ae5ad4`; changes are unstaged and uncommitted.

Unresolved external/legal matters remain jurisdiction-specific requirements, legal consent wording, actual backup retention, external processor obligations and external infrastructure logging guarantees. Authoritative restore-ledger preservation/import and production scheduling need operational rollout. Synthetic process-local email capture does not establish cross-process or external-provider deletion. No production-readiness, legal-compliance or independent security-audit claim is made.
