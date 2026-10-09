# Development data-handling record

**This is not a production privacy policy, legal notice, compliance claim, or legal advice.** It describes the inspected implementation and identifies decisions required before real-user operation.

## Current source behavior

- Registration accepts an email address and password. The backend stores an email address and password hash; the password is submitted to the configured authentication endpoint.
- Mobile access tokens stay in memory. API-bound refresh credentials use OS-protected storage. Separate protected privacy keys hold deletion-status receipts and pending-picker ownership markers; passwords and recent-auth grants are not persisted.
- Text/URL analysis is transient by default. Explicit saving requires current purpose-specific product consent; saved text, score, verdict and timestamps expire after 90 days. Owner/deletion/expiry predicates cover history, counts, detail and export. Original explanation persistence remains later assessment work.
- Media is sent to the configured backend after the user submits it. The current routes return metadata and a hash; they do not implement durable business-record storage of media or media history.
- The older upload path uses framework-managed uploaded files, which may involve temporary storage. Proxy/server buffering and deployed infrastructure have not been inspected. Do not claim uploaded bytes can never touch disk.
- Current media results remain in the mobile screen session and disappear on history refresh/restart.
- Phase 3 implements product consent, private JSONL export, immediate logical deletion and retryable physical purge. Account deletion immediately restricts access and revokes sessions; failure does not undo that restriction. Legacy analyses are explicitly marked as having no retroactive consent.
- Export staging and app-managed private export/cache artifacts expire after 24 hours. Explicitly user-saved export copies are outside later app cleanup. Consent receipts are retained 730 fixed days, redacted audit 365 fixed days, and completed/failed job status 30 days. Unresolved deletion/restoration markers are not age-pruned.

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

Approved implementation inputs are recorded in `docs/phase-3-privacy.md`. Jurisdiction-specific legal requirements, legal consent wording, actual backup retention, external processor obligations and external infrastructure logging guarantees remain unresolved. No lawful deletion exception is invented.

The listed durations are owner-approved implementation inputs, not a legal basis or compliance claim. No support address or privacy contact is invented. Product consent copy is clearly labelled as product wording. A production privacy notice/store disclosure must reflect reviewed service and processor behavior.

An older backup is programmatically blocked from private activation/maintenance until its checkpoint and markers agree with the independently configured authority. Missing/stale authority fails closed. Reconciled markers fence restored accounts, old analysis generations and stale work. Retention and independent preservation of authoritative backup/processor records and actual restore orchestration are operational boundaries, not guarantees established by local tests.

See `docs/current-state.md`, `docs/implementation-blueprint.md`, and `SECURITY.md`.
