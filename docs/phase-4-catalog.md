# Phase 4: Catalog, emergency guidance, and learning foundation

This document describes the Phase 4 implementation boundary. It is not a claim that the content is officially reviewed, that resources are verified, or that production operations exist.

## Public content boundary

The catalog is public and read-only. It does not expose accounts, assessments, private reports, evidence, checklist progress, or learning progress.

The current publication is an India-first (`IN`) **draft** revision. English is the canonical language. Hindi is supported where translated content exists; the API reports visible English fallback metadata when it does not.

The current bundle contains all 33 guide identifiers (`SC-001` through `SC-033`), but every guide is `pending_editorial_review`. Trusted resources are `unverified` and have no destination until an appropriate source review is completed. The client must not describe these guides as officially approved or these resources as trusted.

A publication may be marked `published` only when every guide, playbook, lesson, and checklist has editorial-review evidence and no resource remains unverified. The importer rejects a published manifest that does not satisfy that gate.

Resource `content_digest` is nullable for draft, unverified, or withdrawn resources that do not have a concrete definition requiring integrity metadata. When present, it is the lowercase SHA-256 digest of the canonical resource-definition payload containing `id`, `language`, `name`, `jurisdiction`, `destination`, `publisher`, and `source_references`. The payload is serialized as UTF-8 JSON with `ensure_ascii=false`, sorted keys, and compact `(',', ':')` separators. Verification state, review dates, withdrawal state, and the digest itself are excluded. A non-null digest must match that payload; a verified resource additionally requires a digest, destination, HTTPS source references, and verification date. A digest never makes a resource trusted or verified.

## API

Public read-only routes are under `/v1`:

- `GET /catalog/categories`
- `GET /catalog/guides`
- `GET /catalog/guides/{guide_id}`
- `GET /catalog/search`
- `GET /emergency/playbooks`
- `GET /emergency/playbooks/{playbook_id}`
- `GET /learning/lessons`
- `GET /learning/lessons/{lesson_id}`
- `GET /checklists`
- `GET /checklists/{checklist_id}`
- `GET /resources`
- `GET /resources/{resource_id}`

List routes use bounded `limit` and opaque `cursor` values. Catalog and search requests accept `language` and `jurisdiction`; guide list/search also accept a bounded `category_id`. Responses expose `language` fallback metadata and public cache headers containing the immutable revision, publication status, and SHA-256 publication digest.

Content is not mutated through the API. Operators validate or import a complete manifest with `app.catalog_content`. The importer validates paths, strict schemas, language/jurisdiction, cross-references, HTTPS destinations, source references, review status, resource verification evidence, and the complete 33-guide inventory before one publication revision is committed.

## Offline and update behavior

Emergency playbooks are bundled in English and Hindi. Bundled content is available to guests without authentication and remains available when the API is offline. If a network response is invalid or unavailable, the client first attempts the last typed-valid cache entry and then the bundled emergency asset. Invalid cache entries are removed rather than treated as trusted content.

A successful network response is cached only after JSON shape/model validation and integrity metadata validation. Cache replacement uses a temporary file and rename, so a failed update leaves the previous cache entry in place. Cached or bundled fallback content is disclosed in the UI as potentially out of date. Failed updates never delete the bundled emergency guidance.

Cached public responses older than seven days, or with a future timestamp, remain usable as last-known-good content but are flagged stale in memory for the UI. Cache writes, removals, and clears are serialized and use unique temporary paths so concurrent catalog requests cannot overwrite one another's temporary file. A cache write failure does not turn an otherwise valid online response into a service failure.

Phase 4 uses HTTPS, immutable publication revisions, and separate SHA-256 digest metadata. A resource-definition digest identifies one canonical resource record; the publication-bundle digest remains the SHA-256 of the complete canonical bundle and is used for immutable revision metadata and cache headers. Signed manifests are intentionally deferred; introducing them would require key custody, rotation, and operational verification procedures.

## Guest checklist and learning

Checklist completion is stored only in an app-local bounded JSON file. It is never sent to the backend, tracked through analytics, or synchronized to an account. Guests can explicitly reset all local checklist progress. Authentication state transitions clear guest progress to prevent it from crossing account boundaries.

Checklist writes include the last known catalog revision when one is available. Local progress operations are serialized, and a write that overlaps an account transition is cleared after the transition check so guest state cannot cross into an authenticated session.

Lessons include small, local-only knowledge checks. Answers are evaluated on-device. No answer or progress data is uploaded.

## Verification boundary

The backend test suite requires the repository's locked Python environment. Flutter analysis and tests use Flutter 3.44.8/Dart 3.12.2 through the existing Windows launcher. Physical Android offline behavior, process death, backup/restore, PostgreSQL integration, external content review, and live official-resource verification remain separate verification work.
