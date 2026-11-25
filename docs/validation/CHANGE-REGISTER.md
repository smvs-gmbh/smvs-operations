# SMVS Operations change register

Use one entry per change or independently reviewable increment. Record
scope, requirement and risk references, and the evidence and decision for
the release. The pre-release baseline for comparison is `d446f5d`.

Current phase: **owner-operated pilot evaluation**, confirmed 2026-11-25.
Development and installed scope are distinguished in the
[pilot checkpoint](../deployment/PILOT-2026-11-25.md) and [changelog](../../Changelog.md).
Neither the pilot source checkpoint nor the requirements drafts are an approved
QMS baseline. Subsequent server changes follow development, verification and a
committed, identified source candidate.

| ID | Proposed on | Change | Release target | Status |
| --- | --- | --- | --- | --- |
| CHG-001 | 2026-11-17 | Display AMS Hub information in Exceptions | Pilot server | Read-only view deployed; UAT/PRD retrieval and application checks recorded. Formal validation acceptance remains pending. |
| CHG-002 | 2026-11-17 | Reconcile confirmed Hub closure into local Case closure | Confirm after CHG-001 | Recorded. Implementation and acceptance pending. |
| CHG-003 | 2026-11-17 | Complete transaction audit and protected retention/recovery | Current pre-release assessment | Requirements recorded. Coverage review and backup design pending. |
| CHG-004 | 2026-11-17 | Background Hub change synchronisation | To discuss | Proposed. Cadence and reopening response pending. |
| CHG-005 | 2026-11-18 | Expose retained Catalogue Snapshot fields in personal views | Next increment | Implemented locally; server unchanged. |
| CHG-006 | 2026-11-18 | Download current table views as audited CSV | Next increment | Implemented locally; acceptance and deployment pending. |
| CHG-007 | 2026-11-18 | Typed Excel view downloads preserve identifiers | Next increment | Implemented locally; acceptance and deployment pending. |
| CHG-008 | 2026-11-25 | Reduce import worker memory pressure | Pilot server repair | Implemented and verified on development and server; reconciled in `f951354`. |
| CHG-009 | 2026-11-25 | Expandable import failure diagnostics | Pilot server repair | Implemented and verified on development and server; reconciled in `f951354`. |
| CHG-010 | 2026-11-25 | Pilot consolidation and development-first workflow | Development checkpoint | Phase decision recorded; source, delivery scope and draft evidence consolidated. No additional feature deployment. |
| CHG-011 | 2026-11-25 | Local CRM relation lookups and integrity checks | Local experiment | Implemented and verified locally; owner review and FRS/RA/RTM update pending. |

## CHG-001 — AMS Hub in Exceptions

- **Purpose.** Give NMVO staff the shared Hub status and investigation history
  alongside the existing exception and RCA evidence.
- **Scope.** Match the local Exception and Hub Alert by the exact
  `uniqueAlertId`. Show the Hub Alert status, attributed investigation states
  and history in the Exception detail and RCA. Identify the source and distinguish
  unavailable Hub data from an accessible Alert with no history. Exceptions
  API remains the source for local Alert and transaction details. Open the
  Exception detail from the existing list to see the Hub information.
- **Layout refinement.** In Exception detail, place the AMS Hub panel directly
  below Request & participants in the right column. The technical source
  observations follow Pack & product in the left column. The compact panel shows
  overall status and the latest recorded status change with actor and UTC time.
  A dedicated **AMS Hub** record tab, after Root cause analysis, loads the
  investigation on demand and presents newest-first event cards with complete
  reason/message text. No table view, search or column-configuration controls
  are required for this short history. Preserve the list scope in record/tab links.
  Local RCA and Hub status remain distinct. This refinement does not introduce
  list-driven Hub polling or AI decisions.
- **Transient failure handling.** Allow up to 12 seconds of response inactivity
  per HTTP request, with a four-second connection timeout. Distinguish a timeout,
  authentication, configuration or Alert identity failure in safe user-facing
  feedback and provide Retry/Refresh links. A repeated direct PROD check returned
  the Alert and history successfully. The portal regression covers a timeout and retry link.
- **Data and access.** Use the configured Hub environment and the internal
  Operations access boundary. Keep credentials, raw authentication responses
  and access tokens out of application output and logs. This change reads the
  Hub. Local Case state stays under the existing workflow until CHG-002.
- **Impact.** [URS-109](../requirements/URS-001%20User%20Requirements%20Specification.md#urs-109),
  [FRS-EXC-009](../requirements/FRS-EXCEPTIONS-001.md#frs-exc-009),
  [RA-01, RA-02, RA-14](RA-001.md),
  [RTM-001](RTM-001.md). Check the release's qualification scope with EMVO
  before enabling the Operations connection in production.
- **Evidence and acceptance.** Direct UAT checks verified Alert and history
  retrieval and an End User investigation update. A separate direct PROD
  check on 2026-11-17 verified authentication, Alert listing and one matching
  investigation history. For the application increment, demonstrate exact-ID
  matching, separate local and Hub statuses, an Alert with history, an empty
  history, a missing Alert, API unavailability and restricted access. Verify
  that existing Exceptions navigation and local RCA remain usable in each case.
  Use UAT to verify an inbound OBP Finding. The release record will link the
  tested build and results.
- **Operation.** Set `AMS_HUB_ENVIRONMENT=uat` for qualification or
  `AMS_HUB_ENVIRONMENT=prd` for the approved production connection. Use the
  five matching `AMS_UAT_*` or `AMS_PRD_*` values. The feature is off by
  default. Signed-in investigation staff use **Load AMS Hub investigation**
  in Exception detail or RCA. The synthetic workspace excludes the connection.
- **Implementation evidence.** The portal regression test covers the on-demand
  read, matching IDs, remote closure alongside an open local Case, unauthorised
  access, empty or unavailable history and upstream failure. A direct read
  through the new adapter returned the expected UAT Alert and its two history
  events. The inbound OBP exercise and business acceptance remain open.

## CHG-002 — Automatic local closure

- **Scope.** Make automatic local closure configurable by an Administrator.
  Audit the persisted setting and changes. When enabled, close the local Case
  when the Hub confirms `Closed` for every
  linked Alert. Record the Hub origin and affected Alert IDs in the Operations
  audit trail. Write the change to the local Case only. See the
  [agreed closure rule](../architecture/NAMS-Architecture-Proposal.md#automatic-local-closure-from-ams-hub).
- **Impact.** [URS-109](../requirements/URS-001%20User%20Requirements%20Specification.md#urs-109),
  [FRS-EXC-009](../requirements/FRS-EXCEPTIONS-001.md#frs-exc-009),
  [RA-04, RA-11](RA-001.md), [RTM-001](RTM-001.md).
- **Acceptance.** Verify enabled/disabled behaviour, persistence, permissions
  and audit of the configuration. Demonstrate single and multiple Alert Cases, partial or
  missing Hub status, a Finding without closure, repeated synchronisation and
  the audit record. Specify the handling of any later Hub reopening separately.
- **PRD review example, 2026-11-17.** The reviewer observed an Intermarket
  Alert with current Hub status `Closed` and a closure action attributed to an
  End User in DE, with a timestamp and reason. The role-specific investigation
  indicators were blank. Use an equivalent synthetic case to verify that
  Operations closes its local Case or completes its local support work once
  current Hub closure is confirmed for every linked Alert. Preserve the foreign
  actor attribution and reason when supplied. If the current status cannot be
  retrieved, keep the local Case open until closure can be confirmed.

## CHG-003 — Transaction audit and protected retention

- **Scope.** Audit every user and system transaction, including reads, exports,
  interface requests, failed attempts and automatic decisions. Apply
  FRS-CORE-007 and the [retention and recovery concept](AUDIT-BACKUP-CONCEPT.md).
- **Impact.** URS-003, URS-096, URS-110, FRS-CORE-006/007, RA-07 and RA-12.
- **Acceptance.** Review coverage by workflow, verify atomic changes and audit,
  protected archive, retrievability and reconstruction after isolated restore.
  Confirm category-specific retention, backup schedule, RPO/RTO and owners.

## CHG-004 — Hub synchronisation proposal

- **Proposal for discussion.** Load new matching Alerts initially with bounded
  concurrency and reuse local Hub observations in the UI. Poll
  `GET /api/v1/investigations/details` by action time in the background,
  including updates to locally closed Cases. Refresh current Alert status for
  affected IDs where required. Persist a checkpoint with overlap and duplicate
  detection. Indicate freshness and incomplete or failed retrieval.
- **Traffic.** Separate Hub work from rendering the Exceptions list. Repeated
  list loads use local observations. Query volume follows change pages and
  affected Alerts, rather than the number of list renders. Cadence and
  individual-view refresh policy remain for discussion.
- **Reopening evidence.** EMVO-00470 v4.0 pp. 43–44 allows transitions out of
  Closed for authorised actors. Section 7.6 pp. 54–56 describes archived Alerts
  as read-only through the Hub APIs. A local Closed Case therefore remains
  eligible for change monitoring. Agree whether a detected reopening reopens
  the local Case automatically or raises a review task.
- **Impact and acceptance.** URS-109, FRS-EXC-010, RA-11 and RA-14. Verify
  pagination, bounded time windows, retries, duplicate events, interruption,
  catch-up after downtime, Hub archival and a burst of 1,000 Exceptions.

A71 correlation remains a follow-up to verify against Hub data and evidence of
the relevant distribution market.


## CHG-005 — Catalogue Snapshot fields in personal views

- **Problem.** Products retained total/active Pack counts and OBP information,
  but the view picker and SQL field registry exposed only five business columns.
- **Scope.** Explicit shared rendering/SQL catalogue for retained operational
  Snapshot fields. Products adds numeric total/active Packs, state, OBP name/ID,
  EMVS MAH ID, source code/scheme, original creation/withdrawal values, withdrawal
  reason and national/Article 57 codes. Batches and related Batches add the
  Product's OBP and retained manufacturer/market/creation/multimarket/recall fields.
  Additional columns are optional; existing layouts and field keys are preserved.
  Direct product/batch search also matches OBP name/ID.
- **Interpretation.** SAI remains authoritative for Swiss Product and MAH names.
  Source dates stay labelled as supplied values, without inferred date/time-zone
  conversion. Missing numeric values stay missing; zero is a real value.
  Packs > 0 and Active packs > 0 are different conditions and neither establishes
  an upload during a particular period. Use Upload History for dated events.
- **Impact.** FRS-CORE-002; RA-02 and RA-03. No import, mapping, schema or data
  migration. Reads use existing retained Snapshot evidence and typed count columns.
- **Evidence.** Regression tests cover saved MAH + Packs + OBP conditions,
  filtering before pagination, zero versus missing/active counts, leading-zero
  OBP IDs, source-value escaping, unchanged SAI naming, optional defaults, empty
  results and stable Batch/related-Batch field offsets. Reserved action columns
  remain unavailable for SQL conditions or sorting. Formal release acceptance
  remains separate from these local automated checks.


## CHG-006 — CSV for table views

- **Scope.** Shared Actions → Download CSV for CRM, directories, scoped reports
  and other read-only tables. Preserve displayed column selection/order and
  applied query/sort criteria. Paginated views include all matching pages;
  unsaved column changes are honoured without exporting unapplied conditions.
  Existing selected-row actions retain their own scope and confirmations.
- **Implementation.** Retrieve authorised pages sequentially in bounded chunks
  (500 for supported directory paginators). Reuse the report evaluator for both
  displayed results and CSV selection/sort. Detect changed counts, schemas and
  source strips; abort errors/cancellation without a partial download. This does
  not provide a cross-request database snapshot for concurrent CRM modifications.
- **Data.** Quote UTF-8 CSV fields, preserve source text/identifiers and displayed
  numeric formatting, and omit selection/action controls. Prefix formula-like
  values with an apostrophe for literal spreadsheet import. Limits: 50 MiB
  request, 100 MiB generated text and 400,000 rows; reject instead of truncating.
- **Audit and migration.** `0052_portal_csv_exports` adds generation receipts
  containing actor/UTC/source/column metadata, view hash, counts and SHA-256, not
  cell contents. Commit the receipt before releasing bytes. Independent safe
  failure logs cover route validation/generation/storage failures. Receipts prove
  generation, not browser delivery; end-to-end failed-read auditing and protected
  retention/recovery remain CHG-003. Downgrade refuses to discard retained receipts.
- **Traceability.** FRS-CORE-001, FRS-CORE-002, FRS-CORE-007; RA-01, RA-02,
  RA-07, RA-09. Existing access rules govern every retrieved page and CSV POST.
- **Evidence.** Backend CSV/receipt/permissions/origin/error/migration regression,
  Node report-evaluator checks, and headless-browser tests of multi-page Products
  and CRM, hidden/reordered unsaved columns, leading-zero identifiers, multiple
  independent tables, missing-page failure and cancellation. Wide/narrow layouts
  reviewed. Production remains unchanged; only local MySQL is upgraded to 0052.


## CHG-007 — Excel downloads preserve identifiers

- **Problem.** CSV retains the source GTIN digits, but Excel can infer a numeric
  type and remove leading zeros or round longer identifiers. CSV quoting does
  not specify a spreadsheet column type.
- **Scope.** Add Download Excel beside Download CSV using the same current-view
  collector, pagination, cancellation and access/origin controls. Export `.xlsx`
  text cells for identifier/text columns and literal source messages; preserve
  numeric Pack counts as numbers where faithful. Do not coerce date-like batches
  or use spreadsheet formulas to disguise identifiers as text.
- **Integrity.** Known identifier labels/keys override numeric metadata. Leading-
  zero numerics and values exceeding Excel's 15-digit precision stay text.
  Reject unsupported control characters or cells longer than 32,767 characters
  before file generation rather than silently truncating. Spreadsheet work runs
  outside the request event loop.
- **Audit/migration.** `0053_table_export_format` records csv/xlsx in the existing
  generation-receipt store. Old receipts are labelled csv without changing their
  checksums/contents. Downgrade refuses to discard retained Excel provenance.
- **Traceability.** FRS-CORE-002/007; RA-03 and RA-07. Regression covers GTIN/GLN-
  style identifiers, 20-digit serials, date-like batches, numeric Pack counts,
  literal formula text, text fallback for precision risks, failure without
  truncation, format receipts and preservation of pre-existing CSV receipts.
  Production is unchanged; local MySQL is upgraded to 0053.

## CHG-008 — Reduce import worker memory pressure

- **Trigger (2026-11-25).** Production SAI and Daily Snapshot executions repeatedly
  ended with `worker_interrupted`. Supervisor recorded unexpected SIGKILL exits,
  occasionally affecting the portal too. The node has 512 MiB RAM and nearly
  exhausted swap. Local replay of the retained SAI archive peaked at 565.4 MiB.
- **Scope.** Parse SAI XML incrementally and release processed XML elements;
  share repeated field-name strings. Stage Snapshot rows using bounded bulk
  inserts. Read publication source datasets in repeatable, ordered 500-row pages
  and write packages/batches in bounded groups within the original transaction.
- **Integrity.** Preserve source bytes, source values, row order, record hashes,
  stable identities, completeness/duplicate checks, publication selection,
  idempotency and atomic rollback. No database migration, automatic SAI reference
  change, or Alert Desk Pilot activation.
- **Verification.** Retained SAI replay: 94,457 extracted rows, identical complete
  output digest before/after, peak process memory reduced to 182.6 MiB on the
  local measurement host. Regression covers multiple read/write pages, repeated
  iteration, idempotency, completeness rejection and rollback after late writes.
- **Traceability.** Existing import/publication requirements and associated data
  integrity risks apply; this corrects resource usage rather than adding a new
  user capability. Detailed deployment and operational evidence is retained in
  `docs/validation/evidence/2026-11-25-import-memory.md`.
- **Production result.** SAI execution 352 and Snapshot execution 353 succeeded
  on their first manual attempts. Product/batch and participant publications are
  dated 2026-11-25. Worker PID remained stable; portal health remained successful.

## CHG-009 — Expandable import failure diagnostics

- **Scope.** Add a native, closed-by-default **Failure details** disclosure to
  failed/interrupted Run history entries. Show execution ID, error code, elapsed
  time (interruption detection time where applicable), safe explanations and
  suggested checks, plus available source/processing identifiers, statuses and
  failure stages. Source success is explicitly distinct from end-to-end success.
- **Evidence boundaries.** Only read retained records. An explicit source-job
  link takes precedence. A single same-report job within the execution window
  is labelled contextual activity rather than confirmed ownership; multiple
  candidates are not assigned. Hard terminations remain of unknown cause unless
  evidence was recorded. Do not invent OOM diagnoses for old executions.
- **Security and resources.** Existing Imports administrator access remains.
  No new endpoint, mutation or migration. Bounded queries inspect at most two
  candidate jobs and three processing runs per failed entry, without loading
  artifact blobs, URLs, response bodies, exception traces or source metadata.
  Explanations/stage labels are allowlisted; rendered values remain escaped.
- **Verification.** 515 full-suite tests passed. New regressions cover explicit,
  contextual, ambiguous and missing source evidence, source filtering, no Blob
  fetches/secret disclosure, and absence of failure controls on successful runs.
  Browser checks covered 1500/650 CSS-pixel widths and native keyboard expansion
  behaviour. Narrow tables retain the existing horizontal scrolling pattern.
- **Production.** Applied only the Imports query/helper, two templates and scoped
  stylesheet. Backup/manifest:
  `backups/import-failure-details-20261125T074135Z` under the private runtime root.
  Restarted only the HTTPS portal; scheduler PID 117895 remained running.
  Read-only production rendering found 29 SAI and 27 Snapshot detail disclosures
  in their respective latest-30 histories (411/145 ms measured render times).
  Portal health and stylesheet returned HTTP 200; unauthenticated Imports still
  redirected to sign-in (303). Historical failure records were not modified.


## CHG-011 — Local CRM relation lookups and integrity checks

- **Authority/scope.** Owner approved a reversible local trial, following the UI
  proposal and the MAH/year uniqueness clarification. Branch:
  `experiment/crm-lookups-integrity`, based on development checkpoint `4f93b93`.
  No server update, participant delivery or automatic data repair is authorised.
- **Requirements.** URS-001 draft v0.11, URS-111–113. The detailed FRS, risk and
  RTM reconciliation is explicitly deferred until trial feedback and tracked in
  the implementation list. The trial is not a formal validated release.
- **Lookup.** One per-view MAH → Self-declarations selection (highest data year
  or specified year) supplies typed columns, conditions, sorting, links and
  CSV/Excel view exports. It survives preview, private view saving, navigation
  and export paging. No exact turnover value is inferred from the RX sales group
  or from the sales-related fee. Missing data and zero remain distinct.
- **Uniqueness.** Existing duplicates yield a data error and no lookup source
  values. Historical data remains untouched. The current import service locks
  MAHs and rejects a conflicting assigned pair before adding any business rows,
  while retaining staged evidence. No schema migration is applied; a database
  unique constraint and future write/assignment paths remain follow-up work
  after explicit duplicate resolution.
- **Checks.** Read-only CRM Data integrity page with check/severity/type/year
  filters, source links and UTC check time. Required roles apply to non-archived
  MAHs and exclude archived/provisional contacts. A single contact can fulfil
  both roles. Missing SD review uses the existing current invitation scope;
  imported-only links remain review items rather than assumed orphan records.
- **Reversibility.** No new table or source-data transformation. Save trial views
  separately; preserve a private pre-trial MAH-view/preferences backup. Before
  switching back to the base branch, remove the trial views or restore their
  prior configuration: Git alone does not revert database view preferences.

- **Verification.** Clean indexed source export: 521 Python tests and three Node
  tests passed; application import (67 tables), changed Python lint, JavaScript
  syntax and Git whitespace checks passed. New cases cover zero/missing/conflict
  selection, fixed/highest year, private view ownership/validation, required lookup
  context, sorting/filtering before pagination and export-page collection, read-
  only integrity checks, dual contact roles, malformed/unavailable assignments,
  imported-only relations and atomic duplicate-import rejection with staged data
  retained. A synthetic browser fixture verified saving a fixed-year view and a
  48-MAH CSV across two pages, plus integrity navigation at 1500/650 CSS pixels.
  Existing dependency warnings are unchanged. No operational records were repaired.


## CHG-012 — Structured declaration lookup and related-record return navigation

- **Authority/scope.** Owner requested local implementation of the structured editor
  and explicit return link to the originating record. Continues CHG-011 on
  `experiment/crm-lookups-integrity`. No production deployment or data repair.
- **Requirements.** URS draft v0.12, refined URS-111 and new URS-114. FRS, risk and
  RTM reconciliation remain tracked for trial acceptance; no approved QMS baseline.
- **Lookup.** Separate Lookups tab; up to eight typed conditions combined as AND/OR,
  Unique match or Min/Max numeric record selection, and explicit output projection.
  Only configured lookup outputs are offered as columns. Source year/selection
  context stays mandatory when showing values. Sort/filter output dependencies
  block removal until resolved. No arbitrary selection on ties; no aggregation.
  A candidate's duplicate MAH/year cannot be masked by filtering its other source.
  Empty numeric fields are excluded from Min/Max; zero remains a valid value.
  Legacy highest/fixed-year saved views remain readable without a migration.
  This increment has one Self-declarations definition per MAH view. Independent
  named lookups and Contracts remain separate follow-up work.
- **Navigation.** Explicit source kind/ID with allowlisted view context and section,
  independent of browser history and shared session state. Source names are resolved
  from the database, not query text. Contacts retain origin during edit/save/cancel;
  related-parent contact Previous/Next is scoped to assigned contacts. MAH agreement
  and selected-declaration links carry the same return context. Directory back links
  remain separate. Invalid/missing sources omit the extra link. No external return
  destinations, nested origin chain or source edit commands are accepted.
- **Reversibility.** No schema/source-data change. Save new trial views separately;
  new structured view configurations are not understood by the previous revision.
  Remove those trial views or restore their pre-trial configuration before rolling
  source back. Existing prior views are converted only on user apply/save.
- **Verification.** Regression tests cover AND/OR, Unique/Min/Max, ties, empty/zero,
  hidden duplicate sources, output dependencies, saved views and malformed input;
  source identity, view/section preservation, scoped contact navigation, editing,
  saving and invalid/missing origins. Browser and final suite evidence recorded below.

- **Final evidence.** 523 full-suite Python tests and three Node export tests
  passed; changed Python lint, module syntax and Git whitespace checks passed.
  Isolated browser review at 1500/650 CSS pixels verified the new Lookup/Columns
  panels, typed conditions, projection, save/reload and an exact 48-record CSV
  across two pages. Contact review verified source identity/view/section,
  parent-scoped Previous/Next and edit/cancel preservation. Save preservation is
  covered by the HTTP regression. Fixture checks made no operational data edits.


## CHG-013 — One display selector for lookup fields

- **Authority.** Owner feedback identified duplicate column selection and unwanted
  compulsory context columns in CHG-012. Local development correction only.
- **Behaviour.** Lookups → Columns to display is the sole control for related
  display fields. Checked fields appear immediately and persist through apply,
  private view saving/reload and complete-view exports. Columns contains fixed
  directory fields only; fixed-field ordering/reset does not alter lookup choices.
  SD year and Selection result are optional. Duplicate/ambiguous selections are
  labelled in affected cells, so omitting the diagnostic column cannot disguise
  an invalid source choice. Original source evidence is unchanged.
- **Compatibility.** Existing configured outputs remain selected and may be
  unchecked. No silent database rewrite, schema migration or server deployment.
  Stale layout settings cannot suppress checked outputs or add unchecked ones.
- **Requirements.** URS-111 refined in draft v0.13; deferred FRS/RA/RTM reconciliation
  remains tracked. This is not an approved validation baseline.

- **Verification.** 524 full-suite Python tests, three Node export tests and changed
  Python/JavaScript/whitespace checks passed. An isolated synthetic browser fixture
  verified that selecting only RX packs sold immediately adds only that related
  column, optional diagnostic toggles, fixed-only Columns/reset, apply/save/reload,
  duplicate error labels without a diagnostic column, and an exact 48-row CSV over
  two pages at 1500/650 CSS-pixel widths. No operational views or records were edited.
