# SMVS Operations — implementation status

**Data snapshot: 2026-11-04, verified at 20:25 UTC / 21:25 Europe/Zurich.**

**Later functional update, same date:** `/imports` now provides schedule visibility,
daily/interval configuration, Pause/Resume, queued Run now, source-specific Backfill,
cancellation, execution history and a worker heartbeat. Backfill preserves the
schedule; Run now recalculates its next occurrence. See [Import management](../integration/import-management.md).
The data counts below retain their original snapshot time.

This is the technical handover record for the current local implementation.
Counts and schedules below were checked against `smvs_operations`; they are a
point-in-time snapshot, not permanently current dashboard figures. Conceptual
architecture and controlled requirements retain their own scope and approval status.

## Current result

The local portal combines NMVS source observations with Swiss SAI reference data,
participant context, daily activity history and reusable technical pack/upload
evidence. Local root-cause assessments, review status and to-do follow-up are now
available. Shared participant investigation, formal Alert closure and replacement
of NMVS Alerts remain subsequent work.

The interface is English throughout, including accessibility labels, validation,
empty states and generated summaries. British spelling is the project convention.
Original German/French names, descriptions and source messages are preserved.
Application-rendered dates use ISO format and explicit UTC times; native date
inputs can follow the browser locale. The platform uses the agreed upright,
typographic SMVS / Operations wordmark without a cross or Data Matrix.

## Implemented sources

| Source | Implemented behaviour | Current coverage / reference |
| --- | --- | --- |
| NMVS Daily Snapshot | Retained original, idempotent extraction and operational mapping of Products, Batches, Organisations and Locations | Published snapshot: 2026-09-26 |
| Refdata SAI | Latest-export discovery through the download page, full XML/ZIP extraction and GTIN14 mapping | Published full export: 2026-10-05 03:02:27, as stated by the source filename |
| User Activity Report | Genuine-only Verification and IMT Fulfilment history, UTC-day coverage, organisation drilldown and separate bulk pack measurements | 2026-08-06 to 2026-11-03; 90 days for each of two sections |
| Exceptions API | Paged alert queries, retained raw responses, completeness validation, source revisions and atomic publication | Complete query coverage 2026-08-01 to 2026-11-03; 2026-11-04 queried through 19:02:15.675 UTC |
| Pack Audit Trail Report | Explicit queued retrieval per exact source/product scheme/product/serial; schematic chronology, reusable versions and originals | Seven accepted live report versions, plus one supplied example; not a complete per-pack archive |
| Product Pack Upload Audit Trail Report | Genuine-only window retrieval, daily history, manual backfill and product/batch context | Continuous accepted coverage 2026-08-01 to 2026-11-03 |

The API source is the Swiss NMVS. These reports do not establish a complete
EMVS-wide history. A successful query, an event occurrence and a capture timestamp
are separate facts. No events on an accepted day is distinct from a missing import.

## Data snapshot

| Entity | Count |
| --- | ---: |
| Products / original Product source records | 5,690 / 5,690 |
| Observed product version contexts | 8,417 |
| Batches | 49,496 |
| SAI packages / preparations / address-holder records | 63,237 / 26,043 / 1,364 |
| Local Organisations / Locations | 58 / 45 |
| Activity facts / section-day coverage records | 5,544 / 180 |
| Unique source Alerts / distinct retained payload revisions | 2,552 / 2,552 |
| Accepted Exception query publications | 11 |
| Accepted Pack Audit report versions / pack request records | 8 / 6 |
| Accepted Upload report versions / upload-window request records | 8 / 7 |

All six pack requests and seven upload requests were `ready` at verification.
Report versions and request records are evidence/retrieval counts, not Alert counts.
Activity facts include different metric kinds; they must not be summed as if every
fact were a transaction. The earliest returned Alert is dated 2026-08-03 despite
query coverage beginning on 2026-08-01.

The Product, Batch and participant views still use the September Snapshot, and
Swiss names still use the October SAI publication. Neither publication is made
current merely by viewing a page or importing more recent Exceptions.

## Portal and agreed behaviour

- **Products and Batches:** Swiss product names and marketing authorisation holders
  come exclusively from SAI. Original NMVS/PMD observations remain separately
  accessible, including negative version values such as -1/-2. Those values retain
  unresolved meaning; they are not evidence of an old or defective upload.
- **Product identity:** validated GTIN14 is the preferred Swiss matching key.
  Other source schemes and literal identifiers remain preserved. A missing SAI
  match does not prove that a pack is foreign; such records remain visible.
- **Batch directory:** Batch State is selectable. The default excludes `Expired`;
  `All states` or an explicit state includes those records again. At this snapshot,
  the default shows 18,628 records: 18,599 Active and 29 Recalled. There are 30,868
  Expired records in the full source set.
- **Organisation directory:** the default excludes only `Deactivated`. Other
  statuses and unset values remain visible. The default shows 55 of 58 records;
  three are Deactivated. Explicit selections and Reset behave consistently.
- **Participants:** Organisation and Location have separate identities and source
  statuses. Caller Location and last-pack-update Location are different roles.
  Foreign/unknown identifiers are not silently assigned to local participants.
- **Activity:** Verification and IMT charts, period comparisons, filters and day
  details distinguish zero activity from missing days. Bulk pack totals/averages
  remain separate from transaction counts and exception rates.
- **Exceptions:** date, source market, business process, error, identifiers and
  participant filters; separate Provided/Stored Batch references, exact related-pack
  links and original API observations. No investigation status is inferred.
- **Pack audit:** creation, source-stated changes and failed attempts are distinct
  milestones. Original rows remain expandable. Event grouping by Transaction ID
  takes place within the pack-scoped report. Dispatch entries are not additional
  Alerts or investigation actions, and do not prove Hub acknowledgement.
- **Upload history:** matching uses product identity and exact case-sensitive
  Provided/Stored Batch. The selected period retains its own coverage status.
  Matches outside it are offered across **all already imported history**, including
  earlier months, grouped by day/batch with direct day links and pagination.
  Viewing these matches makes no API request. Duplicate rows across overlapping
  versions appear once in the display; variants remain separate source evidence.
- **Evidence boundary:** Upload reports contain no individual serial numbers.
  A batch upload does not establish that a specific serial was included. The
  individual Pack Audit Trail can supply separate pack-creation evidence.

## Scheduler configuration

Daily times are local **Europe/Zurich**, including daylight-saving adjustments.
Report periods use UTC. The scheduler is a separate portable process, not cron
and not a web-server startup hook.

| Import key | Configured cadence | Enabled | Recovery / refresh |
| --- | --- | --- | --- |
| `sai` | 04:00 daily | No | Discover the latest full export; reuse identical successful extraction |
| `daily_snapshot` | 04:15 daily | No | Snapshot acquisition and operational mapping remain distinct steps |
| `user_activity` | 05:00 daily | Yes | Fill missing days; revisit the latest seven complete UTC days |
| `exceptions` | Every 7,200 seconds after completion | Yes | Fill gaps since the initial/earliest imported period; revisit seven recent days including today's partial data |
| `pack_uploads` | 05:15 daily | Yes | Fill gaps since the earliest retained upload window; revisit three recent complete UTC days |
| Pack Audit / manual Upload queues | Explicit requests, checked by the serve loop | On demand | Durable queue, serial per-worker retrieval, bounded retry and retained prior accepted versions |

A schedule being enabled does not prove a process is running. The foreground
scheduler must remain active. No OS login/reboot autostart or production supervisor
has been installed. Queue processing can wait for a current import/report poll to
finish. Source downtime and delayed availability can postpone a scheduled result.

## Repeatability and safety

Runtime sessions permit only `smvs_operations`; the legacy `smvs` database is not
used. Original bytes are immutable and content-addressed. Identical content with
the same parser/transform reuses canonical staging; domain identities prevent
repeat imports from duplicating the same business entities. Acquisition/job
attempts remain separately observable, and different report versions remain distinct.
This is not a claim of external exactly-once submission.

Partial/truncated/invalid Exceptions results do not publish. Source disappearance
from a subsequent query does not delete retained Alerts. Overlaps permit safe
reconciliation, but late insertion beyond the refresh window requires an explicit
broader query. No approved permanent evidence-retention or backup policy is implied.

The local portal has no login and is bound to loopback. Explicit same-origin POSTs
can queue evidence retrieval and save local reviews; ordinary GET views do not submit source requests.
No medicines state, participant message, Alert closure or AMS-Hub action is changed.

## Verified examples and source limitations

1. **Destroyed → Destroyed:** three Spanish intermarket Alerts on 2026-10-19.
   Exception 1366 has a retained Pack Audit Trail: Active → Destroyed succeeds at
   08:31:47 UTC; another Destroy request at 08:31:49 fails with A7. The pack was
   created in December 2024. This example does not assign Swiss investigation
   responsibility; the caller market/business process determine the review context.
2. **Propofol, Exception 2551:** a late-October selected window has no matching
   Upload events, but the new history search offers three product/batch events on
   2026-09-01. The source reports 1,920 successful pack uploads for that request.
   The individual Pack Audit Trail separately reports this serial's creation that
   day. Its reported data-availability time of 2026-11-04 18:30 UTC precedes the
   Alert at 18:51 UTC, although the report was fetched at 20:01 UTC. A fresh download
   does not guarantee fresh audit-source data. The supplied NMVS Alerts screenshot
   also shows the September creation entry for this pack.

## Discussed but not implemented

- **Exceptions Audit Trail importer:** sample CSV analysed and useful extra
  Hub-related error context identified; no daily importer, projection or schedule
  has been introduced. Alert queries are not a full successful-verification history.
- **Pack Disclosure:** deliberately not selected for integration at this stage.
- **Upload Metric Report:** contract considered; no separate metric importer or
  reconciled global upload dashboard is implemented.
- **Unified evidence timeline:** adding a separately attributed Exceptions-API
  observation alongside audit-report events and an explicit “Report data predates
  this alert” indicator were proposed, but remain unimplemented. Current UI shows
  the source availability timestamp and generic unmatched-event notice.
- **Shared investigation / CRM direction (2026-11-04):** document the End-user-first
  collaboration pilot, NMVO-owned closure and integrated organisation/contact/SPOC
  directory with a planned idempotent Airtable CSV migration. These are proposed,
  not implemented. Hub integration follows the End-user pilot. See the
  [shared investigation proposal](../architecture/Shared-Investigation-and-CRM-Proposal.md).
- **OBP / CAPA / Incident Reports (2026-11-04):** planned manual import of the
  EMVO OBP directory without assuming an existing relationship or access rights;
  structured cause/action/effectiveness follow-up for process failures, separate
  from Alert closure; and template-based, copyable Incident Report text for CANEA.
  The Incident Report template is pending; these capabilities are not implemented.
  See the [shared investigation proposal](../architecture/Shared-Investigation-and-CRM-Proposal.md).
- **Local Root cause analysis:** dedicated tab with a versioned cause catalogue,
  category-specific checks, hypothesis/confirmation and editable findings/next action,
  Open/To do/Resolved, UTC follow-up dates, local history, stale-source resurfacing
  and explicit Save analysis / Resolve / Reopen actions with a similar-exception
  resolution preview. Resolution basis/reason and pending-work safeguards are implemented. See
  [local review semantics](../integration/exception-review.md).
- **Investigation / NAMS / AMS-Hub:** authenticated assignments, formal Alert closure,
  participant-specific workflow, business Action Log, messaging and End-user portal/API
  remain design work. Foreign-initiated IMT does not trigger automatic routine
  Swiss investigation or report retrieval.
- **R20 / CR 106801:** supplier clarification is pending on pre-deployment L3/L4
  availability and re-querying periods after temporary R19 results are removed.
  The existing importer processes Alerts; the new L3/L4 endpoint/schema has not
  been integrated. Retained local bytes are separate from source query-result TTL.
- **Operations readiness:** authentication, supervisor/autostart, failure notification,
  rate-limit-aware enhancements, approved retention/backup and production release
  controls remain open. An indexed upload-event projection may be needed as retained
  report volume grows; current history scans read event JSON one report at a time.

On 2026-11-05, Upload history gained evidence-guided period selection: exact-pack
creation where retained, older imported batch matches first, and bounded suggestions
for uncovered UTC days. No automatic report requests or schema changes were added.

## Verification and version-control state

Most recent complete code validation: **368 tests passed**, with one pre-existing
Starlette/httpx deprecation warning. Targeted Upload tests passed after the final
wording/fixture changes. Local review tests cover reversible hiding, older to-do
items, stale versions/source data, exact bulk scope and atomicity. Ruff and whitespace checks passed for the latest change.
Live database checks and browser checks covered default state filters, explicit
Expired/Deactivated selection, older Upload suggestions and day navigation.
Exact replay of the supplied Upload CSV left report and staging row counts unchanged.

The database is at **`0018_local_resolution` (Alembic head)**. The last committed code
baseline is **`9fc51e7`**; the subsequent portal, participant/activity/Exceptions,
pack/upload evidence and documentation work is still uncommitted. Review the
working tree and database evidence before a separately authorised commit. No commit or push has been performed. The later Imports UI validation preserved
the existing enabled states and cadence values. Its additive migration and updated
local worker were applied for the verified implementation.

## Entry points and detailed notes

From the repository root:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
.venv/bin/python -m app.integration.scheduler --serve
.venv/bin/python -m app.integration.scheduler --list
```

`--list` inspects configuration; `--serve` runs due work and queued evidence tasks.
Do not copy credentials into commands, documentation or source control.

- [Local portal, language and filters](../integration/local-portal.md)
- [Daily Snapshot](../integration/daily-snapshot.md), [SAI](../integration/sai.md)
- [Product/Batch/SAI mapping](../integration/product-batch-mapping.md)
- [Snapshot participants](../integration/snapshot-participants.md)
- [User Activity](../integration/user-activity.md)
- [Exceptions](../integration/exceptions.md)
- [Pack Audit Trail](../integration/pack-audit-trail.md)
- [Product Pack Upload history](../integration/product-pack-uploads.md)
- [Scheduler and recovery](../integration/scheduler.md)
- [Import management UI and command queue](../integration/import-management.md)
- [Evidence/investigation proposal](../architecture/Exception-Evidence-and-Investigation-Proposal.md)
