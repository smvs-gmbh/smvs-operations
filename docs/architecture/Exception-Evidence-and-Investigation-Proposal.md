# Exceptions → evidence → investigation

Discussion proposal, 2026-11-04. Step 1, manual Pack Audit evidence and daily/on-demand
Upload history from step 2 are implemented; step 3 remains proposed. The
Exceptions Audit Trail importer remains open. See [implementation status](../overview/IMPLEMENTATION-STATUS.md)
for the verified current data snapshot and the boundary between implementation and proposals.
See [the implementation note](../integration/pack-audit-trail.md) for the demand-driven queue and schematic timeline.
No automatic per-Alert Audit Trail downloads, investigation assignments, status changes,
communications, AMS-Hub connection or NMVS Alerts cutover are enabled.

This follows ADR-004 (evolving Investigation Context, evidence vs assessment vs
decision), ADR-006 (explainable correlation), GLO-001 and SDS-002/NAMS proposal.
The user's three reference screenshots show an Alert list, Inspection with
participant-specific responses/status, and Action Log. They are UI/workflow
references, not an API contract or permission to send their shown comments.

## Keep three histories distinct

| Information | Ownership / meaning | Presentation |
| --- | --- | --- |
| Exception observation | NMVS assertion and subsequent observed source variants | Exception details / Original data |
| Technical pack history | NMVS Pack Audit Trail Report | Evidence timeline, source time, event/transaction IDs, original report version |
| Investigation Action Log | Internal or attributed participant actions/decisions, plus separately confirmed Hub events | Actor, role, action time, old/new values, reason, visibility, delivery/acknowledgement |

An imported record is not a human investigation action. A report event is not an
SMVS conclusion. A local saved comment is not a delivered MAH/End-user message.
Alert state, participant investigation state and internal case state need explicit
mappings; an Alert and an internal investigation need not have a 1:1 relation.

## Confirmed report contracts

Live `GET /report-types/...` checked on 2026-11-04:

* `PackAuditTrailReport`: all audit points related to a specified pack over its
  lifetime. Required parameters: `productCodeScheme`, `productCode`, `serialNumber`.
  Accepted GTIN aliases are GTIN/GS1/NTIN, PPN alias IFA. Batch is not a required
  parameter and is not a safe substitute for a possibly wrong provided batch.
* `ExceptionsAuditTrailReport`: audit points caused by exceptions over a requested
  time window; required `startDateTime`, `endDateTime`, optional business-process
  switches and `syntheticMonitoring`. It is not an individual pack's full history.

At the initial Step 2 assessment, the import included 2,262 Alerts but 1,604 distinct usable exact
scheme/product/serial signatures, with four Alerts lacking a usable pack signature.
For the 1,199 Alerts whose caller market is CH, there are 545 such signatures.
These figures illustrate possible deduplication only; source signatures do not
prove physical identity, and they do not settle which packs require investigation.
A single product-level pack report would mix different serial numbers. Product,
Batch and reference context can separately be reused from existing published data.

## Step 2: recommended retrieval policy

The implemented first step uses **an explicit “Load pack audit trail” action** on eligible local evidence
views; no list-row or page-open fan-out. Make the result states visible: not
requested, queued, being generated, available with capture time, failed, unavailable
or identifiers insufficient. A failure is not an empty pack history.

1. Resolve the requested source authority, exact product scheme/code and exact
   serial first. Only documented scheme aliases may be canonicalized; retain the
   literal requested values. Do not silently trim/case-fold serials or repair wrong
   provided product/serial values. Missing identifiers require review.
2. Coalesce concurrent/pending requests for the same report signature. Reuse an
   existing retained report version across linked Exceptions of that pack, retaining
   each link's reason and correlation limitations. This does not merge the Alerts.
3. Show **capture/as-of time**, latest relevant source event and source coverage.
   Reuse is conditional on purpose and freshness; “lifetime” does not cover future
   events. Offer an explicit refresh when new activity requires later evidence.
4. Queue downloads with a configurable concurrency/rate limit, bounded retry,
   cancellation/failure status and the existing credential/destination protections.
   Retain immutable original bytes before parsing. No external source call in a
   normal GET/detail render. A worker crash/repeated click must not multiply jobs.
5. Keep every report version used for an assessment linked to that assessment.
   A refresh updates current evidence without silently changing the historic
   evidential basis of an earlier decision.

Later, an approved action “start investigation” could request missing/stale local
pack evidence through the same queue. Automatic criteria require a documented
purpose, budget, trigger and ownership; do not prefetch for every incoming Alert.
A product-level context update is a separate optimization, not a replacement for
pack history. Retention/expiry must preserve already cited investigation evidence.

## Local / IMT responsibility remains a role question

The user states that foreign-initiated IMT cases belong with the other NMVO and
should not trigger routine SMVS investigation/report fetching. Apply that intended
boundary to later automation; do not infer it from the national Alert ID prefix.

The actual dataset demonstrates why `isIntermarket` alone is insufficient:
630 Alerts combine sourceMarket CH, a local single-pack business process and
isIntermarket=true. Another 1,059 rows have source markets AT/DE/ES and business
process National System Intermarket, while the boolean is not populated. Four
EU/MAH PPD Request rows are another context. These are source observations, not
an approved legal/workflow responsibility mapping.

Proposed review matrix before enabling automatic retrieval:

| Observed context | Proposed handling pending agreed rules |
| --- | --- |
| CH caller and local Organisation/Location, national single/bulk process | Candidate for Swiss operational review; distinguish initiation of intermarket lookup from fulfilment of a foreign request |
| Foreign caller market + National System Intermarket | Retain as relevant technical/source context; no automatic local investigation or Pack Audit Trail request |
| EU / OBP / MAH upload or incomplete/conflicting roles | Separate review; no automatic assumption of local end-user ownership |
| isIntermarket=true on its own | Insufficient for assigning or excluding responsibility |

Until verified and agreed, no IMT-triggered automatic report retrieval is enabled.
Manual cross-market evidence access, if later needed, requires the source to allow
it and an explicit purpose; a successful API call does not establish responsibility.

## Step 3: investigation boundary

Product direction agreed on 2026-11-04: **Shared investigation**, with End-user
collaboration before Hub integration. Participants contribute to a common
investigation; the NMVO makes the final closure decision. CRM contacts and SPOC
assignments support case-specific access. See the
[Shared investigation and CRM proposal](Shared-Investigation-and-CRM-Proposal.md)
for the delivery order, closure proposals and Airtable migration approach.

Use the screenshot's capabilities as input to a requirement/capability matrix:
SMVS assessment and private notes; End-user root-cause assertion; MAH/OBP response;
NCA escalation; shared Hub status and messages. Verify which are fulfilled by AMS
Hub versus local workflow before creating commands or copying UI controls.

Suggested detail views: **Overview**, **Technical evidence**, **Investigation**,
**Action Log**, **Contacts** with purpose-limited access. Root cause, origin and
participant responses remain attributed assertions until reviewed. Proposed actions
must record actor and delegated organisation/role, event and observation times,
old/new values, reasoning, linked evidence version and audience. A later group or
batch action needs an explicit selected scope and per-item outcome; matching a
batch string alone cannot authorize mass closure.

The existing no-login internal portal is suitable for read-only source review.
Before any investigation writes or external sharing, define identity/access,
concurrency, durable command idempotency, internal-note visibility and append-only
business audit. AMS-Hub transmission requires outbox/retry/acknowledgement and
reconciliation, separate from local acceptance. Do not recreate MAH collaboration
where the verified Hub interface already provides it.
