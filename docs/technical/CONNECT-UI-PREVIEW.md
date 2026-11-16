# SMVS Alert Desk — local design preview

2026-11-10. A standalone synthetic prototype for owner review, not a public
collaboration release or an implementation of case grants/persistence.

## Run and scope

Run `.venv/bin/uvicorn app.connect_preview.app:app --host 127.0.0.1 --port 8013 --no-access-log`
and open `http://localhost:8013/`.

The prototype has its own shell, CSS and JavaScript. It imports no database,
registration configuration or source clients. It is not mounted in Operations or
the public Connect gateway and is not included in the gateway's explicit deployment
allowlist. The original `/` preview and the new `/proposal` view each expose only their fixed HTML/CSS/JavaScript assets. Browser connections and
form submissions to services are disallowed by CSP. No registration, CRM, alert
lookup, email, upload, invitation or permission operation is exposed.

All identifiers, product names, organisations and evidence are fictional. They
are not claimed to be SAI/NMVS records. Submitted responses and messages are
simulated in the current tab, not stored in Operations. Reload/reset clears them;
there is no localStorage or persistent browser database. User-entered messages
are inserted as text, not HTML. Do not enter real personal or pack data during
this design review.

## Participant layout

A slim SMVS Alert Desk header replaces the internal Operations navigation. It shows
the represented organisation, demo case/alert reference, participant status and
three tabs:

- **Investigation:** alert context, schematic pack chronology, orange Intelligence
  observations and the short response. The response sits next to evidence on a
  wide screen; mobile provides a direct jump to it.
- **Shared updates:** attributed evidence, findings, progress and messages. The
  participant can ask a question or share progress. The prototype audience is
  always the participant and SMVS; later MAH sharing must be explicitly designed.
- **Pack details:** exact submitted identifiers and a dated batch reference.
  Observed values remain distinct from authenticity and alert-time conclusions.

Use the existing SMVS colour family, a typographic Connect wordmark, soft buttons,
readable card hierarchy and an orange automatic-analysis label. Use arrows on
context links, clear UTC times and responsive layouts. Tabs support arrow/Home/End
keys; dialogs support Escape and native modal focus behaviour. Source data in the
future live projection must retain its spelling and SAI-only Swiss name policy.

## Click-through scenarios

The top design toolbar changes between A7 repeated Export and A3 serial-length
mismatch. **Reset preview** restores the fictional starting state.

For A7, existing evidence shows creation, a successful Export and a rejected repeat
three seconds later at the same reported location. For A3, the transmitted serial
has 12 characters against a 14-character exact-batch reference. The A3 view does
not fabricate pack creation/history or request a report for a possibly misread
serial; physical-pack comparison comes first.

The participant chooses a procedural issue in their own process, a technical
issue, continuing investigation or differing findings. An explicit own-process
procedural choice records End User as their proposed Origin; technical/other
findings allow an Origin selection with Not established as the default. All are
participant assessments awaiting NMVO review, not automatic confirmed attribution.

**Corrective measures will be taken** is unchecked and optional. The two optional
text fields are **Additional findings** and **Corrective measures / comments**.
No action catalogue, internal CAPA proof or effectiveness audit is demanded.

**Review & submit** opens a concise summary and identifies the audience. The
simulated submission appends a contribution, shows **Awaiting SMVS review** and
allows a later update without replacing the earlier contribution. An unfinished
investigation can be submitted as progress without a corrective-action commitment.
Draft saving stays in the current tab. No End-user Close/Resolve control exists.

## Review and next implementation gate

Check whether the short response is sufficiently clear, evidence has the right
prominence, Origin is understandable and shared/private audiences are explicit.
Only after this design review should real case/publication tables, participant
grants, durable contributions and the dedicated Connect API be added. Preserve
NMVO-only decisions and independent source/work states. A successful simulated
submission is not a security or production acceptance test.

Validation: isolated HTTP route/CSP tests and headless browser checks for short
submission, optional text, progress, Origin, text-safe messages, draft feedback,
scenario/reset, amendments, keyboard navigation, mobile width and enlarged text.

## Review feedback: exception-first without pack history

Owner feedback after the initial preview: Pack history is optional; the participant
must be able to understand an exception from its own API observation. IMT does not
by itself mean that all pack details are absent. Missing report values must remain
absent, rather than being invented or reconstructed into audit events.

Proposed simplification for review (not yet implemented): use two principal tabs,
**Investigation** and **Shared updates**. Rename/move Pack details into expandable
**Alert details** within Investigation. Replace the separate alert, history,
automatic-analysis and What happens next cards with one concise explanation and
an evidence section. The short participant response remains next to it. If there
is no pack audit report, omit its timeline rather than showing an empty request
panel to the participant. Put the next-step note below submission.

An A7 supplied-state example supplied by the owner contains a requested Supply,
current Supplied state, three reported dispense attempts, identical source and
last-update location IDs and a last-update timestamp 6.980 seconds before the
alert. Those fields support a plain-language description of an already-supplied
state and a rejected further Supply attempt. They do not establish three
successful dispensings, the scope of the attempt counter, the operation executed
at the last update or a confirmed procedural cause. Label the time as **Last
reported update**, not as a proven successful Supply/Export event.

A compact explanation can say: **This pack is already marked as supplied. Your
latest attempt to supply it was rejected.** Below it, show only useful observed
facts: same reported location, last update about seven seconds earlier and three
reported supply attempts. Mark these as **Exceptions API observations**. Distinguish
them from a report-based chronology and from participant findings.

Keep product/GTIN, batch and full serial accessible in the case-specific pack
identity area for comparison. Additional timestamps, provided expiry, transaction
references, exact source error/event messages and technical client fields belong
in expandable details, only where that participant is authorised to see them.
A normalised English explanation is application guidance, not replacement of the
retained original message. Prefer reviewed code/operation/state mappings to an
unreviewed free-text or generative translation. Unknown or contradictory codes
must fall back to neutral description, not a guessed cause.

Source market CH and an intermarket flag require role review, not automatic
classification as a foreign End-user case. An Alert ID prefix alone does not
establish initiating/fulfilling responsibility. The current no-automatic-IMT-report
policy remains in force until reviewed role/scoped-access rules are implemented.
Do not copy the real example identifiers or serial into this synthetic prototype
or repository fixtures; demonstrate the structure with fictional values if the
proposed layout is accepted.


### Priority update: avoid unnecessary routine A7 questionnaires

The owner subsequently clarified that well-supported same-location A7 repeats
belong primarily in internal evidence-led resolution, with a prevention notice to
the End-user. They need not enter the demonstrated response form. The current A7
click-through is a layout experiment, not the required default workflow. Prioritise
A3 and evidence-dependent A2 scenarios: existing automatic observations first,
pack photograph and relevant technical checks from the End-user, exact-pack upload
evidence from the MAH when that participant phase is introduced. See the
[owner decision](../architecture/Shared-Alerts-Management-End-User-Pilot.md#owner-decision-routine-a7-handling-and-a3a2-priority--2026-11-10).


## Revised alert-type-led proposal — 2026-11-10

Open **http://localhost:8013/proposal**. The initial preview remains at `/` for
comparison. The revised proposal uses the same isolated app and security boundary;
its assets are `/proposal.css` and `/proposal.js`. It is not the live Connect app.

The case selector demonstrates three fictional paths:

| Path | Evidence first | Participant task |
| --- | --- | --- |
| A3 | Exact batch known, 14-character serial matches the reference length, individual upload unconfirmed | Printed serial comparison, packshot selection and one technical-check choice |
| A2 | Product/other batches known, exact batch absent; upload search period and coverage explicit | Printed batch comparison, packshot and relevant reading checks; SMVS coordinates the MAH question |
| A7 | Successful Export followed by rejected repeat at the exact same reported location | Already locally resolved by an attributed manual NMVO decision; prevention notice and optional acknowledgement/update |

There are only two tabs: **Investigation** and **Shared updates**. The compact pack
identity strip keeps the full reported serial available. **Alert details** and
**Evidence & sources** expand when needed; there is no empty Pack History panel.
Orange Intelligence observations distinguish supported matches from unanswered
questions. Snapshot observations retain their date and are not alert-time proof.

A3/A2 answers may be incomplete: review/submit can send a progress update without
mandatory free text or corrective-action commitment. The review identifies the
participant/SMVS audience. Updates append, remain text-safe and do not close the
alert. For A7, the local decision remains resolved even when an acknowledgement
is submitted. No automatic rule execution, external closure or delivery occurs.
The upload-follow-up card depicts a fictional coordinator status; a live card
must be driven by an actual recorded task, not shown as in progress by default.

Packshot selection uses a local file picker and displays **only the filename**.
It does not read file contents, upload, inspect, persist or make them available to
SMVS. It must not be described as received evidence. The actual photo path still
requires the previously specified scoped upload and storage controls.

Reference reviewed: `/Users/reinhold/Documents/Development/VerifyIt-Guides/README.md`
and `verifyit_knowledge_base.json` (CH API 3.1, generated 2026-08-27). GA-002
(compared printed/decoded identifiers), GA-010 (intended DataMatrix), GS-001
(data not found) and GS-005 (local processing) inform the question composition.
This is a source review and reuse proposal, not a runtime import or an authority
to supply medicine. The Connect text asks for investigation facts; it does not
copy a dispensing outcome or treat local resolution as supply permission.

Validated with isolated HTTP/CSP checks and a headless browser: A3 contribution,
A2 incomplete progress, filename-only photo selection, A7 optional acknowledgement,
text-safe updates, tab keys, Escape, 390px layout and 125% text. No network writes
were issued. Desktop, mobile and A7 screenshots were inspected locally.


### Correction: operation-code context and missing identifiers

The revised proposal now separates **NMVS response** (source-based explanation)
from **Intelligence** (our additional observations). Fixed synthetic examples use
reviewed CH API 3.1 mappings from VerifyIt-Guides: A3/41020001, A2/41020002,
and A7 + Export/51320801. Preserve the original operation-code message in details.
The A3 example explicitly includes an IMT lookup; a real case must obtain that
fact from its actual source context, never from the alert code alone.

The earlier “SMVS is checking the upload / In progress” card has been removed.
There is no actual follow-up task behind it. The source has already reported that
the submitted identifiers were not found. What remains unresolved is the cause:
printed/scanned discrepancy, a technical issue or missing data, for example.
Only after comparing the correct printed identifiers might MAH upload evidence
help establish why the lookup failed. Do not imply a fresh repeat lookup is the
investigation or that this response proves an exhaustive search of every market.

The future investigation catalogue must key its explanation and conditions by
operation code + API version/context, alert type, attempted operation and relevant
state/IMT fields. Code 41020010 adds a length/format mismatch and possible technical
issue within A3; that should focus the questions without confirming the cause.
Code 51320801 can accompany A7 or A24 depending on attempted operation. Never
select a route by code or alert in isolation; unknown/conflicting mappings use a
neutral response with original evidence and NMVO review.


### Narrative and participant contacts — 2026-11-10

This prototype is explicitly an **End-user view**. A later MAH view shares the
case narrative but replaces pack/scanner questions with upload/serialisation
questions. It is not a universal identical questionnaire for both parties; contact
visibility does not enrol someone in the case or grant access to contributions.

The narrative now identifies the fictional product, MAH, reporting location,
attempted operation and resulting alert before explaining the source response,
possible causes and the remaining participant questions. The A7 narrative describes
an Export request, not an unevidenced physical scan. Live narratives must use
source-supported actions and display missing or ambiguous identities explicitly.

**Contacts** expands from a short contextual link beside the narrative. It shows
location/organisation contact, nominated MAH alert contact and SMVS coordination,
using synthetic names and reserved example.invalid email addresses. Phone numbers
are explicitly unavailable in this example. A live projection needs the correct
location-level contact or an explicitly labelled organisation fallback, reviewed
case-specific sharing, SAI-derived Swiss MAH identity and a separate reviewed CRM
contact match. No automatic exposure of the CRM directory or assumption that a
listed contact receives messages. Swissmedic/NCA is deferred until an authority
contact and escalation/publication workflow are specified.

## Shared case with two participant perspectives

Open **http://localhost:8013/case-study**. This third view leaves `/proposal` and
`/` available. Its fixed assets are `/case-study.css` and `/case-study.js`, plus
the existing proposal stylesheet. It uses the same isolated asset-only app.

### Case-derived example and provenance

A read-only inspection of the local development database on 2026-11-10 found an
A3 / operation code 41020001 with National System Bulk Pack API, attempted operation
VERIFIED and isIntermarket false. Organisation and location source identifiers
matched the published participant namespace/run and the location's parent matched
the organisation. SAI-derived product and holder associations were available.

The product had 28 observed batches in the currently published 2026-11-10 Snapshot,
but no exact match for the provided batch. The transmitted serial length was 14;
there was no exact-batch reference to validate length/format and no retained pack
audit report. These structural facts inform the first example. The later Snapshot
is not treated as proof of alert-time state. Existing source rows were not changed,
and no imports, report requests, invitations, emails or case decisions were made.

All names, contacts, product/pack identifiers and displayed event timestamps in
the unauthenticated design preview are fictional replacements. No real serial,
CRM contact details or raw evidence payload was exported. A name available through
SAI is represented by a fictional name only in this anonymised demonstration;
a real projection must retain the established SAI-only Swiss naming policy.

The second scenario is separately labelled **simulated**: PMD present, no batches
observed. It is derived from the owner's Swiss practice observation, not a claim
that a matching case was found in the inspected sample. Its operation code and
original message are explicitly not established; it is not mapped automatically
to the case-derived bulk branch. The A7 example remains synthetic.

### Roles, contributions and deliberate sharing

The design toolbar switches **End User / MAH** within one case. It is a design-only
role switch, not an access-control implementation or an invitation mechanism.
Both perspectives see the narrative, source response, Intelligence, participant
roles and expandable case contacts. End Users receive pack/technical questions;
MAHs receive a short upload-finding selector and optional evidence-reference text.
For A7, the MAH has no questionnaire or corrective-action acknowledgement.

Responses are initially marked **submitted to SMVS**, visible in that participant's
preview plus the conceptual NMVO audience. Switching roles does not expose the
other participant's unshared submission. The design-only **Demo: share reviewed
findings** button simulates an explicit SMVS review/publication; both roles then
see the attributed contribution with a shared-audience label. It does not resolve
the case. Real publication scope, consent/audience and edits require the actual
case authorisation model; hiding a message in client-side JS is not security.

No real MAH participation or pending task is inferred from a CRM match. The participant
strip depicts proposed involvement and is explicitly labelled as a simulation.
All responses are in-memory only. A case change/reload clears them; photo selection
still reads only a filename and never uploads or retains contents.

Validation: browser checks covered the bulk/no-IMT context, absence of a borrowed
serial reference, participant-specific forms, response review, private/unshared
versus explicitly shared contributions in both directions, MAH evidence text,
PMD-only scenario fallback, A7 MAH scope, Help/Escape, mobile width and 125% text.
HTTP/CSP checks cover the new assets and unsupported write paths. No network writes
occurred; desktop End-user/MAH screenshots were visually inspected.


## Focused alternative with decision or next action first

Open **http://localhost:8013/focused**. This is a separate End-user alternative;
all earlier designs remain unchanged. Fixed `/focused.css` and `/focused.js`
assets use the same isolated, no-service preview boundary.

Owner feedback: the previous layout had too many equally prominent panels and
messages. The essential A7 content is the local SMVS decision and prevention
follow-up. Intelligence explains the decision; it should not compete with it.

The initial A7 screen therefore contains one outcome heading, one short explanation,
a quiet product/MAH identity line and one action card. The optional corrective-
measures commitment and optional comment reveal a send button only when there is
an update to send. A confirmation stays inside that card; no unrelated status
banner is added above the story. The existing local decision remains unchanged.

**How SMVS reached this decision** starts collapsed and contains the orange
Intelligence label, concise evidence and attributed fictional decision record.
**Pack details & contacts** is also collapsed. Conversation opens on demand in a
dialog. There are no main tabs, participant strips, concurrent response panels or
upfront chronological feed. The development comparison controls are collapsed.

For an open A3, the same focused frame presents one question at a time: compare
printed identifiers, optionally select a packshot filename, then indicate the
technical-check result. A review step allows optional comments and commitment.
Unfinished checks can be submitted as progress. Back preserves the current answers;
amendment appends a new simulated contribution. Neither submission nor an optional
commitment resolves an A3. The PMD-only example retains unknown operation/routing
facts and does not claim a confirmed missing historical upload.

This alternative intentionally focuses on End-user experience. The earlier
case-study view remains the place to review MAH-specific inputs and simulated
cross-participant publication. No production capabilities or role model are replaced.
All names/identifiers are fictional and responses are in-memory only; packshot
contents are not read or uploaded. Reload/case switching clears the simulation.

Validation: A7 optional feedback and unchanged decision, text-safe conversation,
A3 navigation/back/review/amendment, PMD fallback, native Escape/modal behaviour,
390px layout and 125% text. Desktop/mobile A7 screenshots were visually inspected;
browser checks recorded no writes or JavaScript errors. HTTP/CSP checks cover the
new fixed routes and retain the original preview route checks.


## Compact middle-ground alternative

Open **http://localhost:8013/compact**. The owner asked for a middle ground between
case-study density and the focused wizard: participants should not need to read
much. Preserve every previous design for comparison.

This view displays the outcome, a one-sentence explanation and product/MAH context,
then a slim orange Intelligence strip with only a short evidence summary. Detailed
supporting sources expand inside that strip. The next action remains one prominent
card. Pack details/contacts are collapsed, and conversation opens on request.
There is no global feedback banner or participant dashboard.

A3 uses two short selectors on one page (printed identifiers and technical checks),
an optional filename-only packshot and optional comments/commitment. There is no
wizard and no mandatory narrative. Responses can report incomplete checks, and
submission/amendment keeps the case open. A7 commitment/comment remains optional
and does not alter the existing local decision. The examples, memory-only scope
and no-service security boundary are unchanged.

Validated browser behaviour: A7 update, source disclosure, A3 same-page contribution
and amendment, filename-only photo, text-safe conversation, PMD variant, mobile
width and 125% text; no writes or JavaScript errors. Desktop A7 visually inspected.


## Two-column variant with simple answers

Open **http://localhost:8013/columns**. Preserve `/compact` and all earlier views.
Desktop uses a 1:2 grid: visible pack details and contacts on the left, concise
Intelligence and contribution on the right. On narrow screens the action appears
first and pack/contact details remain available below. Alert code/meaning is the
page title; work status is a separate small label.

A3 has two unselected Yes/No radio groups: printed batch/serial match, and whether
the participant can rule out scanner/software issues. A No to the second question
means **not ruled out**, not proof that a technical fault exists. Unanswered checks
remain **not answered**, not No. No cause/Origin is inferred automatically.

**Root cause not on my side** is an independent, unchecked participant assessment
and can be submitted with or without the two checks. It is recorded for SMVS review,
not a confirmed attribution to the MAH. It is also available when disagreeing with
a locally resolved A7; submitting it does not silently reopen or change the NMVO
decision. Optional comments, corrective-measures commitment and filename-only
packshot are retained. No response is stored outside the preview tab.

Validated: measured 1:2 column ratio, alert headings, initial blank answers, explicit
not-my-side assessment, No/not-ruled-out interpretation, amendment preservation,
incomplete response, A7 disagreement with unchanged status, PMD scenario, text-safe
messages, 390px viewport and 125% text. Desktop A3 visually inspected; no writes.

### Refinement: legibility, pack history and a consistent finding

The `/columns` variant now uses **Your investigation** as its neutral task title.
Main Intelligence text matches the investigation question scale (relative rem units);
source notes remain secondary. The layout proportions and previous variants remain.

A separate **Pack Audit Trail** card shows the retained fictional A7 sequence and
opens a source-labelled report dialog. A3 has no retained report and says so; the
PMD-only scenario has no supplied report. No history is fabricated for missing
reports and no automatic report retrieval occurs. A live report should be published
as case-scoped evidence, with reviewed content/audience/version and access audit,
not copied indiscriminately into emails or exposed via a raw source API.

The A3 form now separates factual checks from a single **Your finding** radio group:
**Root cause on my side**, **Root cause not on my side**, **Still investigating**.
This replaces the earlier independent not-my-side checkbox for open cases. In this
prototype, not-my-side is eligible only when printed identifiers match and the
participant reports scanner/software issues ruled out. This is an End-user-flow
consistency gate for review, not a universal proof of cause or a final production
rule for every operation/context. It does not automatically choose a finding.

If an upstream answer changes and invalidates an already selected not-my-side
finding, clear that finding with an inline explanation; preserve other answers.
Unanswered checks remain unknown. Still-investigating can be submitted with missing
checks. A No to ruling out a technical issue means not ruled out, not confirmed
technical fault. No submission assigns final Origin or closes the alert.

Not-my-side disables and clears the optional own-side corrective-measures commitment
in this prototype, so the two cannot be submitted together. The corresponding A7
disagreement also cannot be combined with that commitment and leaves the NMVO
resolution unchanged. A future confirmed external cause may still call for preventive
cooperation; that belongs in an appropriately scoped action rather than contradictory
own-side-cause wording.

Browser checks: font-size parity, available/missing reports and modal/Escape,
exclusive findings, prerequisites and revalidation, correction commitment consistency,
incomplete progress, amendment, A7 unchanged decision and mobile/report layout.
No network writes or JavaScript errors; revised desktop A3 visually inspected.

### Own-side commitment and Intelligence text provenance

In `/columns`, choosing **Root cause on my side** now always reveals **Corrective
measures will be taken** directly after the finding, outside optional notes. It is
unchecked and optional: showing the control does not assert the participant has
made that commitment. Amendment preserves a submitted own-side selection/commitment.
Switching away from own-side clears/disables the hidden commitment, avoiding unseen
corrective declarations in subsequent submissions. A7 prevention handling is unchanged.

The Connect preview's Intelligence text is currently authored scenario copy in
`app/connect_preview/assets/columns.js`, not a live rule-engine response or OpenAI
output. Its bulk A3 scenario is based on the previously recorded read-only local
case inspection; PMD-only and A7 examples are simulated as documented above.

Operations already has deterministic retained-evidence checks (`prechecks.py`,
`repeat_evidence.py`, `intelligence.py`) with code-defined explanations. They are
not wired into the standalone preview. The next live step should expose structured
facts/results plus versioned message identifiers and parameters, rendered through
reviewed text templates. Keep operation-code explanations distinct from our added
analysis; references, evidence date, missing data and rule version must survive
projection. Generative text is not needed for decision conditions and must not
invent findings or turn a hypothesis into a confirmed cause.

Browser verification covered visibility outside collapsed notes, no preselection,
submission/amendment, switching findings and unchecked progress submission.

## Local organisation access pilot

The public Alert Desk and the private Collaboration API run on loopback. Apply
the local migrations with `.venv/bin/alembic upgrade head` and start the services
with one temporary, dedicated secret. Start the manual scheduler after a restart
as well. It processes queued Pack Audit Trail, upload history and manual import
requests while leaving automatic imports paused for the local session.

```sh
export ALERT_DESK_PILOT_SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PORTAL_AUTH_ENABLED=true
export PORTAL_AUTH_ORIGIN=http://localhost:8016
.venv/bin/uvicorn app.domain.investigations.pilot_api:local_app --factory --host 127.0.0.1 --port 8015 --no-proxy-headers --no-access-log &
.venv/bin/uvicorn app.alert_desk.web:local_app --factory --host 127.0.0.1 --port 8014 --no-proxy-headers --no-access-log &
.venv/bin/python -m app.integration.scheduler --serve-manual &
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8016 --no-proxy-headers --no-access-log
```

1. Open **Workflows → Alert Desk invitations**. The directory shows one row per
   active CRM alert-contact assignment. General SPOCs are excluded. Filter the
   directory, select individual rows or all available visible rows, and send.
2. The mail is captured by the local SMTP test mailbox on port 11025. Open
   `http://localhost:18025/` to check the recipient and open the 24-hour link.
3. Request a separate code at the assigned CRM mailbox and enter it in the same
   browser. The code expires after ten minutes and allows five attempts. A
   successful exchange consumes the link and creates an eight-hour session.
4. The alert list and each case are authorised by the private API. End Users
   see locally reported alerts linked to their NMVS organisation, with the
   location checked where supplied. MAH access uses the unambiguous current SAI
   mapping and CRM GLN. The list omits serials; case details show the reported
   serial. A2/A3 cases from confirmed Swiss locations accept findings, including IMT.
   Liechtenstein IMT A2/A3 findings are available to the End User at a confirmed
   location. Eligible A7 cases also accept findings. Other alerts open in a
   read-only case view. For A2, a batch update applies the finding to matching
   alerts with the same product, submitted batch, location and operation in the
   participant's scope. An End User's physical pack comparison is saved on the
   originating alert. Other alerts record that the comparison was not checked.
   Quarantine instructions appear as SMVS case updates.
5. The directory records test-mail acceptance and mailbox confirmation. Revocation
   ends access immediately. Changing the contact record or its CRM scope also
   invalidates the grant. Expired sessions currently require a new invitation.

The case preview remains available for NMVO staff from the exception. It uses the
participant template and performs no public writes. Select the MAH audience to
review the A7 request and CAPA feedback. External mail, production
connectivity and passkey enrolment are outside this local pilot.

### Reviewed intermarket exports

An incoming intermarket alert can carry a foreign source location and no Swiss
organisation ID. The End User list and direct case access both support a confirmed
A7 Export attribution scoped to the source namespace, market, location, GTIN,
batch and a bounded UTC interval. A different batch or overlapping attribution
to another End User does not grant access. The SAI MAH match is independent of
End User attribution.

The local B. Braun test uses the 289 retained A7 Export alerts from the documented
2026-11-04 DE cohort anchored by exception 2551. The attribution is a separate
local record with the operational basis. No NMVS source fields are changed.

End Users and MAHs reviewing a confirmed intermarket Export cohort can apply
an A7 finding, including **Still investigating**, to the matching batch alerts
shown in the form. The selection includes the current alert and matching cases
that are new or still under investigation by the same organisation and role for
the current source version. An interim update leaves those cases in **My cases**
and can be followed by a batch finding. The server checks the selection again
at submission, saves all findings in one transaction and links the copied audit
entries to the originating case. A submission does not change the alert status.

### Participant work and SMVS case updates

**My cases** lists new cases, ongoing findings and requests for another End User
response. The latest finding for the organisation is shared across its Alert
SPOCs. Completed work and packs on hold each have a dedicated view. The A7 batch
action is a separate button and retains the existing matching and audit controls.

The **Priority review** workflow lists A2/A3 cases where both roles report no
cause on their side. Staff can publish a request for another End User update,
a pack instruction or the completion of SMVS review from the participant case
preview. A published decision is audited independently of local exception
resolution. Findings from either role do not lift a hold or mark a case as
suspected falsification. Release instructions must be explicitly published by
SMVS and are superseded by a source revision or a later End User hold.

The pilot sends selected updates to the existing, authorised End User Alert SPOCs
via the local test mailbox. Messages contain the alert reference and a protected
case link. Delivery acceptance is recorded with the published update. External
delivery and durable retry are outside the local pilot.

The case overview uses the Operations stylesheet, module navigation, list toolbar
and table styles. Opening a case from a filtered view preserves the list context
for the return link.

### Local shared-investigation test workspace

Run `.venv/bin/python -m app.alert_desk.test_workspace` and open
`http://localhost:8021/`, or select **Test** in the development portal menu.
The workspace seeds synthetic A2, A3, A7 and A24 alerts in a separate local
SQLite database at `tmp/alert-desk-test/fixtures.db`. The test findings persist
across restarts. Open the same alert as End User or MAH
to submit findings, then open it as NMVO to review the findings and record a
decision. A2 and the reviewed A7 Export cohort have two alerts each for testing
batch updates. A24 is read-only for participants. Each product and batch has a
stable test Case ID. The overview lists the Case ID, status, date of the first
alert, alert types, End User and MAH. Expand a case to see its Alert IDs, dates
and organisations. Open an Alert ID to review findings, evidence and actions in
the RCA, or open the alert as End User or MAH. Follow the batch-finding link in
the RCA to see the alerts covered by that submission.
Mark an alert for individual review in the RCA and record the reason. A reported mismatch
between submitted and printed pack data also marks the alert for review. The
closure preview shows coverage and the alerts eligible for batch closure.
Confirm selected batches to close eligible alerts. Alerts requiring individual
review remain open for a separate decision.
**Reset all test data** clears findings, decisions, flags and audit entries for
every test scenario. The
workspace uses local test identities and sends no invitations or emails.
