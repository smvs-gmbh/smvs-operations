# FRS-CORE-001 — Core Operations

Status **Draft v0.1**, 2026-11-17. Owner SMVS GmbH. Scope covers the local
validation candidate and identified release checks. The
[traceability matrix](../validation/RTM-001.md) records implementation and test coverage.

## FRS-CORE-001

The internal portal shall require an authenticated staff identity where enabled
for the release environment. Server-side authorisation shall enforce the
Administrator and NMVO role boundaries on protected reads and writes. Revoked
access shall be rejected. The release check shall verify configuration and
network boundaries in the target environment.

## FRS-CORE-002

The portal shall support searchable and filterable views of the published
Products, Batches, Organisations and Locations and link related records by
source-qualified identifiers. An unresolved link shall be distinguishable from
a verified match. SAI-derived names and source attributes shall retain provenance.

## FRS-CORE-003

The CRM shall allow authorised staff to maintain records and scoped contact
assignments. Archived records shall be excluded from new assignments where
applicable. Permanent deletion shall require confirmation and enforce
dependency and access-grant rules. Each Notes entry shall have an automatic
date, text, completion state and an optional Important or Review later flag.

## FRS-CORE-004

Connect shall accept authenticated intake submissions within its configured
contract, persist the accepted receipt and review record atomically and handle
identical retries without creating duplicate review records. Email confirmation
shall use an expiring, single-use action. SMVS review and CRM/NMVS linkage shall
remain explicit. Temporary private data shall follow the defined expiry and
erasure rules.

## FRS-CORE-005

Catalogue Overview shall report Products, Batches and reported Packs for the
published Snapshot and distinguish the SAI-matched breakdown. Alert Trends
shall show the selection window, completeness and applicable source/CRM
filters. Drill-downs shall reproduce the selected Alert population.

## FRS-CORE-006

The release record shall identify the application build, database migration and
relevant configuration. Where a release migrates existing data, verify that
retained Cases, Findings, access state and audit records survive. Recovery
shall verify data and evidence integrity after restoring a controlled backup.

## FRS-CORE-007

Every user or system transaction shall retain the applicable actor or service,
UTC time, action, affected record or selection, outcome and correlation ID.
Record state changes with before/after values or version references. Include
reads, exports, interface requests, automatic Case decisions, configuration,
access changes and failed transactions. Record external event time separately
from local receipt time. Define one auditable transaction per business command,
read request or interface call, linking batch actions to their affected records.

Persist a successful business mutation and its audit event atomically.
Retain rejected or failed attempts through an appropriate independent path.
Protect entries against unauthorised modification and deletion, preserve
corrections as later events and make audit access itself auditable. Record
query scope and result counts where sufficient for reads. Exclude credentials,
access tokens and private payload contents from audit text.

The [audit retention and recovery concept](../validation/AUDIT-BACKUP-CONCEPT.md)
records the proposed archive controls and the release decisions still required.
Preserve the attribution of historical records when actor details are unavailable.

## FRS-CORE-008

Operational drafts and exports shall identify the source selection and
applicable access scope. MAH correspondence shall remain under staff review,
with unresolved organisations distinguishable from verified recipient links.

## FRS-CORE-009

Where AI-assisted search is enabled, the service shall send only approved inputs,
identify the output as a suggestion and require staff to apply or revise it.
The prototype requires a separate decision on production enablement and data scope.
