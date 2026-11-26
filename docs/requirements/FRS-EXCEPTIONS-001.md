# FRS-EXCEPTIONS-001 — Exceptions and Alert Desk

Status **Draft v0.5**, 2026-11-26. Owner SMVS GmbH. The
[traceability matrix](../validation/RTM-001.md) records implementation and test coverage.

Revision 0.2 specifies the implemented local URS-122 template behaviour and the
planned hosted TEST boundary under CHG-021. It does not approve the existing draft
or mark the TEST portability requirements implemented.

Revision 0.3 records the hosted TEST implementation in FRS-EXC-012 and its
remaining acceptance boundaries; approval is still open.

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

URS-123 / CHG-022: End User scope requires the requesting `source_location_id`
to match a currently observed, unambiguously assigned Location of the current
CRM-linked organisation in the same namespace and local source-market context.
Refuse an explicitly conflicting source Organisation ID. Missing source Location
IDs have no organisation-only fallback. Prior pack-update Locations and reviewed
export attributions do not grant access. Central scope selection shall apply to
case lists, direct views/templates, findings/batches and request/reminder routing;
current assignment changes invalidate access without deleting retained evidence.
MAH and internal NMVO visibility use their own roles and remain separate.

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

## FRS-EXC-011

Verified participants shall be able to retain optional plain-text comments for
all supported findings within the 1,000-character bound and retain private named
comment templates. Template ownership shall derive from current verified contact,
role and CRM organisation membership; reads/writes shall recheck current access.
Templates shall persist across authorised sessions, support versioned create,
edit, rename and soft deletion, enforce name/length/quota constraints, and retain
mutation/insertion events transactionally. Failed audit persistence shall not
leave a partial template mutation. Published comments shall be independent snapshots.

The investigation shall offer a compact Templates picker. Insertion shall preserve
the existing draft text and not submit a finding. Configuration shall be on a
separate My templates page with an internally constructed return to the exact
case or list context. Explicit same-tab navigation shall preserve the unsent draft
for up to 30 minutes in verified session/case scope. Restore supported answers only
when the case revision matches; otherwise restore only the comment with a review
message. Never restore authority-bearing publication/basis/submission values from
browser storage. If storing the draft fails, prevent silent draft-loss navigation.
Clear obsolete snapshots after submission and cached-page restoration.

This specifies the local verified-participant implementation under CHG-020;
NMVO closing-note templates and legacy case-only access are outside this increment.

## FRS-EXC-012

For the planned hosted TEST pilot, use a distinct store containing synthetic data,
explicit feature enablement, authenticated staff access and isolated service/source
credentials. Non-development execution shall not require disabling production
authentication or setting the environment to development. All invitation/update/
reminder links shall use the validated TEST participant origin. Validate gateway
Host/Origin, HTTPS cookies and narrowly trusted proxy peers; when crossing nodes,
verify private TLS and authenticate the private API. Public participant routes
shall not expose Operations administration, database access or fixture reset tools.

Keep capturing mail initially and enforce an approved-recipient boundary before
activating external test delivery. Record installed commit/manifest, schema,
configuration, retained fixture identity, supervised services, backup and rollback.
Verify the selected VPN/public mode from an external client. Existing production
Operations/Connect shall remain unchanged.

CHG-021 implementation: TEST runtime `42f85d6`, dedicated provider HTTPS
participant hostname, same-node loopback API and explicit TEST enablement.
Gateway/capture process configuration excludes database/source keys; fixed-origin
links, HTTPS cookies, Host/Origin/peer checks, TEST banner and aggregate command
ceiling are implemented. Staff remain on a private authenticated SSH tunnel;
VPN HTTPS staff access is not yet installed. Capturing mail has no external
delivery path. [Target evidence](../deployment/ALERT-DESK-TEST-2026-11-26.md)
records actual checks. Cross-node private TLS is not exercised by this same-node
deployment. Approved external mail, full restore/availability/timing and formal
protocol acceptance remain open; do not imply qualification of these controls.


## FRS-EXC-013

URS-124 / CHG-023: Eligible End User A24 cases shall provide a state-discrepancy
investigation with progress, own-side process/technical/other or not-my-side
findings; CAPA is required exactly for own-side findings. Support bounded optional
comments, private templates and amendment using the existing attributed/versioned
findings interface. Refuse identifier/upload fields, pack-on-hold and batch
commands for A24. Retain submitted text and event history; no pack transaction or
automatic local/Hub closure is triggered. Access is still rechecked by requesting
Location under FRS-EXC-003. MAH A24 entry remains outside this increment. Provide
matching NMVO participant preview and explicit pack-state guidance; missing batch
reference shall not be presented as the A24 investigation rationale.


## FRS-EXC-014

URS-125 / CHG-025: Use one active SendGrid dynamic template for invitations, codes,
case updates, findings requests and reminders. Permit SendGrid only in enabled TEST
with complete private configuration and an exact recipient allowlist. Use one
recipient, fixed HTTPS endpoint and disabled click/open tracking. Commit a delivery
attempt before network I/O, then persist accepted/failed/uncertain outcome and safe
provider reference. Never store bodies, codes, capabilities or API keys in receipts;
use a keyed fingerprint. Refuse automatic retries of unconfirmed outcomes. Expose
receipt history only to TEST staff with no-store/no-referrer; capture inbox contains
captures only. Keep key out of participant gateway. Require fresh invitations after
contact-version changes. Retain existing evidence through configuration rollback.
