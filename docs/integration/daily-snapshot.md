# Daily Snapshot import contract

Terminology follows [GLO-001](../architecture/GLO-001%20Operational%20Investigation%20Glossary.md), including its canonical Daily Snapshot definition. This pre-generated SSR NMVS Reporting API report describes selected source-reported state/context; it is not a complete extract of NMVS holdings.

## Delivery, authority and granularity

- **Products / Batches:** EMVS-originated Product and Batch/Lot information held in NMVS for the applicable national market. Product Code Scheme and Product Code retain their source meaning; this is not an identity mapping to regulatory preparations.
- **Organisations / Locations:** locally maintained Swiss/Liechtenstein SSR NMVS end-user context. The source `Organisations` dataset describes Local Organisations, distinct from physical end-users and from MAH/OBP/manufacturer roles and identifier namespaces.
- **API-version datasets:** technical/usage context; they do not independently establish Organisation master-data authority.

The NMVS holds individual pack/serial-number data required for verification, but individual Serial Numbers are not exposed by the Daily Snapshot. The validated report contains no individual Pack records. `Number Of Packs` and `Number Of Active Packs` are aggregate measures and cannot reconstruct Pack Context. The EU Hub holds Product and Batch/Lot data, not serial numbers; delivery through it is distinct from national-system holdings.

Lookup/request range, report/file metadata time, acquisition time, processing time and Effective Time are distinct. `Date Requested (UTC)` is not established as the Effective Time of every record. A report download is an Acquisition; reprocessing it is a Processing Run. Neither defines a Source Snapshot identity or revision. Mapping and Publication remain future conceptual stages.

## Validated parsing and processing contract

The implementation follows the observed CSV grammar, not a domain model. Fixtures
contain fictional values only. No domain mapping or fixed dataset inventory is
imposed.

Requests select a UTC calendar day and serialize inclusive bounds at 00:00:00Z
and 23:59:59Z. Acquisition DateTime columns store those instants as UTC-naive
values, consistent with the existing database convention.

Downloads explicitly request `Accept: text/csv`. Processing validates the retained
Content-Type before parsing, accepting `text/csv` with syntactically valid
parameters and rejecting absent/unrelated/malformed media types. Validation occurs
after raw artifact retention and creation of the durable processing attempt, so
failure and replay preserve acquisition provenance. Parameters do not select an
alternative decoder; strict UTF-8 remains the observed encoding policy.

The parser decodes strict UTF-8 with an optional BOM. It does not normalize
Unicode, replace invalid bytes or repair suspected mojibake. Python CSV parsing
uses unchanged newline sequences; only empty logical records outside quoted
fields delimit sections. CSV syntax removes quotes from names and values while
preserving their whitespace, embedded newlines and ordering.

The first section must contain one metadata header record and one value record.
The required columns are `Report Type`, `Report Name`, `Date Requested (UTC)`;
additional columns are preserved. `ParsedDailySnapshot.file_metadata` is an
insertion-ordered mapping of exact CSV headers to exact decoded string values.
It is distinct from `DailySnapshotResponse.report_metadata`, which contains the
API response metadata.

Each subsequent section has a single-field name record, a nonempty unique-header
record and zero or more rows of exactly that width. Empty datasets are valid;
reports without datasets are incomplete. Duplicate dataset names, duplicate or
blank headers, malformed quoting, mismatched widths and ambiguous metadata or
name records fail explicitly. Source header `__extra__` is an ordinary header;
no synthetic keys are introduced. Errors omit source values.

## File metadata persistence

Migration `0003_file_metadata` adds nullable JSON `processing_runs.file_metadata`.
Apply it in a separately approved deployment before running this version of the
processing code. Migrations 0001 and 0002 remain unchanged.

File metadata belongs to the interpretation attempt, not acquisition provenance
or immutable content. Each replay persists its own parsed mapping. Historical
runs and attempts failing before successful parsing retain SQL NULL; no backfill
is inferred. Successful parsing commits the entire mapping with the transition
to staging, before any staging inserts. Later staging failures retain that
metadata while rolling back all partial staging data. A failure of the metadata
commit itself can leave metadata absent; existing durable failure reporting still
applies.

The model exposes an insertion-ordered dictionary. The JSON storage representation
is an array of `[key, value]` pairs, because MySQL JSON objects do not preserve
member order. All columns and exact Unicode values survive without normalization.
API response metadata stays on the acquisition. Downgrading 0003 removes this
derived metadata column; raw bytes remain available for later reprocessing.

## Boundaries still requiring specification

The evidence does not establish support for duplicate names/headers, metadata-only
reports, alternative encodings, arbitrary metadata multiplicity, or alternate
separator conventions. Rejection of ambiguous input is deliberate. Dynamic
headers and datasets do not imply a business interpretation.


## Authenticated report destinations

A reusable validator requires an absolute HTTPS URL, no userinfo or fragment,
valid host/port syntax, and the configured Reporting API's exact normalized
origin. Host case and explicit HTTPS port 443 are normalized. Relative URLs,
foreign/suffix hosts, unexpected ports and malformed encodings are rejected
before the download token provider is called. Query parameters are retained and
are not treated as cross-origin. The configured API base itself must pass HTTPS
validation and cannot contain a query.

Both authenticated report lookup and download explicitly disable redirects on
each request, even if an injected HTTP client's defaults enable them. A download
3xx fails with a fixed diagnostic; no redirect target is contacted. Transport and
HTTP failure messages omit URLs, query values, response bodies and headers.
HTTPX/httpcore transport logging is suppressed context-locally for these requests,
including DEBUG headers; unrelated requests retain their normal logging behavior.


## Idempotent extraction (migration 0004)

A repeat acquisition/replay with the same source, retained content, parser and
transform version reuses an already successful extraction. The new processing
attempt stores `reused_from_run_id`; no new staging dataset or row is inserted.
Resolve `COALESCE(reused_from_run_id, id)` to read that attempt's data. Per-attempt
metadata and acquisition provenance remain independent. Failed attempts are not
reused; changed content or an explicitly different interpretation version is
processed separately and is itself repeatable.

A lock on the immutable content row serializes concurrent extraction decisions.
The success lookup uses a current locking read to avoid stale MySQL REPEATABLE
READ snapshots. The lock is held until the staging/result transaction commits or
rolls back. This changes the previous replay behavior, which created staging rows
for every successful attempt. Existing historical duplicate rows are preserved;
there is no automatic cleanup or publication of competing interpretations.

The [central scheduler](scheduler.md) can invoke the same acquisition service.
Its Snapshot adapter needs explicit NMVS configuration; no live NMVS connection
is enabled or exercised merely by configuring a disabled schedule.
