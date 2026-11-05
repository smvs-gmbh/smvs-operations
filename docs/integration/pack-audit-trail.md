# Pack Audit Trail evidence and schematic presentation

Implemented 2026-11-04. This adds technical evidence retrieval/presentation, not
investigation decisions, participant messages or AMS-Hub writes. It follows the
provenance/evidence boundary in ADR-004, ADR-006 and the preceding evidence proposal.

## User flow

From an Exception, open **Pack audit trail**. A GET only reads local evidence. An
explicit same-origin POST via **Load pack audit trail** creates/coalesces a durable
request. The portable scheduler worker checks this queue after each normal tick.
One pack is processed at a time; its row is durable and an independent mutex is
held for the full invocation. A crashed worker can recover the running row; three
attempts with five-minute delays are bounded. Report generation/polling is bounded
to ten minutes per attempt. A unique persisted report title is looked up on retry,
reducing duplicate report creation after interruption. Source query creation is
not claimed to be externally exactly-once: an interrupted POST with delayed source
visibility may still be repeated. Normal page opens and repeat button clicks do not
create another report request while a task is queued/running.

A ready report is reused by exact authority/scheme/product/serial signature.
Serials are not case-folded or repaired, and a product-only match is insufficient.
**Refresh report** explicitly requests a newer version. Retrieval never
starts automatically on an incoming Alert, including IMT Alerts. A manually chosen
cross-market report does not determine investigation responsibility. Missing pack
identifiers prevent the action. The source must independently allow access.

## Acquisition, storage and source scope

`PackAuditClient` verifies `GET /report-types/PackAuditTrailReport`: required
parameters must be productCodeScheme/productCode/serialNumber. It requests English
CSV through `/report-request`, correlates the generated unique title against the
lookup result's title, and downloads only a validated HTTPS same-origin URI. No
redirects or source-supplied arbitrary target can receive credentials. Normal
Reporting API settings/credentials are reused; no secret is copied into tasks.
The observed latestAvailableData at request time is retained as source context;
this is not an invented per-event effective time or a guarantee of no later events.

`pack_audit_requests` retains the current signature-specific queue state, request
identity, retry status and selected report. `pack_audit_reports` holds immutable
accepted versions and copied raw event/metadata evidence. Existing acquisition,
original-byte, processing and staging machinery is reused, including canonical
content/parser reuse. Failed parsing preserves original bytes. Publication checks
returned product scheme/code/serial against requested parameters (documented GTIN
aliases/validated leading-zero equivalence allowed; serial equality exact).
Report Name must match the correlated request title. Unsupported/mismatched reports
fail without replacing a previously accepted report. Identical bytes and parser
reuse the same report version and do not add another set of staging events.

Report signature and namespace are rechecked before display. Raw CSV can be
retrieved from the local retained original route, without contacting NMVS again.
The separate provided-example namespace is never linked to a current Exception or
presented as a newly acquired source report. Original files/events and prior
versions remain retained; expiry and assessment-linked retention need their own
approved purpose-bounded policy. No cleanup or permanent retention policy is added.

## Schematic projection

The presentation has three levels:

1. **Pack history at a glance**: up to six meaningful milestones, with equal
   schematic spacing, explicit UTC times and caller market. Creation, source-stated
   state changes and attempts with explicit Alert codes are visually distinct.
2. **Before the error**: if one transaction is uniquely linked by exact Alert ID
   or Transaction ID, show its source-stated state/operation and the last observed
   preceding state change. This is a source summary, not a root-cause conclusion.
3. **Chronology**: group rows with the same non-empty Transaction ID. Keep each
   original event separately expandable, including its file row and every raw field.
   Empty transaction IDs remain separate. `All transactions` exposes informational
   verification/unknown events too; 50 transactions per page bound rendered detail.
   Milestone links navigate to the correct full-chronology page and group anchor.

ActualState and InitialState supply state observations. TargetState and
AttemptedOperation are shown separately and never treated as an achieved state.
Creation alone does not invent Active. Duplicate/conflicting Event Details keys
are not selected as unambiguous state fields. Dates with no UTC offset or invalid
values remain unresolved and are placed last, without fabricated chronology.
Repeated source rows remain visible because there is no universal Audit Event ID.

Raw numeric Event Code is not automatically an EMVS Alert code: the real report
uses e.g. 11110200 for successful verification and 51220200 for a failed state
transition. Alert codes are taken from explicit A-codes in Event Code or the
AlertCode/InternalErrorCode detail fields; numeric codes remain in original events.
Recognized success-verification names receive a source-attributed label. Other
unrecognized events are preserved without guessed outcomes. MAH/NMVO alert dispatch
rows attached to the same transaction are not counted as extra Alerts or as local
investigation actions. A report saying dispatch succeeded is not a Hub acknowledgement.

Matching a pack, transaction or time does not establish a common cause, physical
movement, authenticity or jurisdiction. Market/Location values describe transaction
context, not a drawn physical shipment route. If the selected Exception has no
matching report event, its independent source time is stated separately rather
than inserted as an invented report row. Multiple matching transactions stay
ambiguous; the short preceding-state narrative is omitted.

## Verified examples

The user's existing Pack Audit Trail CSV is available at `/pack-audit/example`:
6 events become 3 transactions: created; Active → Exported; second export attempt
with A7/A99, with both MAH/NMVO dispatch records grouped in the latter transaction.
It is clearly marked as provided example evidence and is not a fresh IMT retrieval.

A deliberate button-driven live request for local non-intermarket Exception 85
succeeded: report version 2, 18 source events, 16 transactions, selected A7 transaction
correlated by source identifiers. Later explicitly requested examples and refreshes are recorded separately.
No source Pack Audit Trail is automatically requested for an incoming Alert. An unchanged retained version is reused on subsequent views.

The example import helper is a developer diagnostic, not an end-user import flow.
Normal operation uses the Exception button and the running portable scheduler.
There is still no restart/login autostart service. No investigation Action Log,
closure/root-cause workflow, external messages or Hub actions are implemented here.

## Current status and freshness follow-up

See [the dated implementation status](../overview/IMPLEMENTATION-STATUS.md) for
current report counts and the Destroyed/Propofol examples. Later downloads may
still report a source availability time before an Alert. The UI displays that
time; a dedicated stale-relative-to-Alert indicator and a separately attributed
Exceptions-API timeline marker are proposed, not yet implemented.
