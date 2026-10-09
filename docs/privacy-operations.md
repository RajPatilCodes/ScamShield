# Privacy operations

This is an implementation runbook, not a legal privacy notice or production deployment approval. Use synthetic/disposable targets for verification. Production scheduling, backup retention and processor obligations require their own operational review.

## Configuration

`app.privacy_config.PrivacySettings` declares every operational limit. Environment overrides use `PRIVACY_` plus the uppercase field name; examples are `PRIVACY_ANALYSIS_DAYS`, `PRIVACY_EXPORT_MAX_BYTES`, `PRIVACY_POLL_SECONDS`. Approved baseline values are listed in `phase-3-privacy.md`. No Phase 2 authentication setting/limiter is changed. Fixed-day retention uses seconds, not calendar-year arithmetic.

Configure the existing explicit authentication inputs first. Database migration requires an explicit `DATABASE_URL` and identical `MIGRATION_DATABASE_URL`. The protected `scamshield.db`, aliases and unknown-schema adoption remain guarded. Never run tests or maintenance against customer data merely to verify this implementation.

`PRIVACY_AUTHORITY_PATH` designates a separate trusted fencing ledger (SQLite via the standard library). It has no default and is never created by API startup. Its parent must already exist. All API/maintenance processes for one database must use the same authority. Keep its access restricted and preserve it independently of application-database restores; selecting its actual infrastructure/backup retention is an operational decision, not an implementation policy. An unavailable ledger or identity/revision/content mismatch closes authentication/private routes with sanitized `503` and blocks job processing/purge. Static `/health` remains liveness only.

## Migration

```text
python -m alembic upgrade head
```

Revision 0003 adds lifecycle identity, privacy tables and analysis foreign keys/expiry/provenance. Passwords, original timestamps, original analysis values and Phase 2 credential rows are preserved. SQLite CURRENT_TIMESTAMP schema defaults establish UTC for baseline timestamps. Other ambiguous naive legacy timestamps fail preflight. Only after an explicit source-specific resolution may `PRIVACY_LEGACY_TIMEZONE=UTC` or Alembic's programmatic `legacy_timezone` attribute be supplied. This is not a blanket timezone assumption. Orphans/malformed timestamps fail without partial migration. Destructive downgrade remains rejected.

SQLite table rebuilding defers foreign-key checks during the single transaction, verifies the complete final graph, then clears stale deferred DROP-parent counters. Foreign-key enforcement is not disabled. Populated Phase 2 credential preservation is tested.

For the initial migration, explicitly bootstrap an empty authority once:

```text
python -m app.privacy_maintenance --init-authority
```

This refuses an existing ledger, local authority checkpoint or existing deletion intent; do not use bootstrap to activate a restore. Migration adds the local checkpoint table but does not assert that restoration fencing is available. API access stays closed until the configured authority and checkpoint agree.

## Jobs and daily purge

```text
python -m app.privacy_maintenance --dry-run
python -m app.privacy_maintenance --once
python -m app.privacy_maintenance
```

Dry-run reports due-job count and approved configuration without mutation. `--once` processes one bounded batch per due job and drains expiry cleanup through bounded queries/transactions. The long-running mode checks due jobs every five minutes and drains the daily purge at 02:00 UTC; startup after that time catches up the day's purge. Scheduler sleep is aligned to UTC polling and the next purge deadline. The process must actually be operated; documentation alone does not purge data.

Each source query/purge batch is at most 100 records. Export work uses transaction-scoped PostgreSQL advisory slots for the global two-job bound; SQLite serializes writers. Job row locks and committed progress make process death resumable without a speculative timeout lease. The account limit is one active export. Export staging is capped at 100,000,000 bytes, expires after 24 hours, and never silently truncates. Stored transport chunks are bounded by the approved export byte cap divided by batch size; no extra transport limit is selected. Source changes/deletion invalidate publication/download; source expiry can make staging unavailable sooner.

Private reads enforce logical expiry even before purge. Cleanup removes expired analyses/consent/audit/grants/operations/rate buckets and export chunks/statuses. Session-family replay evidence is retained until the unchanged Phase 2 absolute lifetime; cleanup does not shorten a live family's replay protection.

## Retry and failure

Automatic retries use one-minute initial exponential delay, one-hour cap, and at most five retries. Due times/counts are persistent. Polling and occupied worker slots can delay execution past eligibility. Exhaustion is `failed`, never successful deletion, and never reactivates an account.

Authorized maintenance operators can explicitly retry unresolved intent:

```text
python -m app.privacy_maintenance --retry-marker <server-marker-uuid>
python -m app.privacy_maintenance --retry-job <retained-failed-job-uuid>
```

These are privileged local maintenance commands, not staff/support product APIs. Deletion retry reconstructs unresolved work, including after status expiry, without resetting the consumed automatic budget or account restriction. Export retry locks/refetches the owner/job, requires unchanged lifecycle/revision/generation, unexpired original source/staging/status deadlines and no conflicting active export. It rebuilds staging through bounded cleanup from the original source boundary; it does not renew deadlines, retry budget or terminal status timestamps. A manual retry can succeed after infrastructure repair; further failures remain failed when that budget is exhausted. Workers recheck the persisted eligibility deadline after locking/refetching; a concurrent postponement prevents processing.

Completed/failed job status expires 30 days after its original terminal event. Staging expiry/cancellation does not restart that clock. The minimal unresolved deletion marker survives status removal, retains scope/generation/retry budget, and can reconstruct remaining purge. Existing cancelled/expired staging is removed in bounded batches. Application-data completion is only recorded after dependencies are gone. Audit and minimal lifecycle/status records have their separately approved retention.

## Account deletion and status

Acceptance immediately restricts the account, advances fencing state and revokes sessions. There is no grace/cancellation. Account child purge avoids holding the parent User lock while deleting authentication children, accommodating existing recovery/refresh lock ordering. New registration after purge receives a new UUID lifecycle; stale jobs never adopt a reused integer user ID.

The mobile client stores an API/account-session-bound random status receipt before submission; the server stores only its keyed digest. A new registration/session does not reuse a prior account's deletion receipt. Receipt possession authorizes sanitized status, not login, private-data access, cancellation or retry. Unknown/expired status is unavailable, not success. A timeout/connection failure is explicitly uncertain. Existing synthetic capture messages are removed in the handling process; capture remains process-local/nonproduction and other synthetic capture processes require separate clearing/restart.

## Restoration and external boundaries

Private activation and maintenance programmatically compare the independent authority's identity, monotonic revision and marker-content digest with the local checkpoint and complete local marker contents. Missing/empty/stale local markers are not evidence of a current restore. A different authority identity, stale checkpoint, missing ledger or inconsistent ledger contents fails closed. New/updated deletion intent is committed to the authority before the application transaction; an interruption between commits also leaves activation closed, rather than losing accepted intent.

For a quarantined restore with its original checkpoint identity and the trusted newer authority configured:

```text
python -m app.privacy_maintenance --reconcile-authority
```

Reconciliation refuses a missing/wrong identity, an authority revision older than local state or unknown local intent that would need discarding. It imports trusted markers and restores the checkpoint. Previously satisfied intent is reopened because restored data may need physical purge again; explicitly reconstruct that work with `--retry-marker`. Marker predicates continue blocking restored account authentication, older analysis generations and individual deleted records; publication/download checks lifecycle/revision. No age-only marker purge is implemented. Thirty days is a minimum, not a deadline for unresolved intent.

An old backup cannot carry proof of later deletions by itself. The configured ledger is the trust anchor: rolling it back together with the application database cannot establish freshness. Actual independent preservation, trusted authority selection, backup retention and processor cleanup must be operationally established; local tests do not certify them. Do not claim deleted data has been removed from external backups or email providers.

Unresolved: jurisdiction-specific legal requirements, legal consent wording, actual backup retention, external processor obligations and external infrastructure logging guarantees. Product notices are not legal claims. No lawful retention/deletion exception is invented.
