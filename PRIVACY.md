# Development data-handling record

**This is not a production privacy policy, legal notice, compliance claim, or legal advice.** It describes the inspected implementation and identifies decisions required before real-user operation.

## Current source behavior

- Registration accepts an email address and password. The backend stores an email address and password hash; the password is submitted to the configured authentication endpoint.
- The mobile client stores its bearer token in SharedPreferences, not OS-protected credential storage.
- Successful text/URL analysis stores the submitted text with a user identifier, score, verdict, and timestamp. Text-history queries are scoped to the authenticated user.
- Media is sent to the configured backend after the user submits it. The current routes return metadata and a hash; they do not implement durable business-record storage of media or media history.
- The older upload path uses framework-managed uploaded files, which may involve temporary storage. Proxy/server buffering and deployed infrastructure have not been inspected. Do not claim uploaded bytes can never touch disk.
- Current media results remain in the mobile screen session and disappear on history refresh/restart.
- Account deletion, export, configurable retention, explicit saved-analysis consent, and a production consent-management workflow are not implemented.

No deployment, processor inventory, production logging policy, infrastructure encryption configuration, data residency, or backup policy has been verified. This document does not make promises about those unverified systems.

## Repository boundary

The local application database, environment files, signing material, private runtime files, and generated artifacts are not intended for Git. Their exclusion does not delete local data or implement application-level deletion.

Phase 0 did not inspect database contents or use customer data. Future tests must use isolated synthetic data.

## Planned product requirements

- Minimize collection and explain what will be sent before submission.
- Do not request passwords, PINs, OTPs, payment security codes, or wallet seed phrases as report evidence.
- Keep public educational content separate from private assessments, reports, and evidence.
- Provide explicit saving/consent choices, privacy controls, export, and deletion.
- Keep notifications generic and redact sensitive operational logging.
- Define and enforce retention across database records, evidence originals/previews, exports, queued jobs, and backup-restoration procedures.
- Do not use private submissions for model training by default.
- Provide accurate platform-store disclosures based on actual SDK and service behavior.

These are requirements, not implemented guarantees.

## Decisions still required

The owner must approve launch jurisdictions, user-age policy, actual service operators/processors, staff access, data residency, consent purposes, retention periods, lawful exceptions, backup handling, and any third-party analysis integration.

No retention duration, legal basis, support address, privacy contact, or compliance status is invented here. A suitable production privacy policy and store declarations must be prepared and reviewed against the implemented service before launch.

See `docs/current-state.md`, `docs/implementation-blueprint.md`, and `SECURITY.md`.
