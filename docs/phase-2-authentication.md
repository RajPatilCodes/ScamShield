# Phase 2: secure authentication and database foundations

Implementation/verification record, 2026-10-04. No commit or push was performed. The work started at `38ef5f7`; `1d47084` and `ec3a77c` remain its ancestors. All implementation files are from the exact approved allowlist. This is not production-readiness or security-audit certification.

## Implemented behavior

- `/v1/auth` only: registration, single-use verification, login, single-use recovery, refresh, logout, and owner-scoped session list/revocation. Registration does not issue credentials. Existing `/analysis/analyze`, `/analysis/history`, `/analysis/media`, `/analysis/upload`, and `/health` retain their paths and product behavior. Their existing shared authentication dependency checks the new sessions.
- New/replaced passwords use Argon2id. Successful legacy bcrypt login transparently rehashes to Argon2id after account verification. A lower configured cost does not silently downgrade a stronger stored Argon2id hash. Inputs beyond bcrypt's complete 72-byte boundary cannot safely prove the original password and are rejected; recovery provides the replacement path. There is no silent prefix verification or truncation. General accepted bounds remain a minimum of eight characters, with the approved maxima of 1,024 characters and 4,096 UTF-8 bytes.
- Access JWTs last 600 seconds, use HS256 and require `sub`, `sid`, `jti`, `iat`, `nbf`, `exp`, `iss`, `aud`, and access `purpose`. Missing, malformed, wrongly scoped, future/expired and owner-mismatched tokens fail. The account must be active/verified and the session live/unrevoked.
- A login creates one server-tracked session family. Opaque refresh credentials are stored only as SHA-256 digests; every success consumes one atomically and issues one successor. Sessions expire after seven idle days or thirty absolute days. Consumed credentials remain available for replay detection. Confirmed replay revokes the family; in a two-request race the loser revokes even the winner's successor. SQLite writer transactions and PostgreSQL row locks provide the rotation boundary.
- Logout can revoke using the last known family credential, including a consumed one after an uncertain refresh. Repeated/unknown logout is idempotent. Recovery consumes the challenge, replaces the hash, consumes outstanding same-purpose challenges and revokes all account sessions in one transaction.
- Persistent HMAC-keyed account+connection-IP buckets enforce five failed logins / fifteen minutes and three challenge requests / fifteen minutes. Successful credentials do not bypass an existing failure lockout. Forwarded headers cannot change the bucket. PostgreSQL bucket operations use transaction advisory locks. No unapproved registration/refresh numeric cap was added; unknown refresh is rejected and confirmed reuse revokes.
- Recovery acknowledgements do not reveal account existence, including transport failure. Transport failures do not commit an undelivered challenge, preserve the abuse count and log only a sanitized event. Authentication validation rejects non-credential characters/invalid Unicode without reflecting secret inputs. Other API validation retains its existing handler. Authentication failures never create authenticated sessions/credentials.
- Mobile stores only an API-bound refresh and pending-logout flag through an OS secure-storage adapter. Access is in memory; passwords/challenge secrets are not stored. Legacy plaintext bearer storage is removed, not copied. Refresh is single-flight; late login/refresh cannot resurrect a logged-out session. An uncertain refresh becomes pending revocation instead of being replayed. Offline logout disposes private UI state and visibly reports pending server confirmation; restart retries logout rather than restoring the session. Navigation uses session identity and a transition epoch so rapid account changes coalesced into one frame still discard prior private state.
- Main Android resources deny HTTP; debug allows only `10.0.2.2`. Dart independently permits only debug `http://10.0.2.2:8000`, requires HTTPS otherwise and rejects credential redirects. Backup/cloud/device-transfer rules exclude secure credentials, encryption-key preferences and legacy bearer preferences.

## Explicit configuration

There are no development signing-secret defaults. Required inputs include:

| Variable | Meaning |
| --- | --- |
| `ENVIRONMENT` | `development`, `test`, or `production` (development default) |
| `DATABASE_URL` | Explicit database URL for migration workflows |
| `JWT_SECRET` | Required signing secret; production rejects missing, short, repeated-character and known placeholder/default secrets |
| `JWT_ISSUER` / `JWT_AUDIENCE` | Defaults `scamshield` / `scamshield-mobile`; validated in access JWTs |
| `ARGON2_TIME_COST`, `ARGON2_MEMORY_COST`, `ARGON2_PARALLELISM` | Required explicit hashing inputs; memory is KiB |
| `VERIFICATION_EXPIRE_MINUTES` | Required explicit verification expiry |
| `PUBLIC_API_URL`, `CORS_ORIGINS` | Production requires HTTPS |
| `EMAIL_ADAPTER` | `capture` for development/tests; explicitly configured `smtp` for production |
| `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_SENDER`, `SMTP_TIMEOUT_SECONDS` | Required when SMTP is selected |
| `SMTP_PORT` | TLS SMTP port, default 465 |

Production requires explicitly configured PostgreSQL credentials and database TLS (`sslmode=require`, `verify-ca`, or `verify-full`). SMTP uses TLS with certificate validation. Missing production delivery configuration fails startup. Configuration errors hide input values in their rendered validation messages. No production credential or service was used in this work.

The supplied policy selected Argon2id without a numeric cost or verification expiry. Those are required configuration inputs rather than silently invented defaults. Test costs (`1`, `8192`, `1`) and test verification expiry (`30` minutes) are synthetic fixtures only, not production recommendations. SMTP timeout is likewise explicit. Reviewed deployment values and actual delivery infrastructure must be supplied by the operator; infrastructure files were not modified.

### Disposable development setup

After installing `backend/requirements.lock`, set the required inputs in the shell. Do not edit the protected database or an environment file to run tests. For a synthetic local example only:

```bash
export ENVIRONMENT=test
export JWT_SECRET=synthetic-local-test-secret
export ARGON2_TIME_COST=1 ARGON2_MEMORY_COST=8192 ARGON2_PARALLELISM=1
export VERIFICATION_EXPIRE_MINUTES=30 EMAIL_ADAPTER=capture
export DATABASE_URL="sqlite:///$(mktemp -d)/synthetic.db"
export MIGRATION_DATABASE_URL="$DATABASE_URL"
python -m alembic upgrade head
uvicorn app.main:app --reload
```

The capture adapter stores synthetic messages in `app.email_delivery.captures` inside the running process. Tests inspect that capture directly. There is no public capture endpoint, automatic secret logging, real delivery, or persistent inbox. Manual development UI testing needs access to that in-process capture through an interactive/debug backend process; importing it in a second process does not read the server's inbox.

## Migration workflow and database safety

- `0001_existing_schema_baseline.py` exactly represents the original `users` and `analyses` schema.
- `0002_secure_authentication.py` adds account verification/active state, sessions, refresh digests, challenges and rate buckets. Existing hashes and original user/analysis columns/records are preserved. Existing accounts have no verified-ownership evidence, so the new verification field starts false; use verification before login. Original hashes are changed only after successful authorized login/recovery, not by the migration.
- Importing the application no longer runs `create_all`. Migrations require an explicit `DATABASE_URL` and identical `MIGRATION_DATABASE_URL`; the protected `scamshield.db` basename is refused before opening a connection, including case variations and resolved symlink aliases.
- Unknown unversioned databases cannot be upgraded or silently stamped. Explicit adoption requires `ADOPT_EXISTING_SCHEMA=1`, validates baseline tables/columns/indexes/constraints, and may only stamp revision `0001`. Normal upgrade follows after clearing the adoption flag.
- Tests use only disposable synthetic SQLite targets and validate their location before dropping schema or modifying the synthetic adoption fixtures. No migration/query was run against `backend/scamshield.db`; no Compose database volume was used.
- Destructive downgrades are rejected pending a separately reviewed data-preserving workflow. Offline migrations are rejected because they cannot validate the target.

For an independently inspected synthetic legacy fixture only, with the two target variables already matching:

```bash
ADOPT_EXISTING_SCHEMA=1 python -m alembic stamp 0001
python -m alembic upgrade head
```

These are operator instructions, not commands executed against an existing project database during this session. Test adoption is performed programmatically against newly created disposable fixtures.

## Dependency changes

Backend direct dependencies: replace `passlib[bcrypt]==1.7.4` with direct legacy `bcrypt==3.2.2`; add `argon2-cffi==25.1.0` and `alembic==1.14.0`. The existing bcrypt lock version is retained. New locked packages are Alembic, argon2-cffi, argon2-cffi-bindings `26.1.0`, Mako `1.4.3`, and MarkupSafe `3.0.4`; Passlib is removed. Existing unrelated package versions are retained. The hash-locked requirements were regenerated and successfully installed into `/tmp/omnirush/phase2-venv`.

Mobile: add `flutter_secure_storage: ^9.2.4`, resolved to `9.2.4`. SharedPreferences remains solely for legacy removal. Its secure-storage transitive additions are recorded in `mobile/pubspec.lock`: args, code_assets, crypto, six flutter_secure_storage packages, hooks, jni, jni_flutter, jni_util, js, logging, objective_c, package_config, path_provider, path_provider_android, path_provider_foundation, pub_semver, record_use, win32, and yaml (24 new packages including the direct package). Existing unrelated versions are retained. `flutter pub get --enforce-lockfile` completed successfully.

## Executed verification and commands

Backend used isolated CPython 3.12.13; Flutter used the installed Windows Flutter 3.44.8 / Dart 3.12.2, with the existing Android toolchain. No global/project toolchain configuration was changed.

Final successful checks:

| Check | Result |
| --- | --- |
| `tests/test_authentication.py` | 53 passed in final focused/full runs |
| `tests/test_sessions.py` | 11 passed in final focused/full runs |
| `tests/test_migrations.py` | 8 passed in final focused/full runs |
| Focused backend suite | **72 passed**, one dependency deprecation warning |
| Full backend regression suite | **111 passed**, one dependency deprecation warning |
| Flutter analyzer | **No issues found** |
| Full Flutter suite | **33 passed**, including existing widget/product regressions |
| Android debug APK | **Built successfully**, final build 53.6 seconds |
| Android boundary/backup source tests | Passed as part of Flutter suite |

Final focused run: 39.66 seconds. Final full backend run: 41.99 seconds. Final analyzer: 15.1 seconds. Final Flutter tests: approximately eleven seconds. APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`.

Executed backend/dependency commands (root unless specified):

```text
python --version
python3 --version
command -v python3 pip pip-compile flutter dart docker cmd.exe java
command -v uv
ls /tmp/omnirush /mnt/d/flutter/bin /mnt/c/Windows/System32/cmd.exe
docker info --format '{{.ServerVersion}}'
cmd.exe /c docker.exe info --format "{{.ServerVersion}}"
uv venv /tmp/omnirush/phase2-venv --python 3.12
uv pip compile backend/requirements.txt --python /tmp/omnirush/phase2-venv/bin/python --python-platform x86_64-unknown-linux-gnu --generate-hashes --output-file backend/requirements.lock
uv pip install --python /tmp/omnirush/phase2-venv/bin/python --require-hashes -r backend/requirements.lock
```

Executed from `backend/`, with focused tests repeated after fixes/additions:

```text
/tmp/omnirush/phase2-venv/bin/python -m pytest tests/test_authentication.py tests/test_sessions.py tests/test_migrations.py -q
/tmp/omnirush/phase2-venv/bin/python -m pytest -q
```

Executed Flutter commands, from `mobile/` except initial version probe; shell calls used the installed `D:\flutter\bin\flutter.bat` via `cmd.exe /c`. Analyzer/tests/build were chained only after prerequisite success:

```text
flutter --version
flutter pub get
flutter pub get --enforce-lockfile
flutter analyze
flutter test test/session_store_test.dart test/session_controller_test.dart test/auth_flow_test.dart test/api_service_test.dart
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Git inspection commands, repeated during scope/final review:

```text
git status --short --branch
git status --short
git status --short --branch --untracked-files=all
git log --oneline -10
git log --oneline -3
git ls-files
git diff --check
git diff --name-status
git diff -- backend/requirements.txt mobile/pubspec.yaml
git diff --stat
git merge-base --is-ancestor ec3a77c HEAD
git merge-base --is-ancestor 1d47084 HEAD
git merge-base --is-ancestor 38ef5f7 HEAD
```

Two additional read-only inline Python audits were executed through `/tmp/omnirush/phase2-venv/bin/python -c`: a `git diff -- backend/requirements.lock` / `git diff -- mobile/pubspec.lock` parser listed exact dependency additions/removals, and a `git status --porcelain=v1 --untracked-files=all` parser compared all changed paths against the approved allowlist. The latter reported **47 source files: 23 modified, 24 created, zero outside the allowlist**. The former confirmed the five new / one removed Python packages listed above, 24 new mobile packages, and zero existing mobile locked-version replacements. `git diff --check` completed successfully with no output. All three ancestry checks completed successfully, with HEAD still `38ef5f7`.

### Failures and warnings encountered

- `python --version`: failed because unqualified `python` is absent in WSL; native `python3` is 3.10.12. The isolated supported Python 3.12 environment was then used successfully.
- WSL Docker and Windows Docker probes failed: WSL integration is unavailable and the Docker Desktop Linux daemon is not running. No containers or persistent volumes were touched.
- First focused backend run: 52 passed / 3 failed. Invalid database URL raised an unsanitized SQLAlchemy error; migration preflight inspection left an external transaction uncommitted. Configuration error handling and transactional migration setup were corrected. Subsequent focused runs passed 55, 64, and 68 tests. Final review added stronger-hash preservation, protected-path alias, and schema-index-drift cases; focused runs then passed 71. The final malformed-Unicode rejection test expanded this to **72**, all passed.
- Earlier full backend runs passed 94, 106 and 107 tests. After the final additions, one run had 109 passes / 1 failure: JWT issuance/verifier wall clocks diverged by approximately 23 seconds, producing an `iat` rejection. A shared deterministic synthetic test clock now covers issuance and verification; production timing enforcement has no added skew allowance. A rerun passed 110, and the final expanded full suite passed **111**.
- First Flutter analyzer: one undefined transition parameter and one flow-control lint. Navigation was replaced with central auth-keyed navigation-tree disposal. Adding the final transition-epoch guard later exposed one multiline-if lint; two analyzer attempts reported it before the enclosing conditional was corrected. Final analyzer is clean; chained tests/build were not executed on the failed analyzer attempts.
- First focused Flutter run: 19 passed / 2 failed. A registration tap was off-screen and private routes were not being disposed by the callback-based navigation implementation. The test now scrolls to the action, and central navigation-tree replacement fixes disposal. Focused rerun: 23 passed. Earlier full suite: 24 passed.
- Expanded Flutter suite: 31 passed / 1 failed. The native-channel test incorrectly assumed a Flutter target-platform override changes `dart:io`'s Windows platform. The test was corrected to verify actual native-channel delegation and absence of plaintext preference writes. Subsequent expanded suite: 32 passed. The final rapid-account-switch disposal case expanded this to **33**, all passed.
- Backend suites report the existing Starlette/AnyIO `BlockingPortal` alias deprecation. No related dependency/framework refactoring was introduced.
- First successful Android build reported three Java 8 source/target obsolescence warnings from dependency compilation; subsequent final builds succeeded. Gradle/toolchain/signing files were not modified.
- Pub reports 24 packages with newer versions outside current constraints. No unrelated upgrade was performed.

## Remaining verification/operational gaps

- PostgreSQL migration, locking and concurrency integration were not run: Docker Desktop was unavailable. SQLite migration integrity, validated adoption/preservation, foreign keys, uniqueness/check constraints, refresh races and recovery races passed.
- Physical Android native Keystore/encrypted preferences, OS backup/transfer and device lifecycle behavior were not instrumented. The OS adapter/channel, storage contract, source security rules, client HTTPS boundary and APK compilation were checked.
- Live SMTP delivery and a production deployment were not exercised. Synthetic capture and configured-delivery failure handling were tested. Production requires explicitly configured delivery infrastructure and reviewed configuration values.
- No release APK was rebuilt and no release signing/deployment/CI infrastructure was changed.

## Exact source-file record

Modified existing files (23):

```text
README.md
SECURITY.md
backend/app/config.py
backend/app/database.py
backend/app/main.py
backend/app/models.py
backend/app/routes/auth.py
backend/app/schemas.py
backend/app/security.py
backend/requirements.lock
backend/requirements.txt
backend/tests/conftest.py
backend/tests/test_api.py
docs/api-contracts.md
mobile/README.md
mobile/android/app/src/main/AndroidManifest.xml
mobile/android/app/src/main/res/xml/network_security_config.xml
mobile/lib/main.dart
mobile/lib/screens/auth_screen.dart
mobile/lib/services/api_service.dart
mobile/pubspec.lock
mobile/pubspec.yaml
mobile/test/api_service_test.dart
```

Created source files (24):

```text
backend/alembic.ini
backend/app/auth_rate_limit.py
backend/app/email_delivery.py
backend/app/recovery.py
backend/app/sessions.py
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/0001_existing_schema_baseline.py
backend/migrations/versions/0002_secure_authentication.py
backend/tests/test_authentication.py
backend/tests/test_migrations.py
backend/tests/test_sessions.py
docs/phase-2-authentication.md
mobile/android/app/src/debug/res/xml/network_security_config.xml
mobile/android/app/src/main/res/xml/backup_rules.xml
mobile/android/app/src/main/res/xml/data_extraction_rules.xml
mobile/lib/models/auth_session.dart
mobile/lib/screens/password_recovery_screen.dart
mobile/lib/screens/verify_email_screen.dart
mobile/lib/services/session_controller.dart
mobile/lib/services/session_store.dart
mobile/test/auth_flow_test.dart
mobile/test/session_controller_test.dart
mobile/test/session_store_test.dart
```

The isolated dependency environment, pytest temporary synthetic databases, and generated ignored Flutter/build outputs are verification resources, not source additions. No protected scoring/analysis/media/upload implementation, product screen, Phase 0/1 record, infrastructure, toolchain, environment file or package initializer was edited. Final Git status/diff review is reported at handoff. No staging, commit, push or history rewrite is authorized by this record.
