# Snapshot Local Organisations and Locations

Migration `0007_snapshot_participants` adds `local_organisations`, `local_locations`,
`participant_mapping_runs` and `participant_publications`. These represent NMVS
Local Organisation/Location context, not a general organisation/MAH/OBP master or
a confirmed cross-source legal identity.

Publish an explicitly selected successful Snapshot extraction:

```sh
.venv/bin/python -m app.domain.participants --snapshot-run PROCESSING_RUN_ID --namespace SOURCE_NAMESPACE
```

Reused extraction attempts resolve to their canonical successful result. The mapper
uses only the `Organisations` and `Locations` datasets, independently of SAI and the
Product/Batch publication. Missing datasets or count mismatches fail; explicitly
present empty datasets are allowed. The selected snapshot day is the requested day,
not an inferred Effective Time.

## Identity and relationship rules

- Organisation identity: source namespace + exact `Organisation Id`.
- Location identity: source namespace + exact `Location Id`.
- SHA-256 keys over canonical JSON preserve case, leading zeros and source scope
  independently of the database's default collation. Duplicate IDs in a delivery
  fail publication rather than overwrite. This enforces the supported source-key
  contract; uniqueness observed once is not a guarantee for all future deliveries.
- Locations link to Organisations by the exact source Organisation Id, not names.
  Source namespaces must match. Reassignment changes the relationship, not the
  stable Location identity. There is no blanket relationship-history table here.
- If the parent is absent, keep the Location and original parent ID with explicit
  unresolved-link status; do not invent or substitute an Organisation. A later
  complete match can resolve it.
- Only the currently selected source Organisation set establishes a current link;
  an older retained but absent Organisation is not treated as present.

Organisation and Location statuses remain independent raw NMVS assertions. The
mapper does not infer eligibility, licensing, access rights or regulatory status.
`Deleted`, `Suspended`, `Expired` and other non-active source states are retained.
Disappearance in a subsequent delivery sets `is_observed=0`, not source status
Deleted; stable IDs and last known values remain available in the database.

Dates remain original source text. Postal codes are strings. Equipment Count is an
optional nonnegative integer; missing is not automatically zero. Original Location
side Organisation names/types remain in evidence, rather than overwriting the
Organisation record's fields.

## Atomicity, replay and provenance

A durable participant-mapping row records the canonical Snapshot, source namespace,
mapper version and outcome. A dedicated `mapping:participants` mutex serializes
publication across processes; it does not lock or modify the SAI/Product mapper.
All observation flags, upserts and the current participant pointer commit together.
Failure rolls them back; a sanitized failure and retry count remain on the mapping
record. A retry updates that record rather than providing full per-attempt history.

Repeated successful input + namespace + mapping version returns the same result
without new rows or changed IDs. Older snapshots or namespace switches cannot
replace the current publication. A different snapshot result on the same requested
day requires `--allow-same-day-correction`; source selection is explicit.

All supplied fields are retained as evidence with nullable staging links using
ON DELETE SET NULL. The original-view fallback therefore survives staging expiry.
Contact fields are not promoted to generic participant columns or the directory;
they remain in the explicitly selected original Organisation view. No notification,
external transmission or automatic CRM integration is implemented.

## Portal

- `/organisations`: name/ID search, type and status filters, Location counts and pagination.
- `/organisations/{id}`: Organisation context, original lifecycle dates and related Locations.
- `/organisations/{id}/source`: all original Organisation fields, including contacts.
- `/locations`: Location/Organisation/ID/city/postcode search and Location status filter.
- `/locations/{id}`: Location details and its separate Organisation relationship.
- `/locations/{id}/source`: all original Location fields.

Source pages and lookups are restricted to the selected current namespace/publication.
SAI dates/names are not shown as participant provenance. The existing local-only,
read-only portal and its official SMVS logo are retained; login remains a later step.

## Initial data and validation

Snapshot result 1 contains 58 Organisations and 45 Locations. All IDs are present
and unique within the corresponding dataset; all 45 Locations link to a current
Organisation. Organisation statuses: Active 44, Expired 6, Suspended 4,
Deactivated 3, Pending 1. Location statuses: Active 38, Organisation Suspended 3,
Deleted 4. These are source counts, not eligibility conclusions.

Tests cover stable identities/idempotency, parent reassignment, orphan retention,
case-sensitive IDs, disappeared rows, duplicate keys, partial-write rollback,
stale/corrected snapshots, empty/missing datasets, source-view escaping/expiry,
filters and pagination. The real mapping was repeated concurrently: no additional
rows and no changes to Product/Batch or staging counts. Upgrade/schema comparison,
real HTTP responses and browser directory/detail navigation were verified.

The scheduler still handles acquisition. Participant mapping/publication is an
explicit command in this delivery; an automatic post-acquisition mapping policy
has not been introduced silently.
