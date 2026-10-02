# ScamShield mobile

Flutter Android client with an original, locally authored shield/S vector launcher icon and the launcher label **ScamShield**.

## Capabilities

- Register/sign in against `/auth/register` and `/auth/login`; real server tokens are required. Network, authentication, and malformed-response errors are shown; there are no fake sessions or demo scan results.
- Text and URL heuristic checks use authenticated `POST /analysis/analyze`. URLs are submitted as text, not browsed by the mobile client.
- Camera photo capture, gallery images, and gallery videos use `image_picker`. Selected files are uploaded only after pressing Analyze. Cancellation, permission errors, upload loading, and oversized files are handled.
- Authenticated multipart `POST /analysis/media` uses field `file`, with a **20 MiB (20,971,520 bytes)** maximum. Supported formats are determined by the server.
- Media results show filename, content type, byte size, SHA-256, `unverified`/`review` verdict, flags, and actions. This is **metadata-only screening**, not malware scanning, OCR, image interpretation, or video content analysis. No result establishes that a file is safe.
- History loads the latest 100 text checks through authenticated `GET /analysis/history`. Media results are held only in the current screen session and disappear on refresh/restart; server media history is not implemented.

## Run

```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

The default API URL targets a local backend from an Android emulator. A physical device needs a reachable API URL. Use HTTPS for deployed builds; release Android cleartext policy may block HTTP. An available backend is required. The release manifest includes INTERNET permission. Camera/gallery access is handled by the platform picker; Android process-death picker recovery is supported.

## Verify and build

```bash
flutter analyze
flutter test
flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example.com
```

Output: `build/app/outputs/flutter-apk/app-release.apk`. The current Gradle release configuration signs with the development debug key; configure your own release signing before distribution. API_BASE_URL is compiled in; without an override the APK targets the emulator address above. iOS camera/photo permission configuration and device testing are outside this Android implementation.

The session token currently uses SharedPreferences, not hardware-backed secure storage. Text scores are warning heuristics, not proof of fraud or safety.
