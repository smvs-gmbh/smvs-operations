# Changelog

Entries distinguish deployed pilot changes from development-only increments.
Pilot checkpoints and requirements drafts do not constitute an approved QMS
baseline. Detailed scope/evidence: [change register](docs/validation/CHANGE-REGISTER.md).

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

