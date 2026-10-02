# Scam Shield implementation blueprint

## Status and source of truth

This document preserves the implementation blueprint approved in the project conversation. Phase 0 establishes the repository only. All functionality described as planned remains unimplemented until its phase is built and verified. Existing behavior is recorded separately in `current-state.md`.

The target is a production-quality Flutter + FastAPI scam-risk adviser, emergency-guidance tool, and private incident organizer. It is not a bank, police system, guaranteed fraud detector, universal antivirus, or guaranteed recovery service. Screens alone do not establish completion.

## 1. Existing features

- Flutter Android client with Material 3, system themes, and branded launcher resources.
- Email/password registration/login, dashboard, and basic profile/local logout.
- English keyword-based message/URL screening.
- Camera/gallery selection and metadata-only media screening.
- Result details and user-scoped text history with local filters/search.
- FastAPI/SQLAlchemy, SQLite development default, PostgreSQL Compose configuration.
- Existing backend and Flutter tests, not rerun in Phase 0.

Known defects include insecure durable token storage, no server logout/revocation, inconsistent risk thresholds, lost history explanations, no persisted media history, competing upload contracts, no retention/deletion workflow, and unsafe production defaults. Preserve these as explicit work items rather than concealing them in repository setup.

## 2. Missing capabilities and product boundaries

Planned capabilities: verified authentication/recovery; secure sessions; PostgreSQL migrations; object ownership; staff authorization; reviewed scam catalog; guest emergency help; message, URL, phone, QR and honestly scoped media assessment; context and history; private reports/timelines; secure evidence; recovery checklists; trusted resources; notifications; privacy/export/deletion; support/moderation; audit; abuse limits; retention; Android release readiness; iOS foundation; accessibility; comprehensive tests and production documentation.

Proposed initial boundary: guests can read guides, use emergency playbooks and trusted resources, and keep local checklist progress. Cloud-assisted checks and synced private reports require an account. Do not introduce an anonymous upload service without separately approved abuse controls.

India-aware guidance, including UPI, is part of the catalog, but launch jurisdictions and languages still require confirmation. Resources must be jurisdiction-specific and independently verified. Human-review status must only be exposed if a real staffed operation exists. Otherwise say that a report is saved privately, not that an investigation is underway.

Private reports are not public allegations. Do not build public accusation feeds, scammer leaderboards, payment execution, automatic police filing, broad device surveillance, arbitrary executable uploads, or authoritative AI/deepfake verdicts as part of the initial product.

## 3. Final screen map

| Area | Planned screens |
| --- | --- |
| Startup/auth | Session restoration; optional region/language; sign in; register; verify email; forgot/reset password |
| Home | Dashboard and recent private activity |
| Check | Input type; message/link/phone input; supported media/QR review; context questions; submission/privacy review |
| Result | Warning level, explanations, uncertainty, immediate actions, relevant guides, save/report actions |
| My cases | Private report list; saved assessment history; scoped search/filter |
| Report creation | Incident details; exposure/loss; optional evidence; consent review; confirmation |
| Report detail | Overview; timeline; evidence list/detail; add information; recovery checklist |
| Emergency | Exposure selection; immediate-action playbook; trusted reporting options |
| Learn | Category browser; guide; lesson; knowledge check; safety checklist |
| Search | Public content search, separately scoped private search |
| Notifications | Inbox and authorized internal navigation |
| Account/settings | Profile; language/theme/accessibility; notification preferences |
| Security | Active sessions; credential changes; optional local lock |
| Privacy | Consent/data controls; export request/status; deletion request/status |
| Help/resources | FAQ; support tickets; resource directory; external-handoff confirmation |
| Separate staff console | Assigned queue; report/evidence review; moderation timeline; support; editorial approvals |

Main tabs: Home, Check, My cases, Learn, Settings. Urgent help must remain available without authentication.

Every feature needs typed inputs, server validation, authorization, bounded loading, honest errors, distinct empty states, offline behavior where appropriate, and accessible semantic/focus/text/contrast support. Do not use color alone for severity.

## 4. End-to-end user flows

1. Launch -> restore session -> optional region/language -> home. Guest safety content remains usable.
2. Register -> validate -> verify email -> secure session. Login returns to the intended authorized screen. Recovery uses a single-use challenge and revokes affected sessions.
3. Check -> input -> optional context -> inspect/redact submission -> assess -> result. Show what was checked, limitations, reasons, and immediate actions. Save only through the approved consent choice.
4. Result -> finish, save, urgent guidance, guide, or private report. A phone number alone does not establish identity or fraud.
5. Report -> category/not sure -> incident facts -> exposure/loss -> optional permitted evidence -> consent -> idempotent submission -> private confirmation.
6. My cases -> report -> timeline, follow-up, evidence status, recovery, external resource, complaint reference, export/withdrawal/deletion.
7. Urgent help -> money/code/device/access/threat exposure -> protective steps -> verified local reporting. Safety takes priority over evidence collection.
8. Notification -> authenticate if needed -> fetch authorized current object. Push payloads contain no sensitive report narrative.
9. Logout -> revoke server session -> clear credentials/private caches -> detach device association -> guest home.
10. Account deletion -> recent authentication -> consequences -> revoke sessions -> auditable deletion/status; disclose any approved lawful exception accurately.

Keep assessment results, editorial guides, private incident reports, and service review status separate. Opening an external reporting site does not mean a complaint has been filed.

## 5. Initial scam catalog

Initial catalog target: 33 reviewed guides. First content tranche: SC-001 through SC-006, SC-010 through SC-013, SC-018, and SC-019. Remaining guides are required for the planned initial complete catalog; none are claimed implemented by this document.

| ID | Category | Initial scenario |
| --- | --- | --- |
| SC-001 | Customer support | Fake support number requests payment, codes, or remote access |
| SC-002 | OTP/PIN | Code extraction under a cancellation or security pretext |
| SC-003 | Bank/payment | Urgent transfer to a supposedly safe account |
| SC-004 | UPI requests | Collect request disguised as receiving money |
| SC-005 | QR | Replaced merchant QR or fraudulent refund QR |
| SC-006 | Refund | Fake overpayment followed by repayment pressure |
| SC-007 | Recruitment | Fake job and onboarding/equipment fee |
| SC-008 | Investment/crypto | Relationship-led trading platform and blocked withdrawal |
| SC-009 | Loans | Advance fee, excessive permissions, or loan-app harassment |
| SC-010 | Courier | Fake redelivery or parcel-release payment |
| SC-011 | KYC | Suspension threat and credential/document harvesting |
| SC-012 | Government | Fake benefit, tax, or administrative payment |
| SC-013 | Police/legal | Digital arrest, customs accusation, or security deposit |
| SC-014 | E-commerce | Fake store or off-platform marketplace payment |
| SC-015 | Social media | Hijacked friend, giveaway, or login-code request |
| SC-016 | Romance | Relationship-based emergency and repeated financial demands |
| SC-017 | Phishing | Cloned login and credential/session theft |
| SC-018 | Malicious app | Fake bank/KYC/courier APK and powerful permission requests |
| SC-019 | Remote access | Screen-sharing or remote-control coercion |
| SC-020 | Tech support | Browser virus alert and paid support trap |
| SC-021 | Prize | Advance fee to release lottery or giveaway winnings |
| SC-022 | Subscription | Fake renewal invoice and fraudulent cancellation hotline |
| SC-023 | Business/vendor | Invoice or supplier bank-detail substitution |
| SC-024 | Identity | Document/selfie collection under a false verification purpose |
| SC-025 | AI impersonation | Synthetic family/executive emergency payment demand |
| SC-026 | Task/recharge | Deposits required to unlock tasks or withdraw earnings |
| SC-027 | Recovery | Advance-fee recovery agent targeting an earlier victim |
| SC-028 | Sextortion | Real or fabricated intimate-image threats |
| SC-029 | Telecom takeover | SIM swap or port-out account compromise |
| SC-030 | Crypto approval | Wallet-drainer signature or fake airdrop |
| SC-031 | Payment reversal | Mistaken-payment claim requesting a fresh transfer |
| SC-032 | Discovery poisoning | Fake support in search, advertisements, or AI answers |
| SC-033 | Money mule | Recruitment to receive/forward unexplained third-party funds |

Each published guide must have: stable ID, title, category, realistic scenario, scammer behavior, warning signs, user risk, actions not to take, immediate safe action, recovery steps, evidence checklist, reporting options, severity guidance, affected accounts/data, prevention tips, fictional examples, false-positive considerations, sources, reviewer, version, and review date.

Use inert/non-routable example destinations. Never request sexual imagery as proof. Avoid identity accusations based on appearance, nationality, phone format, or report volume. A scenario's severity guidance is not a client-authorized report priority. Distinguish active compromise/critical danger, high risk, suspicious approach, and insufficient information.

## 6. Backend/API architecture

Keep a FastAPI modular monolith, Flutter client, PostgreSQL, and versioned migrations. Private object storage, a bounded queue, isolated file-processing workers, and a separate staff console are planned components, not existing production infrastructure.

Proposed API version: `/v1`.

| Module | Operations |
| --- | --- |
| Identity/sessions | Register, verify, login, rotate refresh, logout, recovery, list/revoke own sessions |
| Profile/preferences | Read/update own allowed fields |
| Catalog/resources | Published categories, guides, lessons, scoped search, approved regional resources |
| Assessments | Create, explicitly save, owner list/detail/delete |
| Reports | Create/update draft, submit, owner list/detail, follow-up, withdraw |
| Timeline | Owner-visible events; internal notes use separate staff serializers |
| Evidence | Report-bound upload authorization, completion, status, authorized preview/delete |
| Checklists | Published content and owner progress |
| Notifications | Register/revoke device, preferences, inbox/read state |
| Privacy | Consent, export, deletion, retention status |
| Support/staff | Owner tickets; assigned staff replies; review assignments; permitted transitions; editorial approval |

Contract rules: strict schemas, reject unknown write fields, owner from authenticated identity, bounded cursor pagination, sanitized errors, idempotency for retry-prone mutations, optimistic concurrency, and no publicly cached private responses. Use approved resource IDs for trusted navigation rather than arbitrary user URLs.

Assessment output includes warning level, signals, limitations, guidance IDs, version, timestamps, and storage state. Do not present heuristic scores as calibrated probabilities. Distinguish metadata checking, structural validation, malware screening, OCR, and content interpretation; claim only capabilities actually performed.

No automatic URL browsing initially. Any future fetcher requires isolated egress, redirect/DNS/IP protections, bounded resource use, and separate approval. Third-party intelligence or AI processing requires explicit privacy/security review.

## 7. Data models and invariants

Planned entities:

- User, Session, RecoveryChallenge, UserPreference, ConsentReceipt.
- Assessment and structured AssessmentSignal.
- ScamCategory, ScamGuideRevision, Lesson, LessonProgress, TrustedResourceRevision.
- Report, immutable ReportRevision, ReportEvent.
- Evidence, UploadSession, processing-job records.
- ReviewAssignment, ModerationDecision, AuditEvent.
- ChecklistProgress, DeviceRegistration, Notification.
- SupportTicket, SupportMessage, ExportJob, DeletionJob.

Private objects have clear ownership and foreign keys. Evidence and report ownership must match. Store monetary values as integer minor units with currency and timestamps with time zones. Unknown results are not fake zero-risk values. Hashes establish byte identity, not truth or ownership. Separate public content from private reports and internal notes from owner-visible events.

Proposed reviewed-case lifecycle: draft -> submitted -> queued -> in review -> needs information/triaged/closed. Owner responses, withdrawal, reopening, and deletion use dedicated authorized commands. Do not expose a review queue unless a real operation exists. Users cannot arbitrarily patch status, severity, verification, owner, staff role, or storage key.

Retention applies to records, evidence originals/previews, exports, queued jobs, and backup-restoration handling. Retention durations and legal exceptions require approval; this blueprint does not set them.

## 8. Security requirements

### Identity

Fail production startup on missing/development secrets; migrate password hashing safely; support long passphrases without truncation; validate required token claims and active session/account state; use short-lived access credentials and rotating server-tracked refresh credentials; store durable mobile credentials in OS-protected storage; revoke sessions on logout/recovery; rate-limit authentication; use strong staff MFA.

### Server-side authorization

| Operation | Required rule |
| --- | --- |
| Private list/detail/search/count | Owner predicate enforced in database access |
| Create | Server assigns owner |
| Draft edit | Owner, editable state, expected version |
| Submit/follow-up/withdraw | Owner, allowed command/state, idempotency where applicable |
| Status/severity/verification | Authorized service or scoped reviewer only |
| Upload/attach | Caller owns report and upload; parent/child ownership matches |
| Evidence access | Current owner or explicitly assigned staff; processing/access state permits operation |
| Staff access | Role plus assignment/scope and audit |
| Resource publication | Content permission and independent approval |
| Export/delete | Owner, appropriate recent authentication, auditable bounded workflow |
| Worker execution | Least privilege; recheck account/object/deletion state |

Opaque IDs are not authorization. No blanket support access or account-recovery override. Maintain separation of duties for sensitive staff actions.

### Inputs, files, and operations

HTTPS-only release API; strict allowlisted schemas; parameterized queries; inert rendering; request, file, concurrency and storage limits; rate/abuse controls; replay-safe mutations; redacted logging; private storage and nonpublic caches. CORS is not authorization; protect cookie-authenticated browser flows against CSRF.

Evidence is untrusted: use narrow permitted formats, private quarantine, server-generated keys/hashes, isolated full-format validation, resource budgets, and safe derivatives. Do not accept arbitrary APKs/archives. Do not equate extension, MIME, signature, or hash with safety. Do not release unprocessed evidence through normal previews.

No sensitive push content, broad SMS/contact/call-log collection, or private-data model training by default. Minimize permissions; authorize deep links; avoid suspicious-content WebViews; clear private caches on logout/account switch; protect sensitive local storage/backups. Platform-specific screenshot/app-switcher measures require accessibility-aware review and no absolute prevention claims.

### Abuse model

Cover fake reports, harassment, mass reporting, fabricated evidence, automated registrations, storage/CPU exhaustion, account enumeration, staff compromise, support social engineering, resource poisoning, export scraping, and deletion races. Reports remain private; counts do not determine verification. If AI is later introduced, submitted text is untrusted data, never authority to call tools or change status/resources.

## 9. Validation and state handling

Proposed limits are implementation inputs to confirm through usability/load testing, not established production policies.

| Input | Requirement |
| --- | --- |
| Email | Bounded standards-aware validation and verified ownership |
| Password | Long-passphrase support; no silent truncation; approved hashing-compatible limits |
| Message | Nonblank; proposed 10,000-character limit plus byte cap |
| URL | Explicit parsing; proposed 4,096-character limit; inert display; no automatic visit |
| Phone | Country-aware parsing/E.164 where applicable; no identity or fraud claim from validity |
| Incident | Bounded narrative; known category or not sure; approximate dates allowed |
| Amount | Optional nonnegative minor-unit integer and currency |
| File | Narrow approved format, size/type/structure checks, decoding/resource limits |
| Size | Proposed 20 MiB per file; report/account quotas require approval |
| Filename | Bounded display-safe value, never a storage path |
| Search/page | Bounded query/cursor/page size; ownership applies throughout |
| Mutation | Reject unknown/server-owned fields; bind idempotency to principal/operation/request |
| Transition | Role/scope, allowed state pair, expected version, reason |
| Trusted destination | Approved resource revision only |

Required edge states: offline guidance and honest unsent drafts; session expiry; unavailable analysis returning unknown/failure rather than safe; wrong-owner not-found; timeout after commit resolved through idempotency; concurrent edit conflict; rate/quota limits; corrupt/quarantined files; permission refusal; process death; unknown language; conflicting signals; benign false positives; deleted notification targets; stale resources; unavailable staff; export expiry; and auditable retention exceptions.

Accessibility includes semantic labels, logical focus, scalable text, sufficient contrast, large targets, non-color-only status, reduced motion, and platform screen-reader testing. Use distinct no-data, no-match, loading, and service-failure states.

## 10. Ordered implementation phases

### Phase 0: repository establishment only

- Files: root ignore rules, backend Docker ignore, baseline documentation, local Git metadata/index.
- Feature: preserve current work and prepare an auditable baseline; no application implementation.
- Dependencies: explicit local setup approval and matching preservation fingerprints.
- Security: exclude secrets/data/artifacts, review candidate files, scan before staging.
- Checks: ignore-rule probes, staged inventory, secret-check limitations, unchanged existing-source hashes.
- Completion: local baseline staged and reviewed; no commit/push without separate approval.

### Phase 1: reproducible development baseline

- Files/modules: existing READMEs, dependency declarations/lockfile, test configuration, future CI and API-contract documentation.
- Feature: supported toolchain, real check commands, approved jurisdiction/language/review/privacy boundaries.
- Dependencies: approved repository baseline and isolated synthetic-data environment.
- Security: no production credentials/data; inspect commands before execution.
- Tests: reproduce existing backend/Flutter checks and record actual failures; verify Android wrapper regeneration/build behavior.
- Completion: reproducible commands, known compatibility, recorded baseline and approved contracts; no invented passing checks.

### Phase 2: secure authentication and database foundations

- Files/modules: backend config/security/database/models/schemas/auth/main, migrations/session/recovery; mobile API/auth/session storage; Android release network configuration.
- Feature: verification, recovery, secure sessions/rotation/revocation, safe configuration and schema migrations.
- Dependencies: Phase 1.
- Security: fail-fast secrets, secure storage, required claims, safe password migration, authentication abuse limits, HTTPS release boundary.
- Tests: invalid/expired/revoked tokens, refresh races, recovery replay, long passwords, rate limits, migrations, logout.
- Completion: server revocation works; unsafe production config fails; authentication failure cannot create a session.

### Phase 3: privacy and ownership

- Files/modules: backend authorization/privacy/audit services/routes, migrations, existing analysis persistence; mobile privacy/session controls.
- Feature: owner checks, consent, retention, export/deletion for existing data; later features must integrate.
- Dependencies: Phase 2 and approved privacy choices.
- Security: owner-scoped queries, recent authentication where needed, redaction, deletion/job coordination.
- Tests: two-user isolation in lists/search/count/export/delete; account switching; expiry and deletion retries.
- Completion: existing private data has enforceable access/lifecycle rules, not documentation-only controls.

### Phase 4: catalog, emergency guidance, learning foundation

- Files/modules: backend catalog/resources/content models and reviewed data; mobile catalog/emergency/learning/resources/navigation.
- Feature: 33-guide catalog, public search, guest urgent playbooks, trusted resources, basic lessons/checklists.
- Dependencies: Phase 1 product choices and Phase 2 API foundation; build after Phase 3 in this sequence.
- Security: reviewed examples and destinations, jurisdiction awareness, no emergency login barrier.
- Tests: content completeness/references, offline behavior, stale resources, accessibility/localization fallback.
- Completion: catalog reviewed; urgent guidance works offline; destinations independently verified and versioned.

### Phase 5: assessment correction and expansion

- Files/modules: backend scoring/schemas/models/analysis; mobile result model/API/scan/result/history and feature controllers.
- Feature: consistent warning semantics, retained explanations/versions, context, explicit saving, pagination, input modes; QR/phone/media capabilities only as verified.
- Dependencies: Phases 2-4.
- Security: no arbitrary fetching, no client-controlled result, minimized content, no unsupported probability/identity claims.
- Tests: thresholds, history round-trip, benign near-matches, language limits, errors/offline, pagination, ownership.
- Completion: initial/reopened results agree; failures never appear safe; saved history and capability descriptions are accurate.

### Phase 6: private reports and timelines

- Files/modules: report models/services/routes/migrations; mobile report wizard/list/detail/timeline/recovery.
- Feature: drafts, submission, revisions, owner history, follow-up and recovery checklists.
- Dependencies: Phases 2-5.
- Security: server ownership, strict fields, idempotency, immutable submitted history, controlled lifecycle.
- Tests: cross-user access, mass assignment, retry duplicates, concurrent edits, invalid transitions, restoration, deletion integration.
- Completion: complete private reporting flow with honest statuses and no cross-user access path.

### Phase 7: secure evidence

- Files/modules: existing media/upload routes plus evidence/storage/upload/worker modules and migrations; mobile evidence feature.
- Feature: bounded report-bound intake, quarantine, validation, safe previews/status, deletion.
- Dependencies: Phases 3 and 6; approved storage/processing environment.
- Security: reconcile weak upload contract; narrow formats, isolated parsers, generated keys, ownership and quotas.
- Tests: forged ownership, malformed/polyglot/truncated files, dimensions/resource abuse, interrupted uploads, unauthorized preview, purge.
- Completion: no public evidence by default; unprocessed/rejected files cannot bypass normal preview policy; lifecycle covers originals/derivatives.

### Phase 8: staff review and support

- Files/modules: staff authorization/assignments/moderation/support/audit/content publication; separate console; mobile timeline/support.
- Feature: actual review operation, information requests, controlled transitions, support tickets, editorial approvals.
- Dependencies: Phases 4, 6, 7 and approved staffing/procedures.
- Security: strong MFA, assignment scope, internal-note isolation, independent resource approval, no recovery shortcut.
- Tests: role matrix, privilege escalation, assignments, transition races, audit, serializer boundaries.
- Completion: staff access is scoped/auditable; statuses reflect actual service; support cannot see unrelated reports.

### Phase 9: notifications, settings, and progress

- Files/modules: notification/device/preference APIs/jobs; mobile inbox/settings/profile/privacy and checklist/learning progress.
- Feature: generic push/inbox, preferences, sessions, synced progress and complete connected navigation.
- Dependencies: Phases 3-8.
- Security: private-payload exclusion, owner-bound devices, logout detachment, reauthorization after navigation.
- Tests: stale/duplicate delivery, denied permission, deleted targets, account switching, preference enforcement, offline sync/accessibility.
- Completion: complete connected flows without sensitive push leakage or cross-account state.

### Phase 10: iOS and production readiness

- Files/modules: new iOS target, Android release config, CI/deployment, operational runbooks and store/policy materials.
- Feature: supported platform releases and controlled pilot.
- Dependencies: Phases 1-9; approved signing, infrastructure, legal/policy, and support arrangements.
- Security: release TLS/signing, permission minimization, protected backups, least privilege, incident response and independent assessment.
- Tests: regression, real devices, accessibility, load/abuse, penetration review, backup restore/deletion, release manifest/TLS, rollback.
- Completion: evidence-backed readiness and resolved blockers; accurate store disclosures; explicit production approval.

## Release decisions and verification

Do not install packages, select production infrastructure, invent legal policies/contacts, or make global tooling changes merely to satisfy this document. Production privacy/security claims must follow implementation and review.

Future tests must use synthetic/consented fixtures and isolated services. Evaluate scams and benign near-matches by category/language. Add negative authorization tests to every access path. Platform readiness includes Android proper signing/debug separation and an actual iOS target tested with supported macOS/Xcode infrastructure. No current passing-suite, security-audit, store-acceptance, or production-readiness claim is made.
