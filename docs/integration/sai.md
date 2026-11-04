# Refdata SAI full-export import

## Scope and execution

The importer discovers the latest full export from the HTML at
<https://sai.refdata.ch/download>. It does not construct a download URL from a date
or assume a daily export. The page describes monthly data; the currently observed
history mostly shows publication on the fifth of the month around 03:00, with
exceptions. Publication time is source filename time, not a guaranteed schedule
or an established timezone. No scheduler is installed by this change.

Run from the repository root in the canonical environment:

```sh
.venv/bin/python -m app.integration.sources.sai
```

The existing `.env` configuration and guarded database session apply. Only
`smvs_operations` is permitted, verified on each transaction. Existing migrations
through `0004_import_scheduling` must already be applied. No new migration is needed.
The command prints acquisition/processing IDs and counts, without credentials or
source row values. It exits nonzero on failure.

Replay retained bytes without contacting Refdata:

```sh
.venv/bin/python -m app.integration.sources.sai --replay ARTIFACT_ID
```

## HTML discovery and download

Read export filenames matching `SAI-Export_YYYYMMDD-HHMMSS.zip` from table rows.
Associate each filename with that row's `data-url`/`href` structured-export link.
Select the largest valid complete timestamp rather than the first row or date
alone. Reject missing and ambiguous links/latest exports. Download destinations
must be HTTPS on exactly `sai.refdata.ch`, with the observed
`/download/structuredexportzip/<numeric-id>` path. Redirects are rejected.

Responses are streamed with a 4 MiB listing limit, 64 MiB ZIP limit and bounded
request timeout. Download metadata records listing URL, selected filename, source
URI, filename timestamp with unspecified timezone, response Content-Type and full
delivery mode. Content bytes and SHA-256 are retained before XML interpretation.
The ZIP itself is authoritative for validation; an HTML/error document downloaded
with status 200 is retained and then fails extraction rather than becoming data.

## Source-faithful XML extraction

The source is a full delivery, confirmed by the project owner on 2026-11-04.
Required members (matched case-insensitively by basename, with exactly one match):

| XML member | Root / staging dataset | Direct row elements |
| --- | --- | --- |
| SAI-Praeparate.XML | SAI_PRAEPARATE | PRAEPARAT |
| SAI-Packungen.XML | SAI_PACKUNGEN | PACKUNG |
| SAI-ATC-Codes.XML | SAI_ATC | ATC |
| SAI-Adressen.XML | SAI_ADRESSEN | ADRESSE |

Require namespace `http://sai.refdata.ch` and schemaVersion `3.2`. This is explicit
structural validation, not full XSD validation. Unknown schemas, namespaces,
required empty/missing datasets, duplicate members/fields, nested or attributed
fields and unexpected row elements fail explicitly. XML DTDs, entities and
external references are forbidden using `defusedxml`. No ZIP entries are extracted
to filesystem paths. Member count, total declared uncompressed size and selected
member size are bounded (100 entries, 512 MiB total, 64 MiB per selected member).
Other files, including sequences, declarations and SL, remain in the immutable ZIP
but are not staged in this first slice.

Preserve decoded source text, field names and XML row order. Empty XML elements
become empty strings; absent elements remain absent keys. Headers are the ordered
union of observed field names. XML-level fidelity (encoding, entities, markup)
remains in the retained original bytes. Do not add derived GTIN14 or padded
approval/package codes to raw staging rows.

## Transactions, replay and provenance

Use existing IntegrationJob, AcquiredArtifact/ArtifactContent, ProcessingRun,
StagingDataset and StagingRow models. Each acquisition has its own provenance;
identical ZIP bytes share immutable content. Each processing/replay attempt has
its own execution record. With the same source/content/parser/transform identity,
a successful extraction is reused via `processing_runs.reused_from_run_id` without
new staging datasets or rows. A content-row lock and a current locking read
serialize the decision and staging transaction on MySQL. Failed/incomplete attempts
are never reused. Changed bytes or an explicitly changed parser/transform version
produce a distinct interpretation; repeats of that interpretation reuse it.
Technical attempts are not multiple business facts.

Commit the job before acquisition and the ZIP before parsing. Commit the processing
attempt before parsing, and parsed member/schema metadata before staging. Stage
all four datasets plus success markers in one transaction, inserting rows in
batches of 1,000. Roll back partial staging on failure, retaining the original ZIP,
parsed metadata where available and sanitized durable failure information. Replay
does not redownload. Do not automatically retry a commit whose completion has been
verified by the existing failure handler.

No current-state publication, domain-table replacement, `refresh_mv_sai`, legacy
`smvs` access, schema changes, deletion or source-disappearance inference occurs.
Consumers resolve `COALESCE(reused_from_run_id, id)` for the selected successful
processing result. They must not union interpretations or historical legacy
duplicate extractions as business facts. Accepted publication and source-to-domain
mapping are the next stage, not implemented by this staging importer.

## Subsequent mapping contract

- Use canonical GTIN14 for GTIN-based pack matching. `normalize_gtin14` accepts valid
  GTIN8/12/13/14, validates ASCII digits/check digit and left-pads to 14. Blank is
  unresolved; malformed nonblank values fail validation. Preserve original values.
- All source packages remain, including those without GTIN. The helper is available
  and tested; derived identifiers are not yet persisted as a domain projection.
- Use only SAI Swiss preparation/package designations and SAI authorisation-holder
  references for Swiss operational display. Preserve NMVS names as source assertions
  and do not silently use them as fallback Swiss names.
- Resolve Pack -> authorisation number -> Preparation -> holder/partner -> Address,
  preserving source namespaces, source version and unresolved results.
- Keep all NMVS Products. Distinguish SAI-matched, no-SAI-match, not GTIN-matchable
  and confirmed non-Swiss. A missing match alone does not prove foreign origin.
- SAI membership, authorisation status and market availability are separate concepts.
  Full-delivery absence is not automatically deletion, withdrawal or inactivity.

## Validation

Tests use fictional ZIP/XML and HTML with mocked HTTP, guarded SQLite database
doubles, failure injection and offline replay. They cover timestamp selection,
ambiguous/foreign links, redirects/errors/limits, XML fidelity and hostile or
malformed structures, GTIN formats/check digits, deduplicated content, acquisition
lineage, durable failure and rollback of partial staging.


## Central scheduling

Use [the import scheduler](scheduler.md) for routine manual and scheduled runs.
The source-specific CLI remains available for diagnosis and offline replay.
Repeated downloads remain recorded as acquisitions; only data rows are reused.
