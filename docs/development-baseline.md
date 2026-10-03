# Development baseline

## Status

This document records the Phase 1 reproducible development baseline. It does not claim production readiness, a security audit, a supported release, or passing checks that have not actually run.

Phase 0 remains the repository-establishment commit:

- Commit: `ec3a77cb21dbb4f982dde02df28c33dd3fb6a6ef`
- Branch: `main`
- Tracked remote: `origin/main`

Phase 1 does not change application features, authentication/session behavior, database schemas, migrations, deployment, or production configuration.

## Supported development matrix

| Area | Baseline | Verification status |
| --- | --- | --- |
| Backend runtime | Python 3.12 | Target selected because `backend/Dockerfile` uses `python:3.12-slim`; Python 3.12.13 was available through `uv` and the backend suite ran there. |
| Backend dependency resolution | `uv pip compile` targeting CPython 3.12 on Linux x86_64 | `backend/requirements.lock` installed with hashes in the Python 3.12.13 environment and passed `uv pip check`. |
| Flutter | Flutter 3.44.8 stable | **Blocked in current WSL environment.** Direct Flutter launcher fails because `/mnt/d/flutter/bin/internal/shared.sh` contains CRLF line endings. No Flutter result is claimed from this environment. |
| Dart | Dart 3.12.2 | **Not independently verified in current WSL environment.** The Flutter SDK launcher is blocked by the same CRLF issue. |
| Android build configuration | Java 17, Gradle 9.1.0, AGP 9.0.1, Kotlin 2.3.20 | **Not verified in current WSL environment.** No Android build result is claimed from this verification pass. |
| Development database | SQLite for isolated tests; PostgreSQL 16 Compose service for development | SQLite backend tests passed in Python 3.12. Docker Engine is available and the backend Docker image builds successfully; PostgreSQL Compose execution was not tested in this pass. |

The lower Dart SDK constraint in `mobile/pubspec.yaml` is aligned with the already-resolved lockfile. The lockfile remains the exact dependency selection for the mobile project.

## Commands

Run backend commands from `backend/`:

```bash
python -m pytest
```

On WSL installations where only `python3` is available:

```bash
python3 -m pytest
```

Run Flutter commands from `mobile/`:

```bash
flutter pub get --enforce-lockfile
flutter analyze
flutter test
```

A development-only Android smoke build may be run when Java 17 and the Android SDK are available:

```bash
flutter build apk --debug \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

The debug build is not a release-readiness or signing check.

## Dependency policy

`backend/requirements.txt` remains the direct dependency declaration. `backend/requirements.lock` contains the resolved transitive Linux/Python 3.12 dependency set and hashes used by the Dockerfile and CI.

The lock keeps `bcrypt==3.2.2` because the existing Passlib 1.7.4 integration has a known compatibility requirement documented by the Phase 0 baseline. This is a resolution constraint, not a new application dependency.

Do not install packages into the repository, use the local application database, or copy local environment files into CI. Regenerate the Python lock only from the approved direct requirements and target runtime. Regenerate `mobile/pubspec.lock` with the supported Flutter/Dart toolchain rather than editing it by hand.

## Test isolation

Backend tests set `DATABASE_URL` before importing the application and use a temporary SQLite database containing synthetic data. The local `backend/scamshield.db` is never used by the test suite. The fixture recreates its tables per test and the temporary directory is removed when the test process exits.

The test suite does not use customer data, production credentials, uploaded evidence, or external services. The Compose PostgreSQL service is development-only and is not required for the current component tests.

## API and product boundaries

The current unversioned endpoints remain the compatibility baseline. The planned `/v1` API is documented in `api-contracts.md` only; Phase 1 does not add or migrate `/v1` endpoints.

The following decisions remain open and must not be invented in documentation or code:

- launch jurisdictions and independently verified regional resources;
- supported languages beyond the current English implementation;
- user-age policy;
- actual staffed human-review operation;
- privacy purposes, processors, data residency, retention periods, and lawful exceptions;
- support and security-disclosure contacts.

Current heuristic, media metadata, authentication, and storage limitations remain explicitly disclosed. No Phase 1 document changes those behaviors.

## CI boundary

`.github/workflows/ci.yml` runs non-production backend and Flutter checks only. It has read-only repository permissions, uses synthetic test data, does not receive production credentials, does not publish artifacts, and does not deploy.

Third-party actions are referenced by immutable commit SHA with a human-readable release comment. Review action changes before updating those SHAs.

## Verification record

The following is the Phase 1 verification record. A check is marked passed only when its command actually completed successfully.

| Check | Working directory | Result |
| --- | --- | --- |
| Phase 0 HEAD/origin/status verification | repository root | **Passed.** `HEAD` and `origin/main` both resolve to `ec3a77cb21dbb4f982dde02df28c33dd3fb6a6ef`, whose commit subject remains `chore: establish ScamShield project baseline`. The current worktree contains the Phase 1 files listed below; it is not clean because Phase 1 remains uncommitted. |
| Python locked dependency installation | `backend/` | **Passed.** A Python 3.12.15 Docker environment installed all dependencies from `requirements.lock` with `--require-hashes`. The Phase 1 Docker image also built successfully. |
| Python lock dependency check | `backend/` | **Passed through Docker installation.** The Phase 1 Docker build completed successfully using the hash-locked `requirements.lock`. A separate `uv pip check` was not rerun in the current environment. |
| Backend tests | `backend/` | **Passed.** A Python 3.12.15 temporary Docker environment installed the locked dependencies and collected 39 tests; `39 passed` in 15.97 seconds, with two deprecation warnings. |
| System Python backend attempt | `backend/` | **Unavailable on the default interpreter.** `python3` is Python 3.10.12 and `python3 -m pytest` failed with `No module named pytest`. A system-Python lock dry run also rejected `websockets==17.1` because it requires Python >=3.11. The supported Python 3.12 environment above was used for the actual check. |
| Flutter lockfile validation | `mobile/` | **Blocked.** The current WSL Flutter launcher fails before Flutter can execute because `/mnt/d/flutter/bin/internal/shared.sh` contains CRLF line endings. |
| Flutter analyzer | `mobile/` | **Blocked.** Flutter could not start because of the SDK CRLF launcher error. |
| Flutter tests | `mobile/` | **Blocked.** Flutter could not start because of the SDK CRLF launcher error. |
| Android Gradle wrapper check | `mobile/android/` | **Not verified in current pass.** |
| Android debug build | `mobile/` | **Blocked.** Flutter could not start because of the SDK CRLF launcher error. |
| CI YAML validation | repository root | **Passed for static validation.** PyYAML 5.4.1 parsed `.github/workflows/ci.yml`; required jobs/permissions and all four third-party action references were checked, and each action used a 40-character commit SHA. `actionlint`/`yamllint` were not installed. |
| Compose YAML validation | repository root | **Passed for static validation.** PyYAML 5.4.1 parsed `docker-compose.yml` with `services` and `volumes` top-level sections. |
| Docker/backend image validation | `backend/` | **Passed.** Docker Engine is available in WSL. `docker build -t scamshield-backend-phase1 .` completed successfully using Python 3.12 and the hash-locked dependencies. PostgreSQL Compose execution was not tested in this pass. |

The direct WSL `flutter` and `dart` launchers were not usable because `/mnt/d/flutter/bin/internal/shared.sh` contains CRLF line endings (`$'\r': command not found`). The installed Windows `.bat` launcher was callable and was used for all Flutter and Android checks above.

## Approved Phase 1 file scope

Final scope review found only these Phase 1 files changed or created:

- `.github/README.md`
- `.github/workflows/ci.yml`
- `README.md`
- `backend/Dockerfile`
- `backend/pytest.ini`
- `backend/requirements.lock`
- `backend/tests/conftest.py`
- `backend/tests/test_api.py`
- `docs/api-contracts.md`
- `docs/development-baseline.md`
- `mobile/README.md`
- `mobile/pubspec.yaml`
- `mobile/test/api_service_test.dart`
- `tests/README.md`

## Out of scope for this baseline

- secure sessions, refresh rotation, revocation, verification, or recovery;
- production secret enforcement;
- database migrations or new models;
- privacy export/deletion/retention workflows;
- new assessment, report, catalog, evidence, staff, notification, or learning features;
- release signing, iOS, deployment, or store readiness.
