# ScamShield

## V2 capabilities and current APK

- Branded ScamShield Android launcher name and original shield icon.
- Edge-to-edge Material 3 interface, dark mode, dashboard, scan, history and profile.
- Authenticated text/URL heuristics and searchable user-scoped history.
- Camera photos and gallery images/videos, up to 20 MiB, uploaded for metadata screening.
- Media screening checks file type/signature consistency and computes SHA-256. It does not perform OCR, inspect video frames, or scan for malware. An unverified result does not mean safe.
- Authentication and network errors are shown honestly; no simulated successful login.

APK: `mobile/build/app/outputs/flutter-apk/app-release.apk`.
This build uses development signing and the default Android emulator backend URL (`http://10.0.2.2:8000`). It is not a standalone offline antivirus or a production deployment. A physical phone needs a rebuild pointing to a reachable HTTPS backend. There is no preset account: register against the running backend.

Validation: backend agent reported 39 passing tests in an isolated environment (with bcrypt 3.2.2 for Passlib compatibility); mobile analyzer and 6 tests passed and release APK built. Camera use has not been tested on a physical device. See `mobile/README.md` for mobile-specific setup.

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
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open API docs at `http://127.0.0.1:8000/docs`.

## Run the Flutter app

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

For a physical Android device, replace the URL with the computer's LAN IP. Build a release APK with:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example.com
```

## Security notes

Set a long random `SECRET_KEY` in production, use HTTPS, move to PostgreSQL, and add rate limiting and abuse monitoring before public release. The detector is a safety aid, not a guarantee; users should verify important requests independently.
