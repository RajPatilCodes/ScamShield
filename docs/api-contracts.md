# ScamShield API contracts

## Contract status

This document freezes the current implemented API for Phase 1 development compatibility and records the approved future boundary. It is not an OpenAPI implementation, a production SLA, or a claim that the planned `/v1` operations exist.

Current routes are unversioned. No `/v1` endpoint is added by Phase 1.

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

### `POST /auth/register`

Request content type: `application/json`.

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Current validation:

- email is standards-aware validated and stored lowercase;
- password length is 8–128 characters;
- the current schema does not reject unknown fields;
- no email verification is performed.

Success: HTTP `201`.

```json
{
  "access_token": "<server-issued-token>",
  "token_type": "bearer"
}
```

The current endpoint issues a bearer token immediately. There is no server-tracked session or refresh-token contract yet.

### `POST /auth/login`

Uses the same request and response fields as registration.

Success: HTTP `200`.

Invalid credentials: HTTP `401` with a sanitized `detail` message.

The current endpoint has no refresh, rotation, revocation, device, or session-list behavior.

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

Future modules include identity/sessions, catalog/resources, assessments, reports, timelines, evidence, checklists, notifications, privacy jobs, support, and scoped staff operations. They are not implemented by this baseline.

The exact future error envelope, session/refresh response shape, pagination cursor encoding, idempotency header name, and concurrency field require approval before Phase 2 implementation. This document does not invent those details.

## Flutter integration contract

The current Flutter client uses `ApiService` with these rules:

- `API_BASE_URL` is supplied at build/run time with `--dart-define`;
- the current Android emulator default is `http://10.0.2.2:8000`;
- deployed builds must use HTTPS;
- current routes are the unversioned routes documented above;
- bearer tokens are sent in `Authorization` headers;
- requests time out after 90 seconds;
- failed or malformed authentication responses do not create a local session;
- failed analysis requests do not fabricate a `ScanResult`;
- media uploads are client-prechecked at 20 MiB but remain server-validated;
- media results must preserve the `unverified`/metadata-only semantics;
- URLs are sent as text and are not opened by the API client.

The current token is stored in `SharedPreferences` and logout only removes the local token. This is a known Phase 2 security item, not a Phase 1 contract change.

Future Flutter `/v1` integration must use typed DTOs, server timestamps and assessment versions, server-authoritative ownership/status, explicit unknown/error states, and reauthorization before opening private destinations.
