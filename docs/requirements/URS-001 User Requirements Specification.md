# User Requirements Specification

# URS-001: User Requirements Specification

| Attribute          | Value                           |
| ------------------ | ------------------------------- |
| **Document ID**    | URS-001                         |
| **Title**          | User Requirements Specification |
| **Status**         | Draft                           |
| **Version**        | 0.9                             |
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

## URS-097

For retained derived information, the system shall preserve sufficient provenance and selected evidence to explain the result after complete source data expires. Where relevant this shall identify Source System, Channel/report/API, acquisition/Observation Times, report/snapshot identity, Processing Run, processing/mapping/rule versions, source-qualified object identifiers, derived result and assessment/decision/action links. For multi-source results, provenance shall distinguish each contributing Source System, Source Authority and relevant assertion, including SMVS/NMVO-owned context, from internally generated observations, assessments and decisions. Unknown source fields and limits on reconstruction shall be explicit. A remote locator or checksum alone shall not satisfy explainability.

## URS-098

The system shall retain Relevant Changes classified by explicit operational relevance rules: first-observed MAHs, Product Codes/versions, changed MAH/OBP associations, potential transfers and relevant new Batch uploads where source evidence supports that classification. Each retained change shall identify what was observed, Observation Time, involved objects, relevance reason/rule version, supporting context/evidence and resulting assessment/decision/action links where applicable. Detection shall not require retaining every intermediate source state; inferred Effective Time, actor or cause shall not be asserted as source fact.

## URS-099

The system shall support required longitudinal Alert/Exception analysis beyond the detailed-source working-set window by retaining the minimum derived information necessary for that analysis under its own purpose-based policy. The analytical use cases, time horizons, source semantics and completeness requirements shall determine the retained information; the working-set expiry shall not determine the analytical horizon. Active/retained Case evidence and minimum five-year audit retention remain independent.

“A7 Alerts per Location over the last year” illustrates the required capability. This does not yet select dimensions/fields for retention, aggregation levels or a physical representation: pre-aggregated metrics, reduced observations or another derived representation require later use-case and source-data analysis. Complete detailed Exception records shall not be retained solely to provide that analysis where sufficient derived information meets the requirement.

## URS-100

The system shall preserve required SMVS-created assessments, investigation/review outcomes, decisions, actions, operational classifications, contextual relationships and evidence that a review occurred under their own operational, case and audit/accountability policies. Expiry or re-retrievability of external source data shall not determine retention of these records; the system shall not assume they can be reconstructed solely from NMVS or another external source.
