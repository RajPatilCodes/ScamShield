# Current implementation assessment

This is a static source assessment for the Phase 0 repository baseline. It is not a claim that current tests, builds, device behavior, or production deployment have been verified.

## Project locations

- `mobile/`: Flutter client, with Android configuration and existing tests.
- `backend/`: FastAPI application, SQLAlchemy models, and existing tests.
- `docker-compose.yml`: development-oriented backend/PostgreSQL setup.
- No iOS project is currently present.

## Implemented behavior

1. Register or sign in using email/password against the backend.
2. Enter a message or URL and receive English keyword-based warning heuristics.
3. Select a camera photo, gallery image, or gallery video and submit it for metadata-only screening.
4. View results, generic safety advice, and recent checks.
5. Load user-scoped saved text history; search/filter the latest 100 entries locally.
6. View a basic profile and remove the local session token on logout.
7. Use system light/dark themes and the existing branded Android launcher resources.

Routing uses imperative Flutter navigation and a four-tab `IndexedStack`. State is local widget state with a shared API service. The only application model is the current screening-result model; there is no incident-report domain yet.

## Existing API

| Endpoint | Current behavior |
| --- | --- |
| `POST /auth/register` | Create user and issue bearer token |
| `POST /auth/login` | Validate email/password and issue token |
| `POST /analysis/analyze` | Authenticate, score text, save raw submitted text, return flags |
| `GET /analysis/history` | Authenticated owner-scoped pagination/search |
| `POST /analysis/media` | Bounded 20 MiB metadata/basic-signature screening |
| `POST /analysis/upload` | Older 25 MiB metadata screening with weaker type validation |
| `GET /health` | Static liveness response, not database readiness |

## Capability limits and defects

- Five regular expressions score urgency, credential/payment terms, links, and selected impersonation terms. This is not calibrated fraud probability, reputation lookup, or verified fraud detection.
- URLs are treated as text, not browsed. There is no dedicated phone inspection, QR decoding, OCR, image interpretation, video content analysis, antivirus, or deepfake verification.
- Backend verdict thresholds are 30/60; mobile colors/filters use 35/70.
- Analysis flags are returned initially but not persisted, so history loses the original explanations.
- Text input is saved automatically. Consent-based optional saving and retention/deletion are not implemented.
- Media results are not stored as history records and disappear on refresh/restart.
- Mobile startup tests token presence rather than restoring a verified session.
- Tokens use SharedPreferences; logout has no server revocation.
- There is no email verification, account recovery, session model, moderation, report/evidence ownership model, or staff console.
- Database setup uses `create_all`, not versioned migrations. Analysis ownership lacks a database foreign key.
- Development secrets/configuration, missing abuse controls, Android debug signing, and the LAN HTTP exception block production readiness.
- Root README names `SECRET_KEY`; the source configuration reads `JWT_SECRET`. Phase 0 preserves the original README rather than changing behavior or setup instructions.

## Tests and artifacts

Existing test source covers basic authentication, text history, upload/media contracts and boundaries, mobile error honesty, media submission, and rendering. It does not establish complete two-user isolation, session lifecycle, or production behavior.

The root README reports historical test/build results. Those results were not reproduced in Phase 0. No application tests, analyzers, dependency installs, builds, or servers were run during repository establishment. The backend test fixture writes a test database and drops/recreates its tables.

An existing APK is present locally under `mobile/build/app/outputs/flutter-apk/`; its provenance, signing, and match to current source are unverified. It is excluded from Git.

The local backend database was identified by path only, not opened. Environment files, local machine configuration contents, and private agent notes were not used for this assessment.

## Toolchain observation

The Dart lower bound in `pubspec.yaml` is broader than the SDK requirements recorded in `pubspec.lock`. The lockfile requires Dart 3.12 or later and Flutter 3.44 or later. Current Android configuration specifies AGP 9.0.1, Kotlin 2.3.20, and Gradle 9.1.0. Compatibility in the current environment remains to be tested in the approved development-baseline phase.

## Planned, not implemented

The target includes reviewed scam guides, guest emergency help, context-aware assessments, private reports and timelines, secure evidence, recovery checklists, trusted resources, notifications, support/moderation, privacy lifecycle controls, iOS, accessibility verification, and production operations. The exact sequence and acceptance gates are in `implementation-blueprint.md`.
