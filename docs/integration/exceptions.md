# NMVO Exceptions API – source observations

Status: implemented Alert import and local portal, 2026-11-04. On-demand Pack Audit
and Upload evidence retrieval is also implemented; investigation workflows,
participant messaging and AMS-Hub writes remain subsequent steps.
See [the dated implementation status](../overview/IMPLEMENTATION-STATUS.md) for
current counts and coverage.
This note does not change approval statuses or scope of controlled requirements.

## Evidence and architecture

The supplied `NMVO Exception API v1 Swagger.json` defines alert queries, recent
alerts and details. The implementation follows the paged query contract; it does
not confuse an acquisition row, Transaction ID, Alert ID, pack identity or case.
It applies SDS-002 §§5–8 and the provenance principles of ADR-004/ADR-006 and
GLO-001. FRS-EXCEPTIONS-001 is currently an empty placeholder, not an approved
workflow or status-mapping specification. NAMS-Architecture-Proposal remains a
discussion draft. No complete NMVS Alerts replacement is claimed.

The user confirmed PROD host `exceptions-api-ch.nmvo.eu` and authentication host
`api-ch.nmvo.eu`. Existing PROD credentials are reused without copying them into
source. Settings `NMVS_EXCEPTIONS_BASE_URL` and `NMVS_EXCEPTIONS_AUTHORITY` explicitly
bind the separate API host to the national source namespace already used by the
Reporting API. The original host remains recorded in source URIs. No assumption
that equal party IDs from unrelated authorities are equivalent is introduced.
The API version defaults to the server-selected latest when no explicit
`NMVS_EXCEPTIONS_API_VERSION` is configured; PROD returned 1.0. This is different
from the API version recorded inside a verification transaction.

## Acquisition and completeness

`POST /alerts` accepts an inclusive UTC `startTimestamp`/`endTimestamp` filter,
maximum 31 days per request. Historical CLI requests use at most 30-day chunks.
Only alert-query creation/escalation POSTs are sent; no alert or medicines state
is changed. Query results are read using `/alerts/data/{requestId}`, page numbers
starting at one and pageSize 1000. No arbitrary URI returned by the source is
followed. HTTPS, no redirects, safe query IDs and sensitive HTTP handling apply.

Every successful page's exact bytes are saved before validation. A generated
immutable manifest references only accepted final-query pages. Truncated queries
are escalated once using `/alerts/fulldataset/{requestId}`; an over-limit result,
failed escalation, remaining truncation, missing/duplicate page/Alert IDs,
inconsistent metadata or a record-count discrepancy refuses publication. HTTP409
is polled with a ten-minute bound; other errors fail to the scheduler's bounded
retry policy. Partial pages remain retained but cannot establish a complete import.

The supplied schema describes `records` as records in the response. Actual PROD
returned `records=1081`, `totalRecords=1081` on a page containing 1000 rows. The
parser permits this observed query-level count or the documented page-level count;
it separately validates every page, stable totals, and the sum of all delivered
rows against totalRecords. It does not use `records` as a pagination stop marker.
The empty current-day query was also verified successfully.

## Operational projection

Three additional tables retain accepted input and projected source assertions:

* `exception_publications`: canonical processing input, explicit authority,
  inclusive query window, query-start time, capture/publication times and counts.
* `nmvs_exceptions`: one row per source authority plus exact `uniqueAlertID`,
  separately preserving transaction/product/provided batch/stored batch/serial,
  caller Organisation/Location, last-update Location and markets.
* `exception_revisions`: unique observed payloads per source-qualified Alert ID,
  with copied source evidence and provenance. Identical repeats add no revision.

Publication is atomic under `mapping:exceptions`. A newer query may update the
selected observation; replaying an older acquisition cannot roll back selection.
Absence from another query never deletes an Alert. Original pages and canonical
staging remain available separately. Source detail is not a platform decision.
No source Open/Closed/investigation state exists in this API and none is inferred.
No Action Log is fabricated from ingestion or source revisions.

Source alert timestamps retain their original text and parse quality, with native
microsecond-capable MySQL columns. Missing/unparseable/offset-free timestamps stay
visible through a separate portal filter. Query start/capture/last pack update are
not substituted for alert occurrence time. Legacy integration-job timestamps
remain second precision; precise query filters come from retained manifest data.
Migration 0011 restores source precision from retained evidence where needed and
refuses lossy MySQL downgrade. Historical windows do not constitute a permanent
retention-policy approval; the purpose-bounded policy still needs specification.

GTIN/GS1/NTIN source codes are validated/normalized to GTIN14 for exact SAI lookup;
other schemes retain their original identity. Swiss display names and holders
come exclusively from the published SAI data. Original API productName remains
available only as a labelled source field. No SAI match is not proof of a foreign
pack. Provided/stored batch links remain separate. Local participant links use the
explicit authority and exact IDs; source Locations additionally require a local
source market, and last-update Locations their own local last-update market.
Unknown or foreign source locations are not silently assigned to Swiss locations.
Related exceptions require exact scheme/code/serial source spelling; they do not
establish a common root cause or genuine physical pack identity.

## Scheduling and recovery

The user requested **two hours**, implemented as an elapsed-time interval in the
existing portable scheduler, not a cron job:

```
.venv/bin/python -m app.integration.scheduler --configure exceptions --every-hours 2 --enable
.venv/bin/python -m app.integration.scheduler --run exceptions
.venv/bin/python -m app.integration.scheduler --serve
```

`interval_seconds=7200`; the next normal run is two hours after completion, with
existing three-attempt/five-minute failure retry behavior. Daily schedules keep
`interval_seconds=NULL` and their existing local-time/DST semantics. Reconfiguration
can return an interval schedule to daily. Failed workers retain the same mutex and
interrupted-execution recovery protections. Missed triggers coalesce; the exception
handler fills missed UTC days since the initial/earliest imported date and revisits
seven recent days through the current UTC instant. Today's interval is partial;
zero recent rows are not confused with failed acquisition. Late source insertion
outside this seven-day overlap is not guaranteed detected: the recent-alert cursor
and/or a broader reconciliation policy are future contract work. Manual historical
queries remain available. No claim of a complete incremental change feed is made.

```
.venv/bin/python -m app.domain.exceptions --start 2026-08-06 --end 2026-11-04
```

The scheduler is running locally, with no login/reboot service installed. SAI,
Snapshot and User Activity schedule settings are otherwise unchanged.

## Portal

`/exceptions` provides UTC range, identifier/product/batch/serial search,
error/market/business-process and optional organisation/source-location filters,
and paginated results. `/exceptions/{id}` shows labelled source and SAI/participant
context. `/exceptions/{id}/source` preserves original API fields and source-revision
provenance. The internal local portal still has no login; no new public service,
Hub transmission, closure or third-party notification is introduced.

Initial validation: 2,262 unique Alerts since 2026-08-06, 2,262 distinct source
payloads, successful two-page acquisition and current-day empty query. A complete
manual scheduler execution plus repeated publication retained both counts. A failed
first pagination validation remains as an audit record; the observed PROD count
semantics were addressed and the same time range was successfully imported.

## Next steps

See [the Pack Audit Trail / investigation proposal](../architecture/Exception-Evidence-and-Investigation-Proposal.md).
Step 2 now includes on-demand Pack Audit and Upload evidence; the Exceptions Audit
Trail importer remains open. Step 3 will add assessments, commands, actor
attribution and Action Log with independent local/participant/Hub states.

## Historical backfill and R20 boundary

A later historical backfill accepted complete query windows from 2026-08-01 through
2026-11-03 and a partial 2026-11-04 window. This extends the initial validation
figures above; current point-in-time counts are in the implementation status.

The supplied CR 106801 / EMVS_CR_32727 excerpts distinguish expiry of generated
query requests/results (HLAC030) from deletion in the API exception data store
(HLAC040), with underlying audit data retained. They do not by themselves confirm
pre-deployment L3/L4 backfill availability. Clarification was drafted for the
supplier; no new L3/L4 endpoint or schema adapter has been implemented. Current
imports use the existing Alert contract and cannot claim coverage of all L3/L4
exceptions. A failed retrieval is retried using a new source query; accepted local
evidence is not removed when a server-side request/result expires.
