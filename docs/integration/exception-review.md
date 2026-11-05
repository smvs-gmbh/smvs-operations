# Local exception review and root-cause analysis

Implemented on 2026-11-04. Root cause analysis is a dedicated tab at `/exceptions/{id}/analysis`, separate
from Exception & context. It replaces the former audit/investigation placeholder.
Existing audit/report tabs remain available. Source evidence is unchanged.

## Work status and follow-up

- **Open**: default work list; includes To do and changed source observations.
- **To do**: requires a next action; optional follow-up date is a UTC calendar day,
  not a notification or scheduled reminder. The dedicated list covers all retained
  source dates and sorts dated follow-ups first. Other selected filters still apply.
- **Resolved**: requires a reason and hides the exception from Open. It remains
  available under Resolved/All and by direct URL. Use Reopen exception with a reopening reason to resume work.

Root cause classification and investigation checks are structured; the conclusion,
findings/evidence, next action and review reason retain explanatory text. None are
machine-confirmed conclusions. An exception can be resolved without a known cause,
for example where no local follow-up is appropriate, provided the reason is recorded.
Resolved is a local work decision, not an NMVS/AMS-Hub Alert closure, participant
agreement, CAPA completion or finding of pack authenticity. Foreign-market
responsibility is not inferred automatically.

If the retained source payload changes, a resolved exception reappears in Open as
Needs review. The prior assessment remains visible with a warning. Saving a fresh
review acknowledges the current source payload. Reimporting identical source data
does not alter local review records.

## Shared root cause for selected similar exceptions

Resolve the original exception with a classified, reviewer-confirmed root cause,
supporting findings, completed checks and a resolution reason, then open Resolve
similar exceptions. Candidates
must share exact source namespace, product scheme/code, provided and stored batch
roles, error code, requesting market, business process, intermarket flag and
attempted operation. Product and error identities and at least one batch must be
present. Source spelling is compared exactly in Python after database matching.
Serials may differ. Matching is a suggestion, never proof of a common cause.

The preview offers up to 50 not-currently-resolved candidates, across retained dates,
with links to inspect each. Check individual entries and provide a common rationale.
There is no automatic or implicit select-all action. Entries with To do status, a next action or a follow-up date cannot be processed
through this shortcut. Targets retain their own findings and next actions; the source
root cause and supplied common rationale are recorded separately for each target.
The category is copied as a working hypothesis; individual checks and confirmation
are not copied. Each history entry includes the structured assessment and a source
reference,
with a reference to the originating exception. A changed source/assessment or
invalid selection rejects the entire transaction; no partial batch is saved.

## Persistence and limits

Migration `0016_exception_reviews` adds `exception_reviews` and append-only application
history in `exception_review_events`. Historical snapshots include the assessed
source payload hash. Optimistic versions and source-row transaction locks prevent
stale overwrites. Identical saves with current versions do not create extra history.
The detail page shows the 30 most recent changes; all events remain stored.

POST forms require the exact same Origin and bounded form bodies; GET views do not
write reviews or call NMVS. The local portal still has no login, so history honestly
labels the actor Local operator (no authenticated identity). This is a local preview,
not an attributed multi-user investigation system. Staff identity, participant
permissions and a formal business Action Log remain requirements before shared use.

Further Intelligence cards, including geographic/market patterns, remain design work.
A source market describes transaction context and is not proof of physical pack
location or movement. CAPA, external communication and formal Incident Reports
remain in the [shared investigation proposal](../architecture/Shared-Investigation-and-CRM-Proposal.md).

## Guided cause catalogue — first local version

Migration `0017_structured_cause` adds nullable JSON assessment metadata without
reclassifying existing text. The catalogue is versioned locally; its codes are
not AMS-Hub codes and no cross-system mapping is assumed.

The dedicated tab has four steps: Classify the cause, Check the evidence, Record
the assessment, and Decide the next step. Each category presents two targeted
checks, explanatory guidance and links to the retained source/audit/upload views.
Selecting a category does not retrieve a report or infer a cause from an error.

Initial categories: Not yet established; Scanning or manual-entry error; Repeated
operation on the same pack; Incorrect operational process; Missing, late or rejected
pack upload; Product or batch master-data issue; Market or distribution context;
Technical or interface issue; Other evidenced cause.

Assessment levels: Not yet assessed, Working hypothesis, Confirmed by reviewer.
An unknown cause cannot be confirmed. Confirmation requires a conclusion, findings,
and each relevant check marked Checked or Not applicable, with at least one Checked.
Not-applicable checks require explanation in the findings. Completing checks is
not automatic proof; confirmation remains the reviewer's assessment. Findings
should identify concrete evidence, uncertainties and any outstanding follow-up.

Earlier free-text reviews remain retained and visible as unclassified. They are
not automatically confirmed and must be classified before sharing a root cause.
The shared category becomes a working hypothesis for each selected target, whose
individual evidence must still be assessed. Local Resolved remains independent
of cause confidence and may be used with an unknown cause and a documented reason.

## Explicit resolution actions

Migration `0018_local_resolution` adds resolution metadata and maps previous
Reviewed rows to Resolved with an explicit legacy marker. Original history entries
are unchanged. No new cause confirmation, resolution time or external closure is
invented for migrated rows.

- **Save analysis** stores a draft as Open or To do. It cannot resolve an exception.
- **Resolve exception** requires a resolution reason and a selected basis: Confirmed
  root cause (validated structured confirmation) or No further local action required
  (a documented decision, without claiming the cause is known).
- Pending follow-up, including previously saved tasks/dates cleared in the submitted
  form, needs an explicit acknowledgement of completion/supersession and explanation.
- Resolved analyses are locked against silent edits. **Reopen exception** requires a
  reason and retains the prior resolution in history. Changed source data still
  resurfaces the item; reopening a stale assessment clears its checks and downgrades
  cause confirmation to a hypothesis until reassessed.
- **Resolve selected exceptions** requires a resolved original with a confirmed cause,
  explicit target selection, common rationale, current versions and unchanged source
  evidence. Each selected target gets its own resolution entry referencing the
  originating assessment/version/hash. Pending target work blocks the entire batch.
  The copied category remains a hypothesis; individual checks are not fabricated.

These are local work-management decisions. Shared Investigation, participant
invitations/Magic Links and NMVO-to-Hub closure remain separate planned capabilities.

## Repeated Export evidence and batch reopening

For A7 Export alerts, the analysis tab summarises retained A7 Export observations
by exact source, market and location, with separate counts for the selected
product and batch. The date range describes observed alerts. In the case used
for the initial check, 289 alerts for 289 distinct serial numbers in the batch
were retained for the same DE location on 2026-11-04. This describes the observed
cluster. Longer-term recurrence and the reason for the repeat need separate evidence.
The B. Braun and Aarau workflow remains attributed operational knowledge in the
[evidence guided investigation proposal](../architecture/Evidence-Guided-Alert-Investigation.md).

The short local resolution requires a retained exact-pack report, a successful
Active to Exported transaction and a linked rejected Export at the same source
market and location. The operator supplies the reason. The history retains the
report version and both transaction identifiers. Pending work requires individual
review. No source report is requested when opening the analysis.

**Reopen batch exceptions** lists current local resolutions for the same source,
product and exact batch, preferring the stored batch and using the provided batch
when the stored one is absent. Select up to 50 and give a common reopening reason.
The update is atomic and preserves each previous decision in its history. Reopened
entries have status Open and are available under the normal Exceptions list filters.

## Audit trail in Operations

The exception's **Audit trail** tab displays local review events in reverse
order with pagination. The **Pack audit trail** tab displays the technical
transactions from the retained NMVS report. Existing analysis, Resolve and
Reopen events are shown from their stored before and after snapshots. This
includes per-exception events from batch resolution and bulk reopening.

The review write and its event are committed in the same transaction. The
event records its UTC time, actor label, target and originating exception,
previous and resulting values, and any saved decision reason and evidence
reference. The view derives its action label from the stored transition.
The local preview identifies the actor as an unauthenticated local operator.
It cannot attribute a historical event to an individual.

For platform-wide audit, introduce explicit event types and a common event
model with authenticated actor or service identity, timestamp, target type and
identifier, action, outcome, relevant changes and correlation identifier.
Future examples include permission grants and revocations and End-user
registration. Define access, retention and protection from tampering before
using that model as an operational control. Record business changes alongside
their audit events and restrict sensitive registration and permission data to
the fields necessary to explain the change. Retain existing review events
and their provenance when integrating the two views.
