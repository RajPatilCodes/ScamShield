# Security status

**Development baseline: not ready for production use.**

This document records current limitations and planned requirements. It is not a security certification, guarantee, supported-release policy, or claim that the planned controls already exist.

## Current implementation

The application provides authenticated text heuristics and metadata-only media screening. Current text-history queries filter by the authenticated user. This does not establish that every future private-data path is secure.

Known release blockers include:

- Deployment/Compose configuration has not been converted to the new explicit authentication settings; production infrastructure was outside Phase 2.
- PostgreSQL integration, live configured SMTP delivery, and physical-device credential-storage behavior have not been verified in this implementation environment.
- Authentication limits cover the approved account+IP login-failure and challenge-request buckets. Broader product/service abuse controls remain future work.
- No implemented retention/deletion workflow for saved text.
- Debug signing for Android release builds; signing infrastructure was outside Phase 2.
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
- Phase 2 implements sessions, refresh rotation/replay revocation, verification/recovery, required access claims, active account/session checks, and production configuration rejection. See the implementation record below.
- Strict schemas, bounded requests, rate limits, idempotency, and concurrency control.
- No automatic fetching of arbitrary submitted URLs.
- Private evidence quarantine and isolated, resource-bounded processing.
- No sensitive report content in notifications, routine logs, or analytics.
- Implemented consent, retention, export, and deletion controls.
- Production platform configuration, dependency checks, security testing, and incident procedures.

These controls require implementation and verification under `docs/implementation-blueprint.md`. No production infrastructure or external security assessment is asserted to exist.

## Phase 2 implementation record

New/replaced passwords use Argon2id with explicit configured costs. Legacy bcrypt is accepted only for complete inputs of at most 72 UTF-8 bytes and is rehashed after successful verified-account login. Longer legacy inputs must use recovery; silently verifying their truncated prefixes is prohibited. General password limits are 1,024 characters / 4,096 UTF-8 bytes.

Access tokens last ten minutes and require subject, session ID, token ID, issuer/audience, access purpose, and timing claims. The backend checks active verified accounts and live owner-matching sessions on every protected request. Refresh credentials are opaque, hashed at rest, single-use, with seven-day idle / thirty-day absolute session expiry. Confirmed replay revokes the session family, including a concurrent winner's successor. Logout and successful recovery revoke server state.

Mobile access tokens stay in memory. Only API-bound refresh credentials and pending-revocation state go to OS-protected storage. Legacy plaintext bearer storage is removed rather than migrated. Failed/uncertain refresh cannot silently retry a consumed credential. Offline logout clears private UI state, retains only a protected pending-revocation credential, visibly reports pending server confirmation, and retries revocation before allowing restoration or another login.

The main Android network policy denies cleartext; the debug resource allows only `10.0.2.2`. Dart credential flows also reject non-debug HTTP and credential redirects. Backup/device-transfer rules exclude secure credential and legacy token preference files. Native OS/device behavior has not been instrumented on a physical device.

Production configuration requires explicit secrets, HTTPS API/CORS, configured TLS PostgreSQL transport, and configured TLS SMTP delivery. Argon2 costs, verification expiry and SMTP timeout require explicit inputs; synthetic test values are not production recommendations. Tests use capture delivery and disposable databases. See [`docs/phase-2-authentication.md`](docs/phase-2-authentication.md) for the full record.
