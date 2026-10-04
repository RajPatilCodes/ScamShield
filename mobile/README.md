# ScamShield mobile

Flutter Android client with an original, locally authored shield/S vector launcher icon and the launcher label **ScamShield**.

## Supported development baseline

- Flutter 3.44.8 stable
- Dart 3.12.2
- Dart SDK constraint: `>=3.12.0 <4.0.0`

The exact dependency selection is committed in `pubspec.lock`. See [`../docs/development-baseline.md`](../docs/development-baseline.md) and [`../docs/api-contracts.md`](../docs/api-contracts.md) for the reproducible checks and API boundary.

## Capabilities

- Register, verify email, sign in and recover passwords through `/v1/auth`. Registration/verification do not create a session. Network, authentication and malformed-response errors are shown; there are no fake sessions or demo scan results.
- Text and URL heuristic checks use authenticated `POST /analysis/analyze`. URLs are submitted as text, not browsed by the mobile client.
- Camera photo capture, gallery images, and gallery videos use `image_picker`. Selected files are uploaded only after pressing Analyze. Cancellation, permission errors, upload loading, and oversized files are handled.
- Authenticated multipart `POST /analysis/media` uses field `file`, with a **20 MiB (20,971,520 bytes)** maximum. Supported formats are determined by the server.
- Media results show filename, content type, byte size, SHA-256, `unverified`/`review` verdict, flags, and actions. This is **metadata-only screening**, not malware scanning, OCR, image interpretation, or video content analysis. No result establishes that a file is safe.
- History loads the latest 100 text checks through authenticated `GET /analysis/history`. Media results are held only in the current screen session and disappear on refresh/restart; server media history is not implemented.

## Run

```bash
flutter pub get --enforce-lockfile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

The default API URL targets a local backend from an Android emulator. Only debug builds allow HTTP, exclusively at `10.0.2.2:8000`; a physical device needs a reachable HTTPS API. Release/profile credential flows reject HTTP, and the main Android network resource denies cleartext. Authentication POSTs do not follow redirects. An available backend is required. The release manifest includes INTERNET permission. Camera/gallery access is handled by the platform picker; Android process-death picker recovery is supported.

## Verify and build

```bash
flutter analyze
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

The debug output is under `build/app/outputs/flutter-apk/`. The current Gradle release configuration signs with the development debug key; configure your own release signing before distribution. API_BASE_URL is compiled in; without an override the APK targets the emulator address above. iOS camera/photo permission configuration and device testing are outside this Android implementation. Phase 1 does not claim release signing or production readiness.

Refresh credentials use `flutter_secure_storage` and OS-protected storage; access tokens stay in memory. The existing `shared_preferences` dependency is retained only to remove the legacy bearer key. Passwords and recovery/verification secrets are never written to session storage. Startup rotates the durable refresh, concurrent requests coordinate refresh, and session invalidation discards the entire private navigation tree. Offline logout visibly records pending server revocation, which must complete before restoration or another login. Secure/legacy credential preference files are excluded from backup and device transfer.

Phase 2 verification: analyzer clean, all 33 Flutter tests passed, Android debug APK built. Native Android Keystore behavior and backup/transfer were not exercised on a physical device; unit tests and source/build configuration checks are not a hardware-backed-storage certification. See [`../docs/phase-2-authentication.md`](../docs/phase-2-authentication.md) for commands, results, dependencies, and gaps. Text scores remain warning heuristics, not proof of fraud or safety.
