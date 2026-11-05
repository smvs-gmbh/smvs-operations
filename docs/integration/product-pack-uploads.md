# Product Pack Upload Audit Trail

Implemented 2026-11-04. This adds daily genuine-only upload evidence and explicit
on-demand time windows, without automatically fetching per-Exception pack reports.
No Pack Disclosure or Exceptions Audit Trail importer is introduced by this change.

## Source and cadence

`ProductPackUploadAuditTrailReport` uses **Reporting API 3.6**, explicitly for this
client. Live discovery confirmed that 3.3 does not advertise `syntheticMonitoring`
and rejects that parameter with 422 / 65020001. In 3.6 the optional boolean is
advertised: false = genuine, true = synthetic, absent = all. Definitions and the
CSV's `Genuine Transactions` marker are both required. Other clients retain their
existing version settings. A diagnostic 3.3 unfiltered report was generated to
inspect the difference, but was not imported or published.

The `pack_uploads` schedule runs at **05:15 Europe/Zurich**. It requests completed
UTC days, revisits the latest three days for late source updates, and fills gaps
since the earliest retained upload window (first run without history: yesterday).
Adjacent days are coalesced into windows no longer than 31 days. Older covered
days are revisited explicitly when needed. This is not an unlimited historic backfill.
The source `latestAvailableData` must reach the end of the requested period.
The portable scheduler process must be running; OS autostart is not configured.

## Retrieval and evidence

`upload_requests` is keyed by authority, exact UTC window and genuine filter.
Concurrent clicks and pending retries coalesce independently of Product/Batch;
ready requests are reused unless refresh is explicit. Titles are durable across
recovery; source lookup precedes submission. This reduces duplicate submissions
but is not an external exactly-once guarantee after an acknowledgement is lost.
A worker processes one request at a time under a database mutex. Three bounded
attempts use five-minute delays. Refresh failures preserve the old accepted report.

Original bytes are retained before parsing; failed validation grants no coverage.
SHA-256 content storage, canonical processing runs and a parser-versioned report
key make exact replay idempotent. Acquisition attempts remain observable; they do
not multiply canonical staging or the same report version. Different generated
report titles can yield different immutable report versions even for the same
period/events. Staging retains all original rows. Display suppresses exact duplicate
rows across overlapping versions; it does not sum versions or count rows as Alerts.
Changed source rows remain visible as distinct source observations, not a silently
reconciled count. No global upload metrics are inferred from these versions.

Limits: 40 MB, 100,000 events per report; strict columns, explicit timestamp offsets,
period bounds, report identity/title and filter checks. Download destinations are
validated before credentials are attached; redirects remain disabled. CSV originals
can be downloaded only within the current source authority. All SQL uses guarded
`smvs_operations` sessions. The legacy `smvs` database is untouched.

## Portal and matching

`/exceptions/{id}/uploads` reads local evidence only. Explicit same-origin POST
queues a report for 1–31 selected completed UTC days, with a refresh option.

Matching requires a supported product scheme, valid GTIN normalization (or exact
PPN) and **exact case-sensitive batch identity**. Provided and Stored batches are
shown as separate source roles, or both if equal. No repair or fuzzy matching of
batch IDs occurs. Events are timestamped and those after the Alert are marked;
that relation is not proof of a late upload, causality or a separate transaction.

No serials are supplied by this report. Product/Batch context is not evidence that
a particular serial was uploaded and does not assert EMVS-wide history. Local
coverage is the union of accepted genuine windows, independent of matching rows.
“No match in the checked period” and “period not fully checked” remain distinct;
a failed fetch never becomes an empty accepted report. Historical emptiness is
not proof of absence outside the checked period. Window boundaries are treated
as half-open for display; an event exactly at the endpoint belongs to the next
window, and overlapping source endpoints do not duplicate visible events.

The supplied monthly CSV was explicitly assigned to the configured Swiss source
as a **Provided export**, preserving its provenance instead of pretending it was
API-acquired. Accepted reports remain immutable with capture time and original file.
The current projection reads selected-window events and searches retained report
history for older/later matches. If volume grows substantially, an indexed event
projection should replace these scans.

## Validation

Live API 3.6 import of 2026-11-03 returned 130 genuine events. The initial daily
handler completed successfully, filling the partial first day and refreshing the
last three days. Automated tests cover filter refusal, empty/partial coverage,
exact replay, overlaps, strict batch identity, authority isolation, durable queue
recovery, preserved raw failure evidence and same-origin portal actions. The new
migration is included in the historical schema-to-model migration comparison.

## Matching events outside the selected period

The Upload history GET also searches every already imported upload report for the
same source, without a date lookback limit. Exact product/batch matches outside
the selected window are grouped by UTC day and Provided/Stored Batch role, with
10 groups per page and links to open each matching day. Older matches may be
months or years earlier, provided the relevant reports have been imported.
The search makes no source request and does not mark the selected period covered.
A matching day can itself have incomplete coverage; opening it preserves that
coverage warning. Unknown or unimported periods remain unknown. Duplicate source
rows in overlapping versions are counted once for display; rows with another
source, product or different-case batch cannot become suggestions.

Only small report metadata is loaded together. Event JSON is read one report at
a time, with product identities cached before parsing matching event details.
The supplied Propofol example finds three matching events for batch 26306051 on
2026-09-01 while keeping the selected late-October/November result separate.

## Evidence-guided search periods (2026-11-05)

The Suggested upload search panel uses retained evidence before offering a report
request. The stored batch takes precedence for guidance; the original search still
shows matches for both provided and stored batch values separately.

- Use an unambiguous `PpdNewPackCreated` event from the accepted exact-pack Audit
  Trail for the expected batch (case-sensitive). The default window is that UTC
  day plus one day either side, limited to complete UTC days. An entered serial,
  a different batch, an invalid timestamp, an example report or conflicting
  creation timestamps cannot establish this anchor.
- Reuse matching batch events from all imported history first. Show a direct link
  to a matching day if it is outside the selected period, favouring proximity to
  the creation date where known, otherwise a day on or before the alert.
- Without a creation date, show up to 31 complete UTC days ending one day after the
  alert (or the latest complete day, whichever is earlier). Suggest a contiguous
  gap of at most 31 days in this window, then an older gap within the bounded
  90-day search window. The 90 days are a search policy, not source retention.
- A day is a gap if accepted reports do not cover the entire UTC day. A request
  for a partially covered day can repeat existing evidence; imports deduplicate it.
  When no gap remains, state the actual covered range rather than asserting the
  pack or batch was never uploaded.
- Explicit manual dates still work, including older periods. Opening a suggestion
  is read-only. Loading or refreshing a report still requires the explicit
  same-origin action and uses the existing durable queue and genuine-only filter.

Pack creation is serial-level evidence; upload events and their counts are
batch-level evidence. The two are shown together without inferring that every
recorded upload event applied to the individual serial.
