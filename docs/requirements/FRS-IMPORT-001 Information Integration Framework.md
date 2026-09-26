# FRS-IMPORT-001: Information Integration Framework

| Attribute          | Value                             |
| ------------------ | --------------------------------- |
| **Document ID**    | FRS-IMPORT-001                    |
| **Title**          | Information Integration Framework |
| **Status**         | Draft                             |
| **Version**        | 0.2                               |
| **Classification** | Internal                          |
| **Owner**          | SMVS GmbH                         |
| **Author**         | Reinhold Sojer                    |
| **Reviewers**      | TBD                               |
| **Approver**       | TBD                               |

---

# Revision History

| Version | Date       | Author         | Description                                |
| ------- | ---------- | -------------- | ------------------------------------------ |
| 0.2     | 2026-06-29 | Reinhold Sojer | Aligned with ARCH-001, ADR-005 and URS-001 |

---

# 1. Purpose

This document defines the functional requirements for the Information Integration Framework of the SMVS Operations platform.

The framework is responsible for acquiring information delivered by Operational Information Sources, validating and transforming the information, and updating the Operational Information Layer used throughout the platform.

The framework establishes the foundation for all Operational Intelligence, Operational Assessment and Decision Support capabilities.

---

# 2. Scope

The Information Integration Framework supports the acquisition and integration of information delivered by multiple Operational Information Sources. Source System and Source Authority have the distinct meanings defined in GLO-001: the delivering system need not originate or maintain every supplied attribute.

Initial source/access scope includes:

- NMVS as Source System, accessed through Reporting API (including Daily Snapshot and other reports) and Exceptions API Channels;
- providers of regulatory reference information as Source Systems.

Future scope includes EMVS AMS Hub and VerifyIt as Source Systems, and operational audit-trail reports or additional services through appropriate Channels. A report or interface is not itself synonymous with its Source System. EU Hub and EMVS AMS Hub are distinct systems.

---

# 3. References

- [GLO-001 Operational Intelligence Vocabulary](../architecture/GLO-001%20Operational%20Investigation%20Glossary.md)
- ARCH-001 Conceptual Reference Architecture
- ADR-004 Operational Investigation Model
- ADR-005 Operational Information Model
- URS-001 User Requirements Specification

---

## Terminology and implementation boundary

Acquisition is a retrieval occurrence with provenance; Acquired Artifact links that occurrence to retained Artifact Content. Identical bytes may share content without collapsing Acquisitions. Parsed Staging Datasets/Rows preserve source structure and values and are distinct from retained raw bytes and future mapped Operational Information.

Implemented Replay creates a new Processing Run from retained acquired content without contacting the Source System. It does not establish a new Source Snapshot or business Observation. Provenance records origin/acquisition circumstances; Lineage links the delivery, content, processing, staging and future mapping stages.

FRS-IMP-004's ordering of staging before validation/transformation and FRS-IMP-006's specific reference to reprocessing staging data are retained unchanged. Their relationship to parse-time validation and replay from retained bytes requires separate requirements review; terminology alignment does not change those obligations or claim they are fully satisfied. This document remains draft.

# 4. Functional Overview

The Information Integration Framework performs the following logical steps:

1. Acquire Operational Information from an Operational Information Source.
2. Store imported information within the Staging Layer.
3. Validate imported information.
4. Transform and map source-specific information into the Operational Information Model.
5. Update the Operational Information Layer.
6. Record complete audit and traceability information.

The conceptual processing flow is illustrated below.

```text
Operational Information Source
            │
            ▼
Information Acquisition
            │
            ▼
Staging Layer
            │
            ▼
Validation
            │
            ▼
Mapping & Transformation
            │
            ▼
Operational Information Layer
            │
            ▼
Audit & Traceability
```

---

# 5. Functional Requirements

## 5.1 Operational Information Sources

### FRS-IMP-001

The system shall maintain a configurable list of Operational Information Sources.

Each source shall include at least:

- source name
- source type
- status
- configuration
- supported import mechanism

Priority: High

---

## 5.2 Information Acquisition

### FRS-IMP-002

The system shall support manual execution of information integration processes.

Priority: High

---

### FRS-IMP-003

The system shall support scheduled execution of information integration processes.

Scheduling frequency shall be configurable for each Operational Information Source.

Priority: High

---

## 5.3 Staging Layer

### FRS-IMP-004

The system shall import Operational Information into source-specific staging structures before validation or transformation.

Priority: High

---

### FRS-IMP-005

The system shall preserve imported source information in its original structure where technically feasible.

Priority: High

---

### FRS-IMP-006

The system shall support reprocessing previously imported staging data without retrieving the information again from the originating Operational Information Source.

Priority: Medium

---

## 5.4 Validation

### FRS-IMP-007

The system shall validate imported Operational Information before updating the Operational Information Layer.

Validation may include:

- mandatory fields
- data types
- completeness
- consistency
- source integrity

Priority: High

---

### FRS-IMP-008

Validation failures shall not modify existing Operational Information.

Priority: High

---

## 5.5 Mapping and Transformation

### FRS-IMP-009

The system shall map source-specific information to the Operational Information Model defined in ADR-005.

Priority: High

---

### FRS-IMP-010

Only information required by the Operational Information Model shall be transferred into the Operational Information Layer.

Priority: High

---

### FRS-IMP-011

The mapping between source-specific fields and the Operational Information Model shall remain maintainable and version controlled.

Priority: Medium

---

## 5.6 Operational Information Update

### FRS-IMP-012

The system shall update the Operational Information Layer only after successful validation and transformation.

Priority: High

---

### FRS-IMP-013

The system shall preserve selected historical Operational Information for documented operational purposes under the retention categories in ADR-005. This includes compact Relevant Changes and required evidence, not automatically complete Product/Batch state histories or all source snapshots. Retention of derived information shall be independent of source-detail expiry.

Priority: High

---

## 5.7 Audit and Traceability

### FRS-IMP-014

The system shall maintain complete traceability between:

- Operational Information Source
- Import execution
- Staging data
- Mapping process
- Operational Information

This lineage shall remain explainable after source expiry through retained identifiers, versions and selected evidence as specified in FRS-IMP-023. It shall not require complete source datasets to remain local indefinitely.

Priority: High

---

### FRS-IMP-015

The system shall record for every integration process:

- start time
- completion time
- execution status
- processed records
- validation results
- transformation results
- execution duration
- error information

Priority: High

---

## 5.8 Error Handling

### FRS-IMP-016

Import failures shall not compromise previously integrated Operational Information.

Priority: High

---

### FRS-IMP-017

The system shall record validation errors, transformation errors and processing errors separately.

Priority: Medium

---

## 5.9 Extensibility

### FRS-IMP-018

The Information Integration Framework shall support the integration of additional Operational Information Sources without requiring architectural redesign.

Priority: High

---

# 6. Security Requirements

### FRS-IMP-019

Only authorised users shall be permitted to execute, configure or monitor information integration processes.

Priority: High

---

### FRS-IMP-020

Administrative activities associated with the Information Integration Framework shall be recorded within the Audit Log.

Priority: High

---

# Persistence and retention requirements

The following specify target behavior; they are not claims that retention, domain mapping or change detection is implemented. Existing requirements retain their identifiers.

### FRS-IMP-021

For each persisted information category, the system shall apply an explicit purpose and retention policy distinguishing processing artifacts/staging, current Operational Information, short-term source details, Relevant Changes, case/decision/action history, longitudinal Alert/Exception analytical information, audit and selected system-wide metrics. Source acquisition shall not automatically publish every supplied record as long-term Operational Information. Replay shall use locally retained content; retrieval after expiry shall be a separate Acquisition and conditional on verified source capability.

Priority: High

### FRS-IMP-022

Before source-detail expiry, the system shall preserve required derived information, case/decision/action context, audit evidence and selected supporting evidence under their independent policies. Source expiry shall not cascade into deletion of that information. Active processing and shared artifact/evidence dependencies shall be accounted for before disposal. Underlying Exception working data shall follow URS-095's defined, configurable rolling policy. Approximately three months is a design assumption, not an approved fixed duration. Duration and age/expiry rules require approval before enforcement. Required evidence for active or retained Cases shall remain available even beyond the working-set window, and the minimum derived information required for longitudinal analysis under URS-099 shall be preserved independently; no physical preservation or analytical representation is prescribed.

Priority: High

### FRS-IMP-023

For derived results, the system shall retain the applicable provenance fields in URS-097, the relevant input assertions/selected evidence and processing/mapping/rule versions needed to explain the result. Before disposing of complete source data it shall establish that this evidence remains available; an unverified promise of later NMVS retrieval shall not suffice. For multi-source results, provenance shall identify the contributing Source Systems, relevant Source Authorities and assertions, including SMVS/NMVO-owned information, separately from internal derivations/results. Required SMVS-created assessments, decisions, actions and review outcomes shall be preserved according to URS-100 rather than assumed retrievable from external sources. Missing source identity/time and unavailable reconstruction shall be explicitly represented. Observation Time shall remain separate from Effective Time, identity and retention duration.

Priority: High

### FRS-IMP-024

The system shall retain relevant integration and automated-result audit evidence for at least five years from the recorded activity, subject to documented stronger requirements. Records shall identify the actor or automated execution, time, action/change, applicable rule/version and supporting context/result links. This shall not impose the same duration on all raw source data or staging.

Priority: High

### FRS-IMP-025

The system shall retain only changes classified by documented operational relevance rules in Operational Change History, recording the information required by URS-098. Daily Snapshot input shall not itself constitute business history; Delta Snapshot input shall not itself constitute Operational Change History. Source change, Observation Time and asserted Effective Time shall remain distinguishable. No detailed Delta Snapshot semantics are specified until its source contract is established.

Priority: High

### FRS-IMP-026

Historical metrics shall be selected explicitly according to URS-076. For each selected series the system shall retain its scope, time basis, aggregation-rule version, completeness and source provenance. It shall distinguish changes in reported snapshot aggregates from source-established upload counts and shall not automatically create histories for each business dimension. Undefined count/aggregation semantics shall be resolved before publishing the affected metric.

Priority: High

---

# 7. Traceability

| URS     | Description                                |
| ------- | ------------------------------------------ |
| URS-010 | Integration of Operational Information     |
| URS-011 | Manual and scheduled integration           |
| URS-012 | Validation of Operational Information      |
| URS-013 | Historical Operational Information         |
| URS-014 | Integration status and traceability        |
| URS-015 | Extensible Information Sources             |
| URS-016 | Source traceability                        |
| URS-017 | Source-independent Operational Information |
| URS-018, URS-019 | Purpose-driven persistence and multiple operational domains |
| URS-057, URS-095 | Independent case preservation and short-term Exception context |
| URS-074, URS-076, URS-099 | Selected historical analysis, system-wide metrics and independent longitudinal Alert/Exception analysis |
| URS-094, URS-097, URS-100 | Multi-source provenance, reconstruction and independent retention of SMVS-created records |
| URS-096 | Minimum audit retention and accountability |
| URS-098 | Compact Relevant Change history |

| Functional requirement | User requirement basis |
| --- | --- |
| FRS-IMP-013, FRS-IMP-021 | URS-013, URS-018 |
| FRS-IMP-022 | URS-057, URS-095, URS-099 |
| FRS-IMP-014, FRS-IMP-023 | URS-010, URS-016, URS-094, URS-097, URS-100 |
| FRS-IMP-024 | URS-090–URS-093, URS-096 |
| FRS-IMP-025 | URS-024–URS-026, URS-098 |
| FRS-IMP-026 | URS-074, URS-076 |

---

# 8. Future Evolution

Future versions of the Information Integration Framework may include:

- incremental synchronisation
- event-driven integration
- parallel import execution
- automatic schema evolution
- configurable transformation pipelines
- monitoring dashboards
- AI-assisted data quality analysis

The conceptual architecture established by ARCH-001 and ADR-005 shall remain unchanged.
