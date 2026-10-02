# Security status

**Development baseline: not ready for production use.**

This document records current limitations and planned requirements. It is not a security certification, guarantee, supported-release policy, or claim that the planned controls already exist.

## Current implementation

The application provides authenticated text heuristics and metadata-only media screening. Current text-history queries filter by the authenticated user. This does not establish that every future private-data path is secure.

Known release blockers include:

- Development signing-secret defaults and development Compose credentials.
- Root README configuration guidance names `SECRET_KEY`, while the application reads `JWT_SECRET`. The original README is preserved during Phase 0; correcting it belongs to approved implementation work.
- Mobile bearer-token storage in SharedPreferences.
- Local-only logout without server-side session revocation.
- No application-level rate-limit or comprehensive abuse-control implementation.
- No implemented retention/deletion workflow for saved text.
- Debug signing for Android release builds and an HTTP LAN exception in the main network configuration.
- Two upload contracts with different limits and validation strength.

Metadata, filename, MIME type, file signature, and SHA-256 cannot establish that a file is safe or truthful. Keyword scores are not verified fraud findings or calibrated probabilities. Phone formatting must never be represented as proof of identity.

## Disclosure process

A private security-disclosure contact and handling process have **not yet been established**. No response-time commitment or private GitHub reporting capability is claimed here.

Do not publish credentials, customer data, private reports, or evidence in public issues. The repository owner must establish and verify a private reporting channel and handling procedure before a pilot or production release. No support or security email address has been invented for this baseline.

## Repository protection

Environment files, local databases, signing material, build artifacts, local machine settings, and agent state are excluded from the intended source baseline. Ignore rules are defense-in-depth, not proof that source files contain no credentials. Review and scan staged content before committing.

If a real secret is discovered, stop publication, notify the owner through an approved private process, and address rotation/revocation and safe remediation. Never rely on deleting a later copy to remove a secret from Git history.

## Planned security requirements

- Server-derived ownership and authorization on every private object and subresource.
- Scoped staff access, strong staff authentication, and audited transitions.
- Secure sessions, refresh rotation, revocation, verification, and recovery.
- Production startup failure when required secrets are missing or unsafe.
- Strict schemas, bounded requests, rate limits, idempotency, and concurrency control.
- No automatic fetching of arbitrary submitted URLs.
- Private evidence quarantine and isolated, resource-bounded processing.
- No sensitive report content in notifications, routine logs, or analytics.
- Implemented consent, retention, export, and deletion controls.
- Production platform configuration, dependency checks, security testing, and incident procedures.

These controls require implementation and verification under `docs/implementation-blueprint.md`. No production infrastructure or external security assessment is asserted to exist.
