# Changelog

Entries distinguish deployed pilot changes from development-only increments.
Pilot checkpoints and requirements drafts do not constitute an approved QMS
baseline. Detailed scope/evidence: [change register](docs/validation/CHANGE-REGISTER.md).

## 2026-11-26 — Alert Desk on shared synthetic TEST

- CHG-021: Runtime `42f85d6`, schema 0055, on a separate Operations store/processes
  beside VerifyIt. Public participant HTTPS at the node hostname; staff Operations
  stays private through an authenticated tunnel. Capturing mail only.
- Six synthetic alerts; real HTTPS participant verification, findings/comments and
  private template checks passed. VerifyIt's 17 tables/data, vhost and release
  unchanged. 632 source hashes verified; PROD unchanged.
- 586 local tests pass. Hosted: 582 pass, four SQLite downgrade cases excluded
  after documented platform failures. Formal protocol/restore/timing/mail acceptance
  remain open. [Deployment evidence](docs/deployment/ALERT-DESK-TEST-2026-11-26.md).

## Unreleased — Alert Desk TEST preparation

- CHG-021: Prepared deployment/access comparison and a 20-case validation protocol
  with traceability, expected outcomes, evidence and open timing-policy decision.
  Reconcile local templates and planned hosted controls in draft FRS/RA/RTM.
- Initial preflight identified VerifyIt; owner subsequently confirmed shared TEST.
  See the dated deployment above for the actual installed scope.

## Unreleased — hosted Alert Desk TEST candidate

- CHG-021: Owner confirmed shared TEST and selected public participant access.
  Add explicit TEST enablement, configurable origins/links, secure gateway checks,
  command ceiling and synthetic-data banner; production remains disabled.
- Separate service runner, private capturing SMTP and guarded synthetic seed.
  Initial Operations staff route remains private through an authenticated tunnel.
  No external test email is enabled; rollout evidence is in the dated entry above.

## Unreleased — compact participant template navigation (local)

- CHG-020 C / URS-122: Templates picker beside Comment; create/edit/delete move to
  My templates with exact case return and prefill from the current comment.
- Preserve unsent same-tab answers; scope snapshots to verified session/case, retain
  only the comment if the case changed. Existing template API/audit and schema 0055
  unchanged. No production rollout.

## Unreleased — optional general Alert Desk comments (local)

- CHG-020 A / URS-122: Optional Comment for all supported End-user/MAH findings,
  including progress updates. Retain drafts on finding changes and comments on
  confirmation/reload/amendment; existing 1,000-character bound and CAPA rules.
- Personal named templates remain planned. No production deployment.

## Unreleased — personal Alert Desk comment templates (local)

- CHG-020 B / URS-122: Verified participants can create, reuse, rename/edit and
  remove private named templates. Insert preserves draft text and does not send.
  Stable ownership, stale-version checks and transactional history; prior comments
  remain unchanged. Local schema 0055 adds template/event tables.
- Local pilot services updated; no production schema or Alert Desk rollout.

## 2026-11-26 — Pack Audit worker feedback (pilot server)

- CHG-019 / URS-121: Show environment and recent worker heartbeat before/after a
  Pack Audit request. Distinguish missing worker, normal/delayed queue, competing
  work, retry and running/unconfirmed processing. Preserve queued work and reports.
- Shared Imports liveness; read-only refresh. Targeted runtime `9c04152`, schema
  0054 unchanged. 547 candidate tests and production verification passed; 399 source
  hashes and existing records verified. [Deployment evidence](docs/deployment/PACK-AUDIT-WORKER-2026-11-26.md).

## 2026-11-26 — Exceptions markets and dates (pilot server)

- CHG-017/018, URS-119/120: Multiple requesting markets and imported-period date
  bounds with Last month / 3 months / year / All. Whole retained history works
  across views, Alert navigation and exports; other conditions remain applied.
- Targeted runtime `ae86621`, based on previous CRM baseline `8e9748d`; unchanged
  schema 0054. API Access and Alert Desk Pilot remain local.
- 538 candidate tests passed; production verification confirms 398 source hashes,
  login protection, 2025-01-01–2026-11-26 date bounds and unchanged 22,235 Alerts
  and existing CRM records. [Deployment evidence](docs/deployment/EXCEPTIONS-DATES-2026-11-26.md).

## Unreleased — API Access (local pilot)

- CHG-016: User → API Access combines the five already imported snapshot API
  sections. Correlate User-Agent/IP with organisations, locations, clients, last
  requests and API services; use saved views and exact-scope exports. Retain
  source-row evidence, fixed snapshot scope and explicit WAF evidence limits.
  URS draft v0.16 / URS-118; no database migration or production deployment.

## 2026-11-26 — production Exceptions history (operational data)

- Extend accepted history to 2025-01-01 through the current UTC day using native
  chunked backfill/gap recovery. Verified 694/694 complete days, 22,235 distinct
  Alerts, original 6,519 retained and no duplicate source Alert IDs. No application
  deployment, schema or schedule change.
- Record source-market/SAI interpretation and complementary report limitations in
  [the operation evidence](docs/validation/evidence/2026-11-26-exceptions-backfill.md).

## 2026-11-25 — deployed CRM pilot cutover

- CHG-015: Clean CRM column labels/catalogues; unify durable general Contact
  affiliations with separate SPOC/Alert roles and protected manual changes. Add
  stable supplier identities, schema 0054, idempotent source reconciliation and
  relation audit/review findings. Protect maintained CRM values on reimport and
  block saved views using retired predicates until explicitly corrected.
- Consistent private database backups with checksums, completion manifests and
  overlap protection; isolated restore/migration rehearsal. URS draft v0.15,
  URS-115–117. Runtime `8e9748d`, schema 0054; daily 01:30 UTC database backup.
  Production restore, migration and CRM rendering verified; 15 source references
  need integrity review. [Deployment record](docs/deployment/CRM-CUTOVER-2026-11-25.md).
  Formal validation reconciliation remains open.

## CRM relation/integrity increments (included in the cutover above)

- CHG-014: Add an independent Agreements lookup beside Self-declarations, with
  typed signing-date comparisons/Min/Max, selected agreement fields, source-MAH
  return links and consistent full-view exports. Preserve missing values, ties
  and imported start/termination text. URS draft v0.14; local development only.


- CHG-013: Lookups alone controls displayed relation fields; Columns lists fixed
  MAH fields only. SD year and Selection result become optional. Fixed-column
  reset preserves lookup choices; saved views and exports use the same selection.
  URS draft v0.13 refines URS-111. Local feedback correction; no server deployment.


- CHG-012: Separate Lookups tab with structured AND/OR conditions, Unique match,
  Min/Max and output projection for MAH Self-declarations. Add explicit source-record
  return links and parent-scoped contact navigation. Existing trial views remain
  readable; no migration or production deployment. URS draft v0.12, URS-111/114;
  detailed FRS/risk/traceability reconciliation and owner acceptance remain pending.


- CHG-011: MAH self-declaration lookup selection and typed view columns; read-only
  CRM Data integrity findings; import guard against new duplicate assigned MAH/year
  records. Branch `experiment/crm-lookups-integrity`; no server deployment.
- URS-111–113 recorded in draft v0.11. FRS/risk/traceability update and acceptance
  remain explicit follow-up work. Existing historical records are not repaired.

## 2026-11-25 — Pilot server corrections

Source checkpoint: `f9513549b514f7c2aabcf8219090ab03488e1990`.

- **CHG-008:** Reduce SAI XML extraction memory, bound Snapshot staging and
  product/batch publication reads/writes, and retain atomic rollback. Successful
  server imports published the 2026-11-25 Snapshot and participants.
- **CHG-009:** Add expandable failure details to Import Run history, including
  safe diagnostic explanations, identifiers, recorded source/processing stages
  and explicit uncertainty for unrecorded termination causes.
- Both changes were applied as targeted pilot-server repairs with rollback
  backups, then reconciled into Git. This is a recorded exception to the
  development-first workflow now established in the [pilot record](docs/deployment/PILOT-2026-11-25.md).

## 2026-11-25 — Development pilot consolidation (not deployed)

- **CHG-005:** Make retained Catalogue Snapshot fields, including reported active
  Pack counts and OBP, available in table views and filtering.
- **CHG-006:** Download current table views as CSV with access/origin checks,
  complete matching-page collection and generation receipts.
- **CHG-007:** Download typed Excel files, preserving identifier leading zeros
  and precision; retain numeric Pack counts where faithful.
- Local schema: `0053_table_export_format`; deployed server remains at `0051`.
  Migrations `0052`/`0053` and these features are not part of the server repairs.
- Preserve URS/FRS working document revisions and diagrams as unapproved drafts.
  Consolidate the development workflow, change history and validation evidence.

## 2026-11-17 — Operations pilot release

- Consolidate Import, Catalogue, Exceptions, Users, Reports, CRM, Workflows and
  Settings, read-only AMS Hub evidence and validation drafts.
- Deploy application source `eee48a6d4007a4ef511a9dd68f3468da958b9bf5`, with
  documentation close-out `a697f75`. Apply schema through `0051_crm_record_notes`.
- Alert Desk Pilot remains a local feature; server activation and synthetic
  workspaces remain excluded. See [release evidence](docs/deployment/RELEASE-2026-11-17.md).

Earlier development history remains available in Git; this file does not claim
to reconstruct every earlier change retrospectively.


## Unreleased — hosted TEST mailbox correction

- CHG-021 D: Correct Open test mailbox to the private TEST server inbox. List and
  escaped message/code view require TEST enablement and authorised Operations
  staff; participant/public/production access remains unavailable. Existing
  invitations and captures are preserved; no external mail or schema change.

CHG-021 D deployed on TEST as `e71fd98`, schema 0055 unchanged. Captured invitation
is available in the authenticated Operations mailbox; existing passkey/invitation
and messages preserved. 32 focused tests and hosted access/refusal checks pass.

## Unreleased — End User requesting Location ownership

- CHG-022 / URS-123: End Users see only alerts from a currently assigned requesting
  Location. Remove organisation-only and reviewed foreign-export access fallbacks.
  Lists, direct views/templates, findings/batches and notification routing share
  the check. Prior pack changes grant no access; MAH/NMVO scope remains separate.
- Preserve fixtures and retained findings. The locally originated A24 demo remains
  visible because its requesting Location belongs to Test pharmacy.

CHG-022 deployed on TEST as `1198796`, schema 0055 unchanged. 589 local tests pass;
native MySQL scope excludes foreign export-attributed A7s and retains four actual
own-location cases. MAH retains six; existing data/passkeys/sessions unchanged.

## Unreleased — End User A24 investigation

- CHG-023 / URS-124: Own-location A24 supports findings, comments/templates and
  CAPA through the existing attributed workflow. No upload/identifier questions,
  pack-state change, batch command or automatic closure.
- Preserve the local A24 example and add a separate foreign-requester fixture
  with an earlier own-location action. Foreign read/write access remains denied;
  MAH A24 input remains outside this increment.

CHG-023 deployed on TEST as `3df4191`, schema 0055 unchanged. Own A24 is editable;
separate foreign A24 is inaccessible to End User. Native transactional checks pass;
existing records/sessions preserved and no real mail/pack operation performed.

## Planned — combined investigation history

- CHG-024: Record the gap between the local-decision Audit trail and expected
  participant/Hub Case history. Participant findings already persist separately;
  Hub history remains live-only and needs retained source observations. No
  implementation/deployment or audit-completeness claim in this planning entry.


### 2026-11-26 — CHG-025 TEST email preparation

Add controlled SendGrid transport, shared dynamic template assets, protected
configuration example and private delivery history (schema 0056). Capture stays
the default; real external delivery requires private key/template activation.
No production change or completed end-user delivery validation is claimed.

CHG-025 installed on shared synthetic TEST as runtime `614524d`, schema 0056.
Both approved contact addresses updated with version-based access invalidation;
findings/templates/passkeys preserved. Capture remains active, key/template ID
and real external delivery acceptance pending. PROD unchanged.

2026-11-26 17:18 UTC: configured TEST SendGrid with the owner's protected key/template
and activated the two-recipient allowlist; API/portal restarted. Source/schema
unchanged. No invitation was sent by activation; first inbox/code validation pending.
Development stays in capture mode; PROD unchanged. Email languages are deferred.


### 2026-11-27 — CHG-026 Owner-supplied product logos (local)

Use the supplied wide Alert Desk PNG in participant access/list/case/template
headers and NMVO previews. Retain the narrow variant as an available brand asset.
Use the supplied Operations PNG in the sidebar and sign-in page, on a white CSS
surface. Preserve original image bytes/proportions and accessible image text.
Serve only named public brand files; Alert Desk CSP permits same-origin images
while keeping default-src none and existing authentication/no-store controls.
Local workspace supports the same assets. No schema, workflow, mail template or
hosted TEST/PROD change.

Verification: 39 targeted investigation/workspace/hosted-origin tests passed;
Ruff and diff checks passed. Chrome desktop and emulated 390 px mobile previews
verified loaded artwork and no horizontal overflow on the access page; local
Operations sign-in visually checked. Input hashes match repository copies.


### 2026-11-27 — CHG-027 TEST invitation template preparation

Prepare single-destination HTML/plain-text SendGrid template with hosted Alert Desk
logo; add message_text while retaining legacy message for existing active versions.
The invalid workspace URL observed in the email is not produced by the application.
Template replacement needs the SendGrid UI (runtime key has no template rights).
A24 MAH behaviour awaits owner decision based on EMVO guidance.


### 2026-11-27 — CHG-028 Conditional MAH A24

A24 MAH view now explains its informational status. A scoped NMVO request or an
explicit own-cause declaration enables progress/findings/comments/CAPA. Current
source and organisation are checked; existing access/closure rules stay in force.
No pack transaction, automatic mail, schema migration or fixture reset.
