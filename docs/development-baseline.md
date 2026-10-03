# Development Baseline

## Status

This document records the Phase 1 reproducible development baseline.

It does not claim:

- production readiness;
- security-audit completion;
- release readiness;
- store readiness;
- passing checks that were not actually executed.

Phase 0 remains the repository-establishment commit:

- Commit: `ec3a77cb21dbb4f982dde02df28c33dd3fb6a6ef`
- Branch: `main`
- Remote: `origin/main`

Phase 1 does not introduce application features, authentication/session changes, database migrations, deployment changes, or production configuration.

---

## 1. Supported Development Matrix

| Area | Supported Baseline | Verification |
| --- | --- | --- |
| Backend runtime | Python 3.12 | Verified through a Python 3.12.15 Docker environment. |
| Backend dependencies | `backend/requirements.lock` | Installed successfully with `--require-hashes`; Docker image build completed successfully. |
| Flutter | Flutter 3.44.8 stable | Verified on Windows using `D:\flutter\bin\flutter.bat`. Analyzer and Flutter tests passed. |
| Dart | Dart 3.12.2 | Supported by the Flutter 3.44.8 toolchain and existing mobile lockfile. |
| Android | Java 17, Gradle 9.1.0, AGP 9.0.1, Kotlin 2.3.20 | Android debug APK build completed successfully on Windows. |
| Development database | SQLite for isolated tests; PostgreSQL 16 for development | SQLite backend tests passed. PostgreSQL Compose execution was not run during this verification pass. |
| Docker | Docker Engine with Linux containers | Docker Engine was available and the backend image built successfully. |

### Flutter environment note

The Flutter SDK mounted into WSL contains CRLF line endings in:

```text
/mnt/d/flutter/bin/internal/shared.sh