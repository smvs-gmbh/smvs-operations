# Daily Snapshot import contract

The implementation follows the observed CSV grammar, not a domain model. Fixtures
contain fictional values only. No domain mapping or fixed dataset inventory is
imposed.

Requests select a UTC calendar day and serialize inclusive bounds at 00:00:00Z
and 23:59:59Z. Acquisition DateTime columns store those instants as UTC-naive
values, consistent with the existing database convention.

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

## File metadata persistence gap

File metadata remains available to processing through the parsed representation,
but is not currently persisted separately. The retained artifact bytes allow it
to be reconstructed. Existing acquisition `report_metadata` stores API metadata
and is not overloaded with file metadata.

If structured persistence is approved, the smallest proposed change is a nullable
`processing_runs.file_metadata` JSON column in a separate migration. Parsed file
metadata belongs to a particular parser attempt, including replays. Persist it
with successful staging; leave historical/failed attempts null rather than infer
values or alter acquisition provenance. Migration 0002 is unchanged.

## Boundaries still requiring specification

The evidence does not establish support for duplicate names/headers, metadata-only
reports, alternative encodings, arbitrary metadata multiplicity, or alternate
separator conventions. Rejection of ambiguous input is deliberate. Dynamic
headers and datasets do not imply a business interpretation. Authenticated URI
restrictions remain a separate pending change; this task does not define a new
cross-origin URI contract.
