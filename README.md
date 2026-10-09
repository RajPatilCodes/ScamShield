# ScamShield

## Current capabilities and local APK

- Branded ScamShield Android launcher name and original shield icon.
- Edge-to-edge Material 3 interface, dark mode, dashboard, scan, history and profile.
- Authenticated transient text/URL heuristics; explicitly consented saving and searchable owner-scoped history.
- Camera photos and gallery images/videos, up to 20 MiB, uploaded for metadata screening.
- Media screening checks file type/signature consistency and computes SHA-256. It does not perform OCR, inspect video frames, or scan for malware. An unverified result does not mean safe.
- Authentication and network errors are shown honestly; no simulated successful login.

Verified Phase 3 debug APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`.
Debug HTTP is restricted to the Android emulator address `http://10.0.2.2:8000`. Non-debug credential flows require HTTPS. There is no preset account: register, verify email, then sign in. Older release artifacts are not evidence of Phase 2 security. This app is not a standalone offline antivirus or a production deployment.

The Phase 0 handoff recorded historical backend and mobile validation results, but Phase 1 reruns and records checks separately. Camera use has not been tested on a physical device. See `docs/development-baseline.md` and `mobile/README.md` for current setup and verification status.

ScamShield is a privacy-first mobile app that analyzes suspicious messages and URLs, explains the risk, and gives safe next steps.

## Stack

- Flutter + Material 3 mobile client
- FastAPI + SQLAlchemy backend
- SQLite for local development; PostgreSQL-compatible SQLAlchemy setup for deployment
- JWT authentication

## Run the backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# WSL/Linux: source .venv/bin/activate
pip install --require-hashes -r requirements.lock
# Configure the explicit authentication inputs and migrate a disposable
# development database as described in docs/phase-2-authentication.md.
uvicorn app.main:app --reload
```

Open API docs at `http://127.0.0.1:8000/docs`.

## Run the Flutter app

```bash
cd mobile
flutter pub get --enforce-lockfile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

For a physical Android device, use a reachable HTTPS API. Build a release APK with:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example.com
```

## Verification and security notes

Run `python -m pytest` from `backend/`, and `flutter analyze` plus `flutter test` from `mobile/`. The supported baseline, actual results, and unavailable-toolchain gaps are recorded in [`docs/development-baseline.md`](docs/development-baseline.md). Current request/response behavior and future `/v1` boundaries are documented in [`docs/api-contracts.md`](docs/api-contracts.md).

Phase 2 adds `/v1/auth` verification/recovery, Argon2id password hashing, rotating server-tracked sessions, authentication abuse limits, secure mobile storage, and explicit Alembic migrations. Analysis/media/upload routes keep their existing contracts. See [`docs/phase-2-authentication.md`](docs/phase-2-authentication.md) for configuration, synthetic email capture, database safety, exact verification results, and remaining gaps. The detector is a safety aid, not a guarantee; users should verify important requests independently.

## Phase 3 privacy and ownership

Text checks are transient by default. Explicit saving requires current product consent and expires after 90 days. Profile → Privacy and data provides consent controls, individual/bulk deletion, versioned JSONL export, and account deletion. Export creation/download and bulk/account deletion require separate five-minute single-use password confirmations.

The `/v1/auth` implementation, scoring and upload/media processors are preserved. The intentional change is removal of automatic text persistence; privacy operations use `/v1/privacy`. Run migration `0003` only against an explicitly confirmed target and run the bounded maintenance process for jobs and the daily 02:00 UTC purge. See [`docs/phase-3-privacy.md`](docs/phase-3-privacy.md) and [`docs/privacy-operations.md`](docs/privacy-operations.md) for exact configuration, commands, verification and external-policy boundaries. This is not a production privacy notice or production-readiness claim.

Configure the independent `PRIVACY_AUTHORITY_PATH` and explicitly initialise its checkpoint for first deployment as described in the runbook. Missing/stale restoration authority blocks private activation and maintenance; restored environments use trusted reconciliation rather than fresh bootstrap.
