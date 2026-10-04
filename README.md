# ScamShield

## Current capabilities and local APK

- Branded ScamShield Android launcher name and original shield icon.
- Edge-to-edge Material 3 interface, dark mode, dashboard, scan, history and profile.
- Authenticated text/URL heuristics and searchable user-scoped history.
- Camera photos and gallery images/videos, up to 20 MiB, uploaded for metadata screening.
- Media screening checks file type/signature consistency and computes SHA-256. It does not perform OCR, inspect video frames, or scan for malware. An unverified result does not mean safe.
- Authentication and network errors are shown honestly; no simulated successful login.

Verified Phase 2 debug APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`.
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
