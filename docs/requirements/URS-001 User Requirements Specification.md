# User Requirements Specification

# URS-001: User Requirements Specification

| Attribute          | Value                           |
| ------------------ | ------------------------------- |
| **Document ID**    | URS-001                         |
| **Title**          | User Requirements Specification |
| **Status**         | Draft                           |
| **Version**        | 0.16                            |
| **Classification** | Internal                        |
| **Owner**          | SMVS GmbH                       |
| **Author**         | Reinhold Sojer                  |
| **Reviewers**      | TBD                             |
| **Approver**       | TBD                             |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.9     | 2026-06-27 | Reinhold Sojer | Initial draft |
| 0.10    | 2026-11-17 | SMVS Operations project | Reconciled the intended use and added requirements for current workflows and planned Hub integration |
| 0.16    | 2026-11-25 | SMVS Operations project | Snapshot API Access investigation: service/client/IP/User-Agent observations, fixed delivery scope and evidence limits (local pilot) |
| 0.15    | 2026-11-25 | SMVS Operations project | CRM cutover: durable general affiliations, explicit roles, field retirement, protected reimports and consistent database backup/recovery |
| 0.14    | 2026-11-25 | SMVS Operations project | Independent Agreements lookup with typed date selection alongside Self-declarations (local pilot) |
| 0.13    | 2026-11-25 | SMVS Operations project | Lookup selections directly control displayed relation columns; Columns contains fixed fields only; optional year/selection context (local pilot feedback) |
| 0.12    | 2026-11-25 | SMVS Operations project | Structured lookup conditions/output configuration and explicit related-record return navigation (local pilot); FRS/RTM/risk reconciliation pending |
| 0.11    | 2026-11-25 | SMVS Operations project | Added relation lookups, MAH/year self-declaration uniqueness and read-only CRM integrity checks for local pilot evaluation; FRS/RTM/risk reconciliation pending |

---

# 1. Purpose

This document defines the user requirements for the SMVS Operations platform.

It specifies **what** the system shall provide from the perspective of its intended users, independently of the underlying technical implementation.

The User Requirements Specification serves as the basis for the Functional Requirements Specifications (FRS), Software Design Specifications (SDS), testing and validation activities.

---

# 2. Intended Use

SMVS Operations is an Operational Intelligence Platform supporting the operation of the Swiss National Medicines Verification System (NMVS).

The platform enables authorised users to derive purpose-driven Operational Information from source data, perform operational investigations, establish Operational Assessments and obtain evidence-based Decision Support. It is not a historical replica, data warehouse or shadow copy of NMVS. Source System and Source Authority remain distinct as defined in GLO-001.

The platform is intended to support operational investigations, reporting, analytics and continuous organisational learning. It does not replace operational systems such as the Swiss NMVS or the EMVS Alert Management System (AMS) Hub and shall not modify production NMVS data.

SMVS staff use Operations to review source evidence, manage local Cases, and
maintain participant and contractual context. Connect supports End User
registration with SMVS review. The Alert Desk pilot allows invited End Users and
MAHs to contribute Findings within an explicitly granted Case scope. SMVS
retains authority over manual local Case decisions. Access to each external
workflow is limited to its approved release and audience.

The first local validation candidate is Git commit `d446f5d`. Its deployment
and business acceptance scope remains for SMVS to confirm. The
[traceability matrix](../validation/RTM-001.md) records the assessed coverage,
gaps and future scope. AI-assisted search is a prototype. AMS Hub integration,
including automatic local closure based on confirmed Hub status, is planned.

---

# 3. Scope

This specification defines the user requirements for:

- Core Platform
- Operational Information Integration
- Operational Information
- Operational Investigations
- Operational Assessment
- Operational Decision Support
- Reporting & Analytics
- AI-assisted Investigation Support
- Audit & Compliance

Implementation details are intentionally excluded and are specified in the corresponding Functional Requirements Specifications (FRS) and Software Design Specifications (SDS).

# Core Platform

## URS-001

The system shall provide a central operational platform for SMVS to support evidence-based operational investigations.

## URS-002

The system shall provide role-based access control appropriate to user responsibilities.

## URS-003

The system shall maintain an audit trail of relevant user and system activities.

Every user or system transaction shall have an attributable audit entry,
including changes, reads, exports, interface requests and automated actions,
with the outcome recorded. The functional specification shall define the
transaction boundary for each workflow and protect sensitive contents.

## URS-004

The system shall provide a web-based user interface.

## URS-005

The system shall provide search, filtering and sorting capabilities across Operational Information.

## URS-006

The system shall provide capabilities for accessing Operational Information, Operational Intelligence, Operational Assessments, Decision Support and Investigation Management according to the user's role and permissions.

# Operational Information Integration

## URS-010

The system shall derive Operational Information by combining information from multiple Source Systems/Source Authorities, including NMVS/EMVS-derived information, appropriate external authoritative sources and SMVS/NMVO-owned operational or contractual context. It shall distinguish supplied assertions from internally created observations and results.

## URS-011

The system shall support both scheduled and manually initiated information integration processes.

## URS-012

The system shall validate Operational Information before making it available to the platform.

## URS-013

The system shall retain compact history of operationally relevant derived information under an explicit purpose-based retention policy, independently of underlying source-data retention. It shall not require every intermediate Product/Batch state or every source snapshot to be retained.

## URS-014

The system shall record the status, outcome and traceability of each information integration process.

## URS-015

The system shall support the integration of additional Operational Information Sources without affecting existing functionality.

## URS-016

The system shall preserve traceability between integrated Operational Information and the originating Operational Information Source.

## URS-017

The system shall maintain Operational Information independently of source-specific data structures and interfaces.

## URS-018

The system shall provide Operational Information without requiring permanent replication of NMVS source data. Persistence shall be assigned an operational purpose and retention category; source exposure alone shall not require long-term retention.

## URS-019

The system shall support Alert/Investigation Management, MAH/contractual/financing oversight and end-user participant eligibility review through source evidence, observations/relevant changes, multi-source context, assessment, decisions, actions and outcomes/follow-up. Not every workflow shall require every stage or an initiating Alert. These operational capabilities complement NMVS medicines verification; they shall not depend on NMVS providing the complete operational workflow.

# Product & Batch Investigation

## URS-020

The system shall provide access to Product and Batch information relevant to operational investigations.

## URS-021

The system shall provide visibility of Product information imported from authoritative Operational Information Sources.

## URS-022

The system shall provide visibility of Batch information associated with Products.

## URS-023

The system shall support searching and navigation of Product and Batch information.

## URS-024

The system shall present source-supported relationships between Swiss NMVS-visible Products, Product Code Versions, Batches, MAHs, OBPs and other relevant Operational Information. Product Code Scheme/Code and version shall remain distinct; MAH/OBP identifiers shall not be equated with NMVS Organisation identifiers or resolved solely by names. OBP uses the GLO-001 definition; its acronym expansion remains unverified.

## URS-025

The system shall identify first-observed Product Codes and Product Code Versions in the Swiss NMVS context, retaining Observation Time and supporting provenance. First observation shall not be presented as proven onboarding or market-entry time without source evidence.

## URS-026

The system shall identify source-supported changes in reported Product Code/version MAH or OBP associations and flag potential transfers for review. A version change alone shall not establish a transfer, legal ownership change or its Effective Time.

## URS-027

The system shall support reviewing MAHs, including newly observed MAHs, and associated Products against local contractual/registration context. It shall distinguish an established contract, evidence of no active contract and unresolved identity or insufficient evidence. Potential free-rider/contractual mismatch assessments shall require verification and shall not be presented as established legal conclusions; decisions and resulting follow-up or no-action outcomes shall be recordable.

## URS-028

The system shall support operational verification of Batch availability.

## URS-029

The system shall present Product and Batch information as part of the Investigation Context where relevant.

---

# Organisation & Location Investigation

## URS-030

The system shall provide access to Organisation and Location information relevant to operational investigations.

## URS-031

The system shall provide visibility of Organisations, Locations and related Operational Information obtained from authoritative Operational Information Sources.

## URS-032

The system shall support searching and navigation of Organisation and Location information.

## URS-033

The system shall present operational relationships between Organisations, Locations and other relevant Operational Information.

## URS-034

The system shall present Organisation and Location information as part of the Investigation Context where relevant.

## URS-035

The system shall support identifying operational relationships between Organisations involved in an investigation.

## URS-036

The system shall support correlating operational activities associated with Organisations and Locations.

---

## URS-037

The system shall support comparison of NMVS Local Organisation/Location information with appropriate authoritative establishment-existence and authorisation/status information to support participant eligibility review. It shall distinguish source-supported status/mismatch findings from unresolved identity, absent matches or insufficient coverage. A missing match alone shall not establish ineligibility. Review decisions and follow-up outcomes shall be recordable; comparison shall not itself imply automatic deactivation. Applicable participant categories, authorities and matching/decision rules require later domain analysis. Swiss GMDP is a historical example, not a mandated source or approved technical integration.

# Operational Events

## URS-040

The system shall provide access to Operational Events relevant to operational investigations.

## URS-041

The system shall provide visibility of Alerts, Exceptions and future Operational Event types.

## URS-042

The system shall support searching, filtering and navigation of Operational Events.

## URS-043

The system shall correlate Operational Events with related Operational Information.

## URS-044

The system shall retain operationally relevant Event information under its assigned retention policy. Underlying Exception source/detail data shall use the separate rolling window in URS-095 rather than indefinite retention of all Exceptions.

## URS-045

The system shall present Operational Events as part of the Investigation Context where relevant.



# Operational Investigations

## URS-050

The system shall support creating and maintaining operational investigations.

## URS-051

The system shall establish and maintain an Investigation Context for each operational investigation.

## URS-052

The system shall support associating Operational Information, Operational Events and supporting Evidence with an investigation.

## URS-053

The system shall support documenting investigation findings.

## URS-054

The system shall support recording investigation outcomes.

## URS-055

The system shall support maintaining the lifecycle and status of an investigation.

## URS-056

The system shall support assigning investigations to authorised users.

## URS-057

The system shall maintain a complete history of investigation activities under the case retention policy. Investigation/Case context, findings, assessments, decisions, actions and required evidence shall not be deleted merely because underlying Exception source/detail data expires locally.

## URS-058

The system shall support recording decisions and follow-up actions associated with an operational investigation.

# Operational Assessment



## URS-059

The system shall present Operational Assessments together with the supporting Operational Intelligence and Evidence.



## URS-060

The system shall support Operational Assessments based on the current Investigation Context.

## URS-061

The system shall present Operational Assessments together with the supporting Operational Intelligence and Evidence.

# Reporting & Analytics

## URS-070

The system shall support Operational Assessments based on the current Investigation Context.

## URS-071

The system shall present Operational Assessments together with the supporting Operational Intelligence and Evidence.

## URS-072

The system shall support exporting Operational Information where appropriate.

## URS-073

The system shall support analytical views across multiple Operational Information Sources.

## URS-074

The system shall support historical analysis of retained Relevant Changes, case/decision/action history, required longitudinal Alert/Exception analysis and selected system-wide metrics for documented operational purposes. It shall not require complete daily Product/Batch state histories or automatically generate historical metrics for every business dimension.

## URS-075

The system shall support reporting on Operational Information, investigations, Operational Assessments and operational trends.

## URS-076

The system shall support deliberately selected Swiss NMVS-wide time series for Product counts, Product Version counts where meaningful, Batch counts, reported Number Of Packs and Number Of Active Packs. Each series shall have a documented scope, grain, aggregation rule, time basis, completeness indicator and retention purpose. Equivalent histories per MAH, Product, Batch, Organisation or Location shall not be generated by default. Differences in reported pack aggregates shall not be labelled as upload counts without supporting source semantics, or interpreted as individual Packs/Serial Numbers.

# AI-assisted Investigation Support

## URS-080

The system shall support AI-assisted operational investigations.

## URS-081

The system shall support AI-assisted generation of operational observations, recommendations and investigation summaries.

## URS-082

The system shall clearly distinguish AI-generated content from user-generated content.

## URS-083

The system shall ensure that operational decisions remain under the control of authorised users.

## URS-084

The system shall provide explainable AI-assisted recommendations by presenting the supporting Operational Information, Operational Intelligence and Operational Assessments.

## URS-085

The system shall support explainable AI recommendations where AI-assisted Decision Support is provided.

## URS-086

The system shall clearly distinguish AI-generated recommendations from system-generated information and user-provided information.

# Audit & Compliance

## URS-090

The system shall maintain complete traceability of Operational Information, investigations and user activities.

## URS-091

The system shall record user actions relevant to operational investigations.

## URS-092

The system shall record system events relevant to operational investigations.

## URS-093

The system shall maintain traceability between Operational Information, Operational Intelligence, Operational Assessment, Decision Support, user decisions and Investigation Management activities.

## URS-094

The system shall support explanation and reconstruction of operational investigations from retained context, evidence and provenance, without requiring complete source datasets indefinitely. Historical source retrieval should be preferred where the relevant Source System/report/API supports it; unavailable or incomplete reconstruction shall be disclosed rather than assumed possible.

## URS-095

The system shall support purpose-bounded retention of detailed Exception operational working data under a defined, configurable rolling policy, subject to documented stronger legal/regulatory requirements. The duration, age reference and expiry calculation shall be approved before enforcement based on operational needs, verified source re-retrieval capabilities and analytical requirements. Information/evidence required by active or retained Investigations/Cases shall remain available under their own requirements even when the working-set window elapses (URS-057). Detailed-source expiry shall not prevent required longitudinal analysis (URS-099).

Approximately three months rolling is the current design assumption for later validation, not an approved fixed retention period. Older detail may be retrieved again only where the documented NMVS capability supports it; historical retrieval is not guaranteed.

## URS-096

The system shall retain audit/accountability information for at least five years from the recorded activity, or longer where a documented stronger requirement applies. It shall record who performed or approved an action/decision, what changed, when, relevant evidence/context, and the automated process/rule and version where applicable. Audit retention shall not require copying every source dataset.

The retention assessment shall distinguish the Operations audit minimum from
pack-specific repository obligations under Article 35(1)(g) of Delegated
Regulation (EU) 2016/161 and the AMS Hub archival rules. The approved policy
shall state the applicable record category, time basis and longer-period rule.
The audit archive and its recoverable backups shall preserve the records for
the applicable period.

## URS-097

For retained derived information, the system shall preserve sufficient provenance and selected evidence to explain the result after complete source data expires. Where relevant this shall identify Source System, Channel/report/API, acquisition/Observation Times, report/snapshot identity, Processing Run, processing/mapping/rule versions, source-qualified object identifiers, derived result and assessment/decision/action links. For multi-source results, provenance shall distinguish each contributing Source System, Source Authority and relevant assertion, including SMVS/NMVO-owned context, from internally generated observations, assessments and decisions. Unknown source fields and limits on reconstruction shall be explicit. A remote locator or checksum alone shall not satisfy explainability.

## URS-098

The system shall retain Relevant Changes classified by explicit operational relevance rules: first-observed MAHs, Product Codes/versions, changed MAH/OBP associations, potential transfers and relevant new Batch uploads where source evidence supports that classification. Each retained change shall identify what was observed, Observation Time, involved objects, relevance reason/rule version, supporting context/evidence and resulting assessment/decision/action links where applicable. Detection shall not require retaining every intermediate source state; inferred Effective Time, actor or cause shall not be asserted as source fact.

## URS-099

The system shall support required longitudinal Alert/Exception analysis beyond the detailed-source working-set window by retaining the minimum derived information necessary for that analysis under its own purpose-based policy. The analytical use cases, time horizons, source semantics and completeness requirements shall determine the retained information; the working-set expiry shall not determine the analytical horizon. Active/retained Case evidence and minimum five-year audit retention remain independent.

“A7 Alerts per Location over the last year” illustrates the required capability. This does not yet select dimensions/fields for retention, aggregation levels or a physical representation: pre-aggregated metrics, reduced observations or another derived representation require later use-case and source-data analysis. Complete detailed Exception records shall not be retained solely to provide that analysis where sufficient derived information meets the requirement.

## URS-100

The system shall preserve required SMVS-created assessments, investigation/review outcomes, decisions, actions, operational classifications, contextual relationships and evidence that a review occurred under their own operational, case and audit/accountability policies. Expiry or re-retrievability of external source data shall not determine retention of these records; the system shall not assume they can be reconstructed solely from NMVS or another external source.

# Participant workflows and operational controls

## URS-101

Authorised staff shall be able to maintain and review CRM records and contact
assignments used for operational follow-up, distinguish verified links from
unresolved links, and record dated, actionable Notes against individual records.

## URS-102

End Users shall be able to submit and confirm a registration through Connect.
SMVS shall review the registration and its CRM links before acceptance. Repeat
submissions and confirmation attempts shall preserve a single review record
per accepted submission and protect temporary private data.

## URS-103

SMVS shall be able to invite an eligible End User or MAH to investigate the
Cases covered by their grant. Participants shall see only their authorised
Cases and the information explicitly available to their role. Expired, revoked
or inapplicable access shall be refused.

## URS-104

Participants shall be able to submit and amend Findings and, where appropriate,
apply them to an explicitly selected set of related Alerts within their scope.
The system shall retain the role, time and affected Alert IDs and present each
party's Finding distinctly from the NMVO decision.

## URS-105

SMVS shall be able to record a reasoned decision to close or reopen an eligible
local Case or an explicitly selected set of eligible Alerts. The system shall
enforce the SMVS inter-market procedure, including support for foreign-led Alerts
and End User investigation scope for EU packs scanned in Liechtenstein.

## URS-106

SMVS shall be able to see for each requested party when feedback is due,
whether a response or progress update was received and whether follow-up is
overdue. Authorised staff shall be able to review recipients before sending
reminders. The applicable timing policy, start event, calendar and escalation
rules shall be agreed before business acceptance.

## URS-107

SMVS shall be able to rehearse and reset synthetic investigation scenarios.
Synthetic Cases, Pack Audit Trails and test resets shall remain isolated from
operational records, external delivery and production access.

## URS-108

SMVS shall have access to current catalogue counts and Alert trends, with the
underlying reporting scope and coverage visible and a route to the supporting
records where available.

## URS-109

For the planned AMS Hub integration, SMVS shall be able to view matched Hub
status and attributed investigation history in the local RCA. Authorised
administrators shall be able to enable or disable automatic local Case closure.
When enabled, a local Case shall close automatically when the Hub confirms
`Closed` for every linked Alert. The local Audit Trail shall record the
configuration changes, closure source and affected Alerts.

The system shall detect later changes to matched Hub Alerts, including
transitions out of `Closed`, and retain the last successful synchronisation
time. The synchronisation interval and the response to a Hub reopening require
a process decision.

## URS-110

SMVS shall be able to recover the application and the evidence required for
operational decisions from a controlled backup and verify the integrity of
operational data after deployment, migration or recovery.


## URS-111

Authorised staff shall be able to add values from related CRM records to personal
working views using an explicit discriminator. Initial relations are MAH to
Self-declarations and MAH to Agreements, independently configured in the same view. Lookup configuration shall be separate from column visibility
and order. Staff shall select output fields and configure typed field/operator/value
conditions, combined as all (AND) or any (OR), separately from the MAH list conditions.
The initial selection rules shall be Unique match, Minimum and Maximum on a numeric
or date field. Unique match shall require exactly one candidate; Min/Max shall select one
record, not aggregate output fields. Ties shall remain unresolved. Empty numeric
selection values shall not be treated as zero. All lookup columns sharing a selection
shall refer to the same record. Lookup output checkboxes shall directly control
which related columns appear, without a second visibility choice. Columns shall
contain fixed directory fields only; resetting these shall not change lookup
selections. SD year and Selection result shall be optional display fields. Ambiguous
or duplicate source selection shall remain identifiable in affected lookup cells
when the Selection result column is not displayed. Removing an output used in list
conditions or sorting shall require resolving
that dependency before applying or saving the view. Existing highest/specific-year
views shall retain their meaning. Staff shall be able to display, filter, sort and
export these values with the current view. The selection and data year shall remain
identifiable when a view is saved or reopened. Highest data year shall not imply
receipt or approval. Multiple explicitly linked Agreements shall be permitted;
ambiguity is not itself a duplicate-source integrity error. Agreement selection
shall support typed comparisons and Min/Max on signing date, exclude missing
dates from date extrema and retain ties as unresolved. Imported start/termination
date text shall be preserved without guessing its format. Signing date alone
shall not establish current contractual validity. Each selected record shall
remain inspectable, including a return link to the source MAH and its view. Missing values shall remain distinct from reported zero values.

## URS-112

There shall be no more than one assigned Self-declaration per MAH and data year.
Where a declaration is required for an applicable year, its absence shall be
identifiable. A conflicting import shall not create duplicate assigned business
records or discard the retained source evidence. Existing duplicate MAH/year
records shall be identified as data errors and shall not supply arbitrary or
aggregated lookup values. Resolution shall require explicit review; historical
source records shall not be silently corrected or removed.

## URS-113

Authorised staff shall have a central, read-only CRM Data integrity view with
record links, check descriptions and filters by check, assessment and record
type. Initial checks shall identify duplicate or unassigned Self-declarations,
missing declarations within an explicit year/applicability scope, current MAHs
without an available SPOC or Alert Manager, unavailable contact assignments,
assigned role contacts without usable email addresses, orphaned/imported-only
contact relations, and repeated MAH GLN/UID values needing review.

A contact may fulfil both SPOC and Alert Manager roles. Archived or provisional
contacts shall not satisfy a required current assignment. Imported relation
references shall remain distinguishable from confirmed operational assignments.
Checks shall distinguish definite errors from review items, identify their scope
and check time, and shall not change records, send messages or automatically
repair findings. Current invitation eligibility shall not be presented as proof
of historical declaration obligation or of an overdue deadline.

These requirements are recorded for the local pilot experiment. The detailed
FRS, risk and traceability updates and business acceptance remain pending.

## URS-114

When an authorised user opens a related CRM record from a record detail, the
application shall provide an explicit return link to that originating record,
identified by type and name, in addition to the destination directory link.
For the initial MAH/End User to Contact flow, return context shall survive reload,
opening in a separate browser tab, editing, saving and cancellation, and shall restore
the source view context and Contacts section. Contact Previous/Next navigation shall
be scoped to the originating parent's assigned contacts. A contact linked to multiple
parents shall return to the actual originating parent. Missing or invalid source
records shall not produce a misleading return link. User-supplied context shall not
allow an external redirect or an editing command on the originating record.

## URS-115

Contacts shall have a unified Assigned organisations relation covering MAHs,
End Users and IT Suppliers. General affiliation shall remain distinct from
SPOC/Alert contact roles and shall not grant communication/access permissions.
Existing role assignments shall remain authoritative; all relationship views
shall project the same roles. General affiliations shall have explicit foreign
keys, at most one target per link and unique contact/target pairs. Supplier
identities shall survive successive staging rows for the same exact source key.
Imports shall resolve only exact identifiers or unique export references;
missing/ambiguous references shall remain review findings. Repeated migration
shall be idempotent. Manual unassignment shall survive reimport, and membership
changes shall record actor, target, action and UTC time. Organisational roles
shall be maintained at the organisation and cannot be removed by general
membership editing. Contact erasure shall detach general affiliations consistently
with existing erasure controls and retain only the permitted minimal audit.

## URS-116

Retired import columns shall be removed from normal display/condition selectors
without deleting original evidence. Source/provenance metadata shall remain
available without import suffixes on normal labels. Existing display-only view
settings shall be normalised safely; assignment display columns may map to one
Assigned organisations column. A saved predicate/sort using a retired field shall
block results and require explicit correction, rather than silently broadening
its scope. CRM timestamps shall remain internally distinct from original source
timestamps. Reimport shall not overwrite manually maintained CRM values or create
duplicate End Users solely because a new export has different staging-row IDs;
changed/missing/ambiguous source identities shall require review.

## URS-117

Consistent database backups shall cover CRM data, relational links, audit records
and archived document blobs. Backup credentials shall not appear in command-line
arguments or normal output. Backup files/configuration shall be private and
completed backups shall have a checksum/manifest; failed/incomplete runs shall
not be recorded as complete. Concurrent runs to the same destination shall be
prevented. A controlled cutover shall retain a pre-migration backup and verify
recovery in an isolated database, as well as schema/data migration and source
record preservation. Scheduled backup operation, location, verification and
recovery instructions shall be recorded. Retention, off-site coverage and ongoing
failure monitoring require explicit operational controls and shall not be
inferred from a successful initial backup or from the Airtable source export.


## URS-118

Authorised NMVO staff shall inspect API access observations retained from the NMVS
Daily Snapshot across Verification, Authentication, Identity, Reporting and NMVO
Exception API sections. The view shall expose supplied organisation, location,
client, IP, User-Agent, last request and API version values, keeping absent values
explicit and original evidence unchanged. Staff shall combine agent/IP searches,
service and last-request source-date ranges and personal column/condition/sort
views before pagination, and export that same filtered view. One explicit
successful snapshot delivery shall bound an investigation/export, with provenance
and optional historical delivery selection; repeated snapshots shall not inflate
counts. Missing API sections shall be distinguishable from empty sections. Links
to organisation/location records shall require the exact corresponding published
delivery; matching names or identifiers in another snapshot shall not establish
a historical relationship. Snapshot observation counts/last-request times shall
not be represented as WAF events, request volumes, URL/business-operation or
destination-market evidence or IP geolocation. A shared User-Agent alone shall
not establish a unique integration. Raw observations and contextual return links
shall remain available within the existing authenticated NMVO boundary.
