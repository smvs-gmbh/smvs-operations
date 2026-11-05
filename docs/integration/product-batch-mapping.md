# Product / Batch / SAI operational mapping

## Scope

Migration `0005_product_batch_model` adds the current operational working model.
This is not a historical daily fact warehouse or an implementation of NAMS.
The mapper consumes explicitly selected successful Snapshot and SAI extraction
results; no external API is contacted. Existing raw data remains unchanged.

```sh
.venv/bin/alembic upgrade head
.venv/bin/python -m app.domain --snapshot-run SNAPSHOT_PROCESSING_ID --sai-run SAI_PROCESSING_ID --namespace SOURCE_NAMESPACE
```

A source namespace must be supplied explicitly and distinguish the actual source
instance. An endpoint-qualified namespace can identify the observed reporting
origin without claiming a PROD/IQE classification that has not been established.
Use separate namespaces when environments/scopes share an origin. The initial
publication is one selected source scope; switching its namespace is refused.

Repeated input results and mapping version return the same successful mapping
run without inserting or updating operational rows. Reused extraction attempts
resolve to their canonical result IDs. Validation checks source type, successful
status, content/parser/transform consistency, required datasets and actual counts.

## Model and identity

- `products`: stable platform identity, GTIN14 when valid. Unknown/non-GTIN product
  codes remain via source-qualified identity, never an invented identifier.
- `product_source_records`: source namespace + original scheme/code; current
  observed NMVS state and reported Product Version.
- `product_versions`: source-product-qualified versions. PMD details are retained
  only when observed for that version. Batch-only references have explicit status
  `batch_reference_only`; no current names/ownership are copied to older versions.
- `batches`: source product + exact Batch Id, with a separate actual Product Version
  FK, source expiry text, state and reported counts.
- `sai_holders`, `sai_preparations`, `sai_packages`: SAI partner/preparation/package
  references, including packages without GTIN.
- `product_reference_matches`: exact normalized-GTIN match, no match, ambiguous
  candidates or not GTIN-matchable. No foreign-origin conclusion is inferred.
- `mapping_runs`, `current_publications`: chosen canonical inputs, mapping version,
  outcome and atomic current publication pointer.

Natural key hashes use canonical JSON and SHA-256 over original source-qualified
identifiers. This preserves case/leading zeros independently of MySQL collation.
Approval/sequence/package and partner numbers are strings. GTIN8/12/13/14 are
validated and explicitly padded to GTIN14. Only the confirmed NMVS `GTIN` scheme
uses this mapping; numeric-looking codes from another scheme are not guessed.

SAI package identity is approval number + sequence number + package code.
Duplicate natural keys fail publication; ambiguous GTIN matches remain unresolved.
Missing nonblank SAI holder/preparation references or orphan Snapshot batches fail
publication. A missing/invalid GTIN alone does not discard a source Product or SAI
package. States, authorisation status and reported counts retain source meaning;
counts are not sales, uploads or stock movements. Expiry text is not guessed into
a date from length alone.

## Product Versions: document-backed interpretation

The supplied EMVO Master Data Guide (EMVO-00122 v10.0, 15 October 2025, pp. 7/36)
and Hub Functional Specification (EMVS0647 v18.0, SR1.16, pp. 26–30, 41, 73–75,
91–95) distinguish Product identity, version context and Batch-version reference.
A version change does not prove a transfer. The documented ownership transfer
changes ownership/escalation roles without mandating a new version. Existing PMD
versions may be updated; Batch-version references can also change in specified
PMD update paths. Versions are not immutable historical revisions.

The observed Snapshot has 22,443 Batches with a different version from the Product
row. They remain linked through stable Product identity and their actual version.
Earlier PMD details observed in this platform may be retained for that same version,
with their original provenance. Details of merely referenced versions remain unknown.

The two supplied document versions differ in details around version 0 and
retrospective market additions. The mapper implements no Hub upload/version
assignment logic and fabricates no ownership/effective times from those rules.
Swiss display names and authorisation-holder labels come only from SAI. They do
not identify historical Hub owners, OBPs, escalation targets or Batch Recallers.

## Publication and failure behavior

An independent `import_mutexes` row (`mapping:product-batch`) serializes mapping
invocations across processes. A durable mapping-run record precedes publication.
All working-model upserts, observation flags and the publication pointer commit
in one transaction. Any failure rolls them back; a sanitized failed-run record
remains. A failed input key can be retried; success of the same key is a no-op.

Stable rows are upserted, not replaced. Missing source rows become not observed;
identities and last known values remain. Previous version details are not downgraded
to batch-only just because the current Product row reports a later version.
Selected evidence is copied into operational records and nullable staging references
use ON DELETE SET NULL, so a staging ID is not the only retained explanation.
This does not implement retention/deletion policy or exhaustive relevant-change history.

Older source dates cannot replace the current publication. A different canonical
Snapshot result on the same requested day requires the explicit
`--allow-same-day-correction` flag; this is a deliberate source selection, not proof
of Effective Time. A successful old mapping invocation returns its existing result
and never rolls back a newer current pointer. Snapshot day is the requested UTC day;
SAI timestamp is filename/source time with unspecified timezone.

Mapping currently runs explicitly via CLI. The scheduler imports sources; automatic
selection/publication after every scheduled acquisition is a separate extension.

## Validation

Tests cover idempotent stable IDs/counts, Swiss names/holder linkage, missing and
ambiguous GTIN matches, Product/Batch version differences, case-sensitive Batch
identity, disappearance, stale/corrected inputs, retained prior-version PMD and
failure rollback after partial writes. Migration-chain tests verify preservation
of integration/staging IDs and schema agreement through upgrade/downgrade.

## Unresolved version markers observed in the real Snapshot

The initial real mapping revealed 96 Product rows with source version `-1`, and
3,908 Batch rows with `-1` (3,898) or `-2` (10). These values are outside the
positive PMD version numbers described by the supplied Hub documents. Their
specific SSR report meaning is not established by those documents.

Migration `0006_source_version_values` therefore retains the original version
text separately. A positive, in-range value has a typed numeric version; other
source values have nullable numeric version and status `unresolved_source_value`.
Products/Batches remain available and linked, but these markers are not claimed
to be confirmed Hub Product Versions. Unknown meaning is shown explicitly.
No marker is replaced with the current Product version or an invented zero.

The additive migration backfills existing numeric version text. Downgrade refuses
before DDL when unresolved numeric-null values would be lost. The input-key record retains its retry count; its status and last failure
are updated on retry. This first mapper does not provide a separate full history
of mapping attempts. No partial current working set was published.

## Original NMVS source view

Mapping `product-batch-sai-2` retains all supplied Product and Batch source fields
in operational evidence, rather than only the selected display/context subset.
This is not a full Hub PMD acquisition. Source Name/MAH fields remain attributed
NMVS values; the Swiss-facing display still exclusively uses SAI. The portal
exposes these originals through explicitly labelled read-only source pages.
