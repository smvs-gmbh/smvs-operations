# Changelog

Entries distinguish deployed pilot changes from development-only increments.
Pilot checkpoints and requirements drafts do not constitute an approved QMS
baseline. Detailed scope/evidence: [change register](docs/validation/CHANGE-REGISTER.md).

## Unreleased — imported Exceptions date ranges (local pilot)

- CHG-018 / URS-120: Restrict date selection to imported query periods, add Last
  month / 3 months / year / All, and allow views spanning the entire retained
  history. Preserve explicit dates in saved views/navigation/exports; retain
  coverage gaps and other filters. Also available in Alert Trends.
- Verified locally; no schema change or production deployment.

## Unreleased — multiple requesting markets (local pilot)

- CHG-017: Select several requesting markets in Exceptions with OR semantics;
  retain the selection in saved views, navigation and exports. Existing single
  market URLs/views remain compatible. EU is labelled Hub/OBP source context.
- Preserve the selection counter when Actions moves into its toolbox. URS-119,
  user guidance and validation follow-ups recorded; no production deployment.

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

