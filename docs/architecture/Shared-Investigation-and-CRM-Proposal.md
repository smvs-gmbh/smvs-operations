# Shared investigation and integrated CRM

> Current design review (2026-11-10): see [Shared Alerts Management: End-user
> pilot and MAH extension](Shared-Alerts-Management-End-User-Pilot.md). CRM and the
> narrow registration gateway are now deployed; collaboration is still proposed.
> Historical implementation/hosting statements below describe their original date.
> The new proposal explicitly compares stateless case-scoped API access with the
> earlier outbound-only publication-store option; the choice needs approval.


Status: discussion proposal reflecting product direction agreed on 2026-11-04.
This records intended behaviour and delivery order; no participant portal, CRM
migration, external communication or Hub integration is implemented by this document.

The [EMVO gold-standard mapping and explicit SMVS closure policy](EMVO-Alert-Handling-Alignment.md)
now governs the investigation content. Section 3.11 gives NMVO closure as the
general rule; SMVS excludes its optional participant closure permissions. Preserve
this distinction alongside the source's timing and investigation requirements.

## Product principle

**Shared investigation** is a central product principle of SMVS Operations:
participants build a common understanding of an Alert through evidence, questions
and contributions. Separate response boxes such as “Root cause not on my side”
are insufficient: a contribution should explain what was checked, what was found
and which question remains open. This is a distinctive direction for this project;
no claim of worldwide novelty has been established.

Exceptions remain the entry point to Alert resolution. The source Alert is an
observation; an Investigation holds the evolving investigation context, evidence
references, attributed contributions and decisions. Linking several Alerts to one
Investigation can follow later without changing the original source records.
Not every future L3/L4 exception automatically requires an Investigation.

The shared workspace should answer: What do we know? What remains uncertain?
Who will check what next? What is the current closure proposal?

## Collaboration and decision ownership

The initial investigation tile presents current assessment, supporting evidence,
open questions, next action and responsible participant, and confirmed root cause
when established. The shared page combines this structured summary with a
chronological discussion and Action Log. Participant statements, observed evidence,
NMVO assessment and final decision remain distinguishable.

| Participant | Contribution | Authority |
| --- | --- | --- |
| End-user | Scan circumstances, workflow, local checks, findings and evidence | Contribute and indicate readiness for closure within the assigned case |
| MAH / OBP | Product, batch, serialisation and upload findings | Contribute through the verified Hub workflow or a later permitted channel |
| NMVO | Reconcile findings, ask questions, assess cause and propose resolution | Make and record the final closure decision |

**Only the NMVO closes the Alert in this proposed workflow.** A participant's
“Ready for closure” is an attributed response to a particular closure proposal,
not an Alert status change. Material changes require renewed confirmation from
the relevant participants. Silence is not consent. The NMVO determines whose
input is necessary and records the decision and any unresolved disagreement;
a universal veto by every participant is not assumed.

Internal notes and shared information have explicit, separate visibility. Neither
opening a case nor adding a contact publishes internal notes or full audit reports.
Evidence is shared deliberately with the intended audience. The Action Log retains
actor, represented organisation, time, changes, reasoning and evidence references;
corrections preserve prior entries rather than silently replacing them.

## End-user first, Hub later

1. Establish the minimal organisation/contact/SPOC directory and map existing source
   identities. Prepare the bounded Investigation service and access controls needed
   by an End-user pilot; avoid a separate long internal-only delivery phase.
2. Build an End-user collaboration pilot with the internal NMVO workspace: scoped
   invitation, shared questions and findings, evidence references, next actions,
   root-cause assessment, closure proposal and NMVO decision with an Action Log.
3. Validate the workflow with representative End-users, including contact changes,
   expired access and requests for additional information. No automatic MAH
   notifications or Hub status changes are required for this pilot.
4. Obtain and map the applicable AMS-Hub contract, then add the adapter and
   reconciliation. Reuse supported MAH/OBP exchange rather than duplicating it.
   Local decisions, queued transmission and confirmed Hub outcomes stay separate.
5. Assess migration and replacement readiness for NMVS Alerts independently.

End-users should not need registration or a locally managed password. Proposed
access uses an expiring, single-use Magic Link to establish a limited session.
Access is scoped to the contact, represented organisation and Investigation and is
checked on each request. Long-running investigations can receive a new invitation;
access can be revoked. Contact and permission records are still required. A
forwarded email link alone does not prove which individual used it. NMVO decision
and closure actions require authenticated internal staff, for example corporate SSO.
Exact expiry and verification rules remain implementation decisions before a pilot.

## CRM within Operations

Integrate the small relationship-management domain into Operations rather than
maintaining an independent contact directory for each feature. Existing Snapshot
and SAI facts remain retained source observations; CRM records add maintained
relationships and validated identity links, without rewriting source evidence.

| Object | Initial purpose |
| --- | --- |
| Organisation | Maintained identity, names, lifecycle and external identifiers; can hold several roles such as End-user, MAH or OBP |
| Contact | Person or explicitly identified team mailbox, communication details and language; affiliation can change over time |
| Organisation/contact relationship | Role and validity of a contact's affiliation; supports more than one organisation where needed |
| SPOC assignment | Contact, organisation and optional location, subject/responsibility, primary or backup role, validity and review status |
| Source identity link | Reviewed association to Snapshot organisations/locations, SAI and later Hub identities, with provenance |
| Investigation participation | Case-specific role and permitted access; distinct from a general CRM affiliation |
| Contract | Swiss MAH relationship with SMVS GmbH, status, effective dates, scope and source. Track expected serialisation and Hub upload responsibility separately from observed uploads. Confirm fields against the available CRM data. |

A SPOC is an assignment, not a separate duplicate person. Organisation, location
and subject determine responsibility; backups and validity periods prevent a
single permanent email field from becoming the access model. A CRM match or SPOC
assignment does not itself grant access to a case or authorise a notification.

Do not merge organisations on name alone. A Swiss SAI authorisation holder, an OBP
and a Hub product owner may represent different relationships. Swiss product names
and MAH display values continue to follow the established SAI selection rules;
CRM labels do not silently override them. Contracts are not a prerequisite for
End-user collaboration and need not expand into a general ERP module.

## OBP directory from EMVO

OBPs are potential investigation contacts, not necessarily organisations with an
existing SMVS relationship. The available EMVO OBP list is a separate reference
source, to be imported manually when a new list is supplied. No automated EMVO
feed is assumed. The initial CRM/End-user pilot does not depend on this import.

Retain the list version, import date and supplied identifiers. Re-imports should
update source-linked records without duplicating organisations or overwriting
locally reviewed contact details without reconciliation. Being listed does not
establish a current SPOC, case responsibility, authority to receive evidence or
portal access. Contact details and the appropriate route must be checked for the
particular investigation. An upload problem can justify involving the relevant
OBP; direct contact and any later Hub-mediated exchange must remain attributed
and distinguishable. No contact or notification is sent merely by importing a list.

## CAPA thinking in Alert management

The product owner identifies NMVS as a GxP system and recurring process errors as
an operational concern. Alert investigation should therefore support a CAPA
approach: understand the cause, correct the immediate issue, prevent recurrence
and check whether the measures worked. This is a product requirement, not a claim
that the proposed application already meets a particular regulatory standard.

Separate immediate correction or containment from corrective and preventive
actions. Resolving one Alert does not demonstrate that an underlying process
problem has been removed. A participant response or “Ready for closure” likewise
does not establish root cause or CAPA effectiveness.

The proposed investigation model should support:

- Evidence-based cause assessment, including related Alerts and repeated process
  failures, with an explicit distinction between suspected and confirmed findings.
- A documented decision on whether follow-up/CAPA is needed and why; not every
  Alert automatically becomes a formal CAPA case.
- Actions with an accountable organisation/contact, owner, due date, status and
  evidence of completion; distinguish correction, corrective and preventive actions.
- A planned effectiveness check with criteria, review date, reviewer and outcome,
  including further action where recurrence or ineffective measures are observed.
- Links between multiple Investigations and one common process issue or CAPA,
  rather than copying the same action into every Alert.
- References to any formal quality-system record and its status. Alert closure,
  action completion and formal CAPA closure are distinct decisions with reasons
  and a retained history. Open follow-up remains visible after Alert closure.

The initial End-user workflow should already capture checks, findings, process
context and agreed next actions in a structured way. A full CAPA module is not a
prerequisite for that pilot. Responsibility for formal CAPA records and approvals,
and whether these remain in CANEA, must be agreed before implementing that workflow.

## Counterfeit incidents and CANEA report preparation

A suspected or confirmed falsification case may require escalation and an Incident
Report. Record suspicion, findings and confirmation separately; an Alert or a
participant assertion alone must not label a pack as a confirmed counterfeit.
The NMVO records the assessment and decisions. Report preparation must not delay
any required operational escalation; the applicable procedure remains to be defined.

Operations should help prepare a reviewable report from the Investigation,
including relevant chronology, identifiers, evidence references, participants,
assessment, measures and outstanding follow-up. These are candidate content areas,
not an invented CANEA template. Preserve source attribution and distinguish facts
from assessments. A report should identify the investigation version and preparation
time so later changes do not silently change the reviewed content.

The user will provide the required Incident Report template. Only then should
fields, wording and required sections be mapped. Prefer clearly structured,
individually copyable text sections for transfer into CANEA; generation of a Word
or PDF document and a direct CANEA integration are not prerequisites. CANEA is the
intended destination for the formal document; a local draft is not evidence of
submission, approval or completion there. Allow a CANEA reference to be recorded
once available. No template has yet been supplied and no report generator or
CANEA connection is implemented.

## MAH CRM module and report delivery

Implement a separate CRM module within SMVS Operations. Start with the MAH and
Contacts tables supplied as Excel exports from Airtable. Derive the field list
and relationship mapping from the actual workbooks. Include stable Airtable
identifiers for each record and its linked contacts where available. Preview
the import and flag ambiguous links for review.

Maintain the MAH's contract status with SMVS GmbH, with explicit unknown status
and effective dates where available. Keep contract status, expected Hub upload
responsibility and observed uploads as separate facts. Expose contract status
for internal review of the A2/A3 monthly report. The policy for delivery by
contract status remains to be agreed.

Link MAHs to contacts through Alert SPOC assignments. Retain multiple contacts
where appropriate and track which assignments are current and verified. Review
the report, MAH assignment and current recipients before sending. Missing or
ambiguous assignments require manual review. SendGrid is the proposed delivery
channel after that workflow is agreed. Record delivery against the approved
report and recipient list.

## Airtable migration approach

Start with an inventory of actual tables, fields and relationships, then map a
representative export before fixing the schema. No exports have been inspected
for this proposal. CSV is suitable as the proposed transfer format; an ongoing
Airtable API integration is not needed for the first migration.

Airtable supports CSV export from grid views; view selection matters, and ordinary
CSV export does not include all base content such as record comments. Use explicit
migration views and check completeness. Include a stable Record ID column, adding
a `RECORD_ID()` formula field where necessary. Airtable documents this mechanism
in its [record ID guide](https://support.airtable.com/articles/4688931572-finding-airtable-ids)
and describes [view exports and exclusions](https://support.airtable.com/articles/5189551686-getting-started-with-airtable-views).

The proposed importer must:

- Retain original files, import provenance and a mapping version; offer a preview
  of creates, updates, ambiguous links and rejected rows before publication.
- Identify source records by Airtable base/table/record identity, with an explicit
  alternative if existing stable external keys are used. Names and email addresses
  are not identity keys. Repeating an unchanged export must not add business rows.
- Resolve linked records through stable exported relationship keys, preparing extra
  columns if necessary. Do not assume linked display names uniquely identify targets.
- Validate required fields and relationships, preserve source text and leading zeros,
  and report unresolved references without silently guessing.
- Define field ownership before repeated imports so a later CSV does not silently
  overwrite locally maintained changes. Preserve reviewed source identity links.
- Distinguish an empty field, an explicit clearing instruction and an absent record.
  Missing rows do not automatically delete contacts, erase history or close cases.
  Deactivating a contact must also address any existing access grants explicitly.

After a reconciled transfer, make the system of record and cutover date explicit.
A temporary transition must have clear editing ownership; uncontrolled editing in
both Airtable and Operations is not the intended steady state.

## Scope and related documentation

This direction expands the internal observational scope of the current charter.
Align the controlled charter, architecture, glossary and requirements before
releasing participant-facing operational workflows; do not silently reinterpret
existing approvals. Source-system read-only protections remain applicable.

See the [NAMS proposal](NAMS-Architecture-Proposal.md),
[evidence/investigation boundary](Exception-Evidence-and-Investigation-Proposal.md)
and [implementation status](../overview/IMPLEMENTATION-STATUS.md). The existing
pack evidence UI provides a foundation; collaborative investigation, CRM, Magic
Links and closure commands are still planned capabilities.

## First local review increment — implemented 2026-11-04

The [local review increment](../integration/exception-review.md) adds the Root cause
analysis card, local work status, to-do follow-up and explicit review of similar
exceptions. It does not yet implement the participant collaboration, authenticated
NMVO closure or CRM described above. Geographic Intelligence cards remain proposed;
transaction market observations must not be interpreted as physical movement.

## Evidence guided investigation and prevention

The [evidence guided alert investigation proposal](Evidence-Guided-Alert-Investigation.md)
records the alert-specific decision paths, evidence reuse, IMT responsibilities and
requirements for a Monthly Alert Report per End-user.

## Proposed deployment isolation — 2026-11-09

Prefer a VPN-only Operations core with internal passkeys and a separate public
collaboration application/store. Exchange only deliberately released investigation
snapshots and bounded participant contributions; the NMVO retains closure authority.
See [Private core and public collaboration proposal](Operations-Core-and-Collaboration-Portal.md).
This deployment separation is proposed, not yet implemented.
