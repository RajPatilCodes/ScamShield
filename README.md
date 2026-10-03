# ScamShield

## Current capabilities and local APK

- Branded ScamShield Android launcher name and original shield icon.
- Edge-to-edge Material 3 interface, dark mode, dashboard, scan, history and profile.
- Authenticated text/URL heuristics and searchable user-scoped history.
- Camera photos and gallery images/videos, up to 20 MiB, uploaded for metadata screening.
- Media screening checks file type/signature consistency and computes SHA-256. It does not perform OCR, inspect video frames, or scan for malware. An unverified result does not mean safe.
- Authentication and network errors are shown honestly; no simulated successful login.

APK: `mobile/build/app/outputs/flutter-apk/app-release.apk`.
This build uses development signing and the default Android emulator backend URL (`http://10.0.2.2:8000`). It is not a standalone offline antivirus or a production deployment. A physical phone needs a rebuild pointing to a reachable HTTPS backend. There is no preset account: register against the running backend.

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
uvicorn app.main:app --reload
```

Open API docs at `http://127.0.0.1:8000/docs`.

## Run the Flutter app

```bash
cd mobile
flutter pub get --enforce-lockfile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

For a physical Android device, replace the URL with the computer's LAN IP. Build a release APK with:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example.com
```

## Verification and security notes

Run `python -m pytest` from `backend/`, and `flutter analyze` plus `flutter test` from `mobile/`. The supported baseline, actual results, and unavailable-toolchain gaps are recorded in [`docs/development-baseline.md`](docs/development-baseline.md). Current request/response behavior and future `/v1` boundaries are documented in [`docs/api-contracts.md`](docs/api-contracts.md).

Set a long random `JWT_SECRET` in production, use HTTPS, move to PostgreSQL, and add rate limiting and abuse monitoring before public release. The detector is a safety aid, not a guarantee; users should verify important requests independently. Phase 1 does not implement production authentication, migrations, or deployment controls.
