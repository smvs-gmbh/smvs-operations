# FRS-EXCEPTIONS-001 — Exceptions and Alert Desk

Status **Draft v0.1**, 2026-11-17. Owner SMVS GmbH. The
[traceability matrix](../validation/RTM-001.md) records implementation and test coverage.

## FRS-EXC-001

Exceptions shall show the reported Alert identity and source values, distinguish
local Case status and provide search/filter navigation. Query completeness and
unknown values shall remain visible where relevant. Source market and
inter-market indication shall be treated as distinct observations.

## FRS-EXC-002

RCA shall link the retained Pack Audit Trail and upload evidence relevant to the
Alert. Retrieving a new report shall require an explicit, authorised action
for the appropriate scope. Evidence shall show missing or incomplete coverage.
Publish report content only when its identity matches the requested pack or scope.

## FRS-EXC-003

Alert Desk shall derive the scope of access from authorised invitations and
grants. Role, organisation and Case scope shall be checked on reads and writes.
Expired or revoked access shall be refused. Apply explicit evidence and
message visibility rules and keep internal review evidence in Operations.

## FRS-EXC-004

Alert Desk shall retain attributed Findings and amendments. A batch update
shall apply to the eligible Alerts within the confirmed scope and record the
Alert IDs and role. RCA shall show the current Finding per role, together with
the submitted CAPA status when supplied, separately from the NMVO assessment.

## FRS-EXC-005

Authorised staff shall record local Case status, cause attribution, decision
basis and optional notes. Resolve and Reopen shall reject stale reviews and
invalid scope. Batch closure shall require an explicit selection and produce
auditable per-Alert decisions. Follow-up and source revisions shall remain
traceable.

## FRS-EXC-006

Local routing and closure shall respect the documented SMVS procedure. For a
foreign-led case involving a Swiss pack, support the responsible foreign NMVO
and restrict local formal closure accordingly. For EU packs scanned in
Liechtenstein, scope the participant investigation to the End User. Represent
uncertain jurisdiction for review where available facts are insufficient.

## FRS-EXC-007

Track the response request and due date separately per applicable role. Show
Waiting for, Response due and Response status in Exceptions. A Finding or
progress update submitted after the request shall be detectable. Accept a
response reminder only after authorised review of the current recipients and
eligible overdue Alerts. Prevent duplicate same-day reminders for the same request.

The implemented pilot interval is configurable from one to 30 weekdays and
defaults to three weekdays from the request date in Europe/Zurich. The
[alert-based feedback target and calendar](../architecture/EMVO-Alert-Handling-Alignment.md#timing-and-monitoring)
remain open for process acceptance.

## FRS-EXC-008

The local synthetic test workspace shall exercise End User, MAH and NMVO views
and support a reset of its fixture store, including synthetic Pack Audit
Trails. Verify separation from operational data, delivery and production access.

## FRS-EXC-009

For the planned AMS Hub integration, match inbound records by unique Alert ID.
Show Hub Alert status, attributed Findings and closure information when
supplied. Provide a compact source summary in context/RCA and a dedicated
AMS Hub record tab with a readable, newest-first history, full source messages,
UTC timestamps and actor attribution. Preserve list scope across record tabs;
short event histories do not require configurable table controls. An Administrator shall be able to enable or disable automatic local
closure through a persisted setting. Audit the configuration change with its
actor, time and before/after values. When enabled, reconcile confirmed `Closed`
into local Case closure only when all linked Alerts are confirmed closed.
Record the origin, affected Alert IDs, applied configuration and source
observation in the audit trail and make repeated synchronisation safe.
Handling a later Hub reopening remains to be specified.

## FRS-EXC-010

The future background synchronisation shall consume paginated Hub investigation
changes by action time and match exact Alert IDs. Persist progress only after
the corresponding updates have been stored successfully. Use overlap and
duplicate detection to recover from retry or restart. Include changes for
locally closed Cases so that a later Hub reopening is detectable. Display
the last successful check and any failure or incomplete coverage.

Verify the API's time-window, archive and pagination limits and exercise
backlog recovery with 1,000 Exceptions. Confirm polling interval, initial
loading, cache freshness and reopening behaviour before implementation.
