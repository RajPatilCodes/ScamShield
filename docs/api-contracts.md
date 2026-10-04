# ScamShield API contracts

## Contract status

Phase 2 versions authentication/session operations only. The analysis, history, media, upload and health paths and product contracts below remain the Phase 1 contracts. This is not a production SLA or a claim that other planned `/v1` modules exist.

Authentication uses `/v1/auth`; legacy `/auth/register` and `/auth/login` are no longer available. Other current routes remain unversioned.

Common current error responses are FastAPI responses of the form:

```json
{"detail": "human-readable error"}
```

Clients must not rely on the wording of error details for authorization or security decisions.

## Current backend contract

### `GET /health`

Returns HTTP `200`:

```json
{"status": "ok"}
```

This is a static liveness response. It does not establish database readiness.

### `POST /v1/auth/register`

Request content type: `application/json`.

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Authentication validation:

- email is standards-aware validated and stored lowercase;
- email length is at most 255 characters;
- password length is 8–1,024 characters, with a 4,096-byte UTF-8 cap;
- unknown write fields are rejected;
- registration requires single-use email verification before login can create a session.

Success: HTTP `201`.

```json
{
  "message": "If eligible, check your email for further instructions."
}
```

New and duplicate requests return the same acknowledgement. Registration never creates an authenticated session or returns an access/refresh credential. Development/tests capture verification messages in memory; responses do not include challenge secrets.

### `POST /v1/auth/login`

Uses the same credentials request as registration. Active verified accounts with valid passwords receive:

```json
{
  "access_token": "<ten-minute-access-JWT>",
  "token_type": "bearer",
  "refresh_token": "<opaque-single-use-credential>",
  "session_id": "<UUID>",
  "expires_in": 600
}
```

Success: HTTP `200`.

Invalid credentials: HTTP `401` with a sanitized `detail` message.

Invalid, unknown, unverified and inactive accounts have the same sanitized authentication failure. Five failed logins per account+connection-IP in fifteen minutes block further login attempts with `429` / `Retry-After` until expiry. Forwarded-IP headers are not trusted for these buckets.

### Other implemented authentication/session routes

| Method/path under `/v1/auth` | JSON request | Success |
| --- | --- | --- |
| `POST /verification/request` | `{"email":"user@example.com"}` | `202`, generic acknowledgement |
| `POST /verification/confirm` | `{"token":"<challenge>"}` | `204`, no session created |
| `POST /recovery/request` | `{"email":"user@example.com"}` | `202`, generic acknowledgement |
| `POST /recovery/confirm` | `{"token":"<challenge>","password":"<replacement>"}` | `204`, all account sessions revoked |
| `POST /refresh` | `{"refresh_token":"<credential>"}` | `200`, rotated login response shape |
| `POST /logout` | `{"refresh_token":"<credential>"}` | `204`, idempotent family revocation |
| `GET /sessions` | Access bearer header | `200`, `{"items":[{"id":"<UUID>","created_at":0,"idle_expires_at":0,"absolute_expires_at":0}]}` |
| `DELETE /sessions/{session_id}` | Access bearer header | `204`; non-owner/unknown IDs return `404` |

Session-list timestamps are Unix seconds; only the owner's currently live sessions are included. Recovery challenges expire after thirty minutes; verification expiry is explicitly configured. Both purposes are single-use and cannot be interchanged. Challenge requests share the approved three-per-fifteen-minute account+IP protection. Recovery delivery outages retain a generic response and log only a sanitized operational event; they do not commit an undelivered challenge.

Refresh has a seven-day idle and thirty-day absolute boundary. Each success atomically consumes its credential and creates one successor. Confirmed reuse revokes the entire family; a concurrent loser therefore invalidates the winner's returned credentials too. Unknown/expired/revoked refresh credentials are rejected; no additional numeric refresh limit was invented.

Logout accepts a current or consumed family credential solely to revoke it, including after a lost refresh response. Unknown credentials also return `204`. This does not grant authentication. All authentication responses use `Cache-Control: no-store`; sanitized errors retain the `detail` envelope. See `phase-2-authentication.md` for configuration and test evidence.

### `POST /analysis/analyze`

Authentication:

```http
Authorization: Bearer <access_token>
```

Request:

```json
{
  "content": "Urgent: verify this message"
}
```

Current validation:

- content is trimmed;
- blank content is rejected;
- maximum content length is 10,000 characters;
- URLs are submitted as text and are not fetched or browsed.

Success: HTTP `200`.

```json
{
  "score": 20,
  "verdict": "low-risk",
  "flags": ["urgent language"]
}
```

The score is a deterministic heuristic warning score, not a calibrated probability, verified fraud finding, identity assertion, or safety guarantee. Current verdict thresholds are:

- `low-risk`: score below 30;
- `suspicious`: score 30–59;
- `high-risk`: score 60 or higher.

A successful text analysis is currently saved automatically. Explicit save consent, model/version metadata, and persisted explanation signals are not implemented in this phase.

### `GET /analysis/history`

Authentication is required.

Query parameters:

| Parameter | Current rule |
| --- | --- |
| `page` | Integer, minimum 1, default 1 |
| `page_size` | Integer, 1–100, default 20 |
| `search` | Optional text, maximum 200 characters |

Response:

```json
{
  "items": [
    {
      "id": 1,
      "content": "message text",
      "score": 20,
      "verdict": "low-risk",
      "flags": [],
      "created_at": "2026-01-01T00:00:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

The current query applies an authenticated-user predicate. Media results are not included, and the stored analysis record does not retain the original flags.

### `POST /analysis/media`

Authentication is required.

Multipart requirements:

- content type `multipart/form-data`;
- exactly one file part named `file`;
- maximum media content size 20 MiB;
- server-allowlisted image/video MIME types and extensions;
- basic signature consistency check.

Success response:

```json
{
  "filename": "photo.png",
  "content_type": "image/png",
  "size_bytes": 1234,
  "sha256": "<sha256-of-bytes>",
  "verdict": "unverified",
  "flags": ["metadata screening limitation"],
  "actions": ["verify the source"],
  "malware_scanned": false
}
```

This route performs bounded metadata/signature screening only. It does not perform antivirus scanning, OCR, image interpretation, video frame analysis, or deepfake verification. The result does not establish that a file is safe. The current route does not persist media history.

### `POST /analysis/upload` — legacy

This is an older authenticated upload contract retained for compatibility documentation only.

It currently uses a 25 MiB limit and returns different fields:

```json
{
  "filename": "photo.png",
  "content_type": "image/png",
  "size": 1234,
  "hash": "<sha256-of-bytes>",
  "risk": 0,
  "verdict": "unverified",
  "flags": [],
  "actions": []
}
```

The Flutter client uses `/analysis/media`, not this route. Phase 1 does not merge, remove, or expand either upload route. Later assessment/evidence work must replace this competing contract deliberately.

## Request and response rules for current clients

- Use `application/json` for JSON requests.
- Send bearer authentication only when the endpoint requires it.
- Treat `401` as a session failure, not as proof that an account does not exist.
- Treat `413`, `415`, and `422` as input/limit/validation failures.
- Treat timeouts, malformed JSON, and unavailable services as unknown/failure states; never convert them to safe results.
- Do not cache private responses publicly.
- Do not send passwords, PINs, OTPs, payment security codes, seed phrases, or private evidence as analysis content.
- Do not use a filename, MIME type, hash, phone format, or heuristic score as proof of identity or truth.

## Future `/v1` boundary — documentation only

The approved target API namespace is `/v1`. Phase 1 records the following rules for future implementation without creating routes:

- strict schemas with unknown write fields rejected;
- authenticated owner derived on the server;
- private list/detail/search/count operations owner-filtered in database access;
- bounded cursor pagination for future private collections;
- idempotency keys for retry-prone mutations;
- optimistic concurrency for editable objects;
- server-owned status, severity, verification, ownership, and storage fields;
- sanitized stable error codes rather than security-sensitive detail leakage;
- no publicly cached private response;
- approved resource IDs instead of arbitrary user-controlled trusted destinations;
- no automatic submitted-URL browsing;
- explicit unknown/failure analysis states;
- versioned assessment explanations and capability disclosures.

Future non-authentication modules include catalog/resources, assessments, reports, timelines, evidence, checklists, notifications, privacy jobs, support, and scoped staff operations. They are not implemented by Phase 2. Authentication/session operations are limited to the implemented contract above.

Phase 2 authentication's response shape and sanitized `detail` errors are specified above. Pagination cursors, idempotency headers, concurrency fields, and general contracts for future non-authentication modules are not implemented by Phase 2.

## Flutter integration contract

The current Flutter client uses `ApiService` with these rules:

- `API_BASE_URL` is supplied at build/run time with `--dart-define`;
- the current Android emulator default is `http://10.0.2.2:8000`;
- deployed builds must use HTTPS;
- authentication routes use `/v1/auth`; analysis/media/history routes remain unversioned;
- bearer tokens are sent in `Authorization` headers;
- requests time out after 90 seconds;
- failed or malformed authentication responses do not create a local session;
- failed analysis requests do not fabricate a `ScanResult`;
- media uploads are client-prechecked at 20 MiB but remain server-validated;
- media results must preserve the `unverified`/metadata-only semantics;
- URLs are sent as text and are not opened by the API client.

Access tokens remain in memory. API-bound refresh credentials use OS-protected storage, and the legacy SharedPreferences bearer key is removed. Session restoration rotates the stored credential. Refresh is coordinated, `401` handling is centralized, and invalidation removes all private navigation/screen state. Logout requires server revocation; an offline pending revocation is shown honestly and cannot restore a session.

Future Flutter `/v1` integration must use typed DTOs, server timestamps and assessment versions, server-authoritative ownership/status, explicit unknown/error states, and reauthorization before opening private destinations.
