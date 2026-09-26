# SDS-001: Operational Information Integration Framework

| Attribute          | Value                                         |
| ------------------ | --------------------------------------------- |
| **Document ID**    | SDS-001                                       |
| **Title**          | Operational Information Integration Framework |
| **Status**         | Draft                                         |
| **Version**        | 0.1                                           |
| **Classification** | Internal                                      |
| **Owner**          | SMVS GmbH                                     |
| **Author**         | Reinhold Sojer                                |
| **Reviewers**      | TBD                                           |
| **Approver**       | TBD                                           |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.1     | 2026-06-29 | Reinhold Sojer | Initial draft |

---

# 1. Purpose

This Software Design Specification (SDS) defines the conceptual software design of the Operational Information Integration Framework.

The framework provides the technical foundation for acquiring, integrating and transforming information delivered by multiple Operational Information Sources.

The design is independent of individual source systems and provides a reusable integration architecture for future Information Sources. Terminology follows [GLO-001](GLO-001%20Operational%20Investigation%20Glossary.md). Source System denotes delivery; Source Authority denotes responsibility for originating or maintaining an information domain/attribute. These need not coincide within one report. This document remains draft; terminology alignment does not approve domain implementation.

---

# 2. Scope

The Operational Information Integration Framework is responsible for:

- acquiring Operational Information
- managing import execution
- storing imported source data
- transforming and normalising imported information
- mapping source-specific information into the Operational Information Model
- maintaining complete traceability throughout the integration process

The framework does not perform Operational Intelligence, Operational Assessment or Decision Support.

---

# 3. Design Principles

The framework follows the architectural principles defined in:

- ARCH-001 – Conceptual Reference Architecture
- ADR-005 – Operational Information Model
- ADR-006 – Operational Intelligence Model

The implementation follows these design principles:

- separation of responsibilities
- source independence
- traceability
- extensibility
- modularity
- technology independence where practical

---

# 4. Operational Information Integration Pipeline

Operational Information progresses through a sequence of well-defined processing stages.

```text
Operational Information Source
            │
            ▼
      Acquisition Layer
            │
            ▼
       Raw Data Storage
            │
            ▼
 Transformation Layer
            │
            ▼
     Mapping Layer
            │
            ▼
Operational Information Model
```

Each stage has a clearly defined responsibility.

---

# 5. Processing Stages

## 5.1 Acquisition

The Acquisition Layer accesses Source Systems through Channels. An Acquisition is one retrieval occurrence; an Acquired Artifact links that delivery provenance to retained Artifact Content. Identical content does not merge separate Acquisitions.

Responsibilities include:

- authentication
- requesting reports
- downloading datasets
- polling asynchronous operations
- receiving API responses
- recording acquisition metadata

The Acquisition Layer shall not perform business transformations.

---

## 5.2 Raw Data Storage

Raw source data shall be preserved in its original form. Artifact Content means the exact retained bytes, distinct from source-faithful parsed Staging Datasets and Staging Rows. Content deduplication does not deduplicate acquisition provenance.

Examples include:

- JSON responses
- XML documents
- CSV files
- ZIP archives

Raw Data Storage enables:

- auditability
- troubleshooting
- reprocessing
- future transformation improvements

---

## 5.3 Transformation

Transformation converts source-specific structures into internal integration objects. In the implemented foundation, a Processing Run is a durable attempt over an existing Acquired Artifact; parsing produces source-faithful Staging Datasets/Rows. Replay starts a new Processing Run from retained content without reacquisition and does not itself establish a new Source Snapshot or Observation. The broader transformation activities below do not describe modifications to retained bytes or source-faithful staging.

Typical activities include:

- parsing
- validation
- normalisation
- data cleansing
- identifier conversion

Transformation does not perform business interpretation.

---

## 5.4 Mapping

Mapping converts transformed information into the Operational Information Model defined in ADR-005.

Examples include:

- Products
- Batches
- Organisations
- Locations
- Operational Events

Mapping is responsible for resolving source-specific semantics. Mapping and Publication are conceptual future stages, distinct from successful acquisition, parsing or staging; the implemented technical foundation does not yet provide them.

---

## 5.5 Operational Information Repository

Mapped information becomes available to the Operational Information Repository.

The repository provides the common information foundation for:

- Operational Investigations
- Operational Intelligence
- Operational Assessment
- Decision Support

---

# 6. Core Components

The framework consists of the following logical components.

| Component                          | Responsibility                                             |
| ---------------------------------- | ---------------------------------------------------------- |
| Scheduler                          | Starts scheduled integration jobs                          |
| Job Manager                        | Controls execution of integration jobs                     |
| Information Source                 | Identifies the supplying Source System, distinct from Source Authority |
| Import Channel                     | Implements a specific acquisition mechanism                |
| Acquisition                        | Retrieves Operational Information                          |
| Raw Data Storage                   | Preserves original source data                             |
| Transformation                     | Normalises imported information                            |
| Mapping                            | Converts information into Business Entities                |
| Operational Information Repository | Stores mapped Operational Information                      |
| Audit Log                          | Records all processing activities                          |

---

# 7. Information Sources

The framework is independent of individual Information Sources.

Source Systems considered by this draft include:

- Swiss NMVS
- SAI
- VerifyIt

Future Information Sources can be added without modifying the integration pipeline.

---

# 8. Import Channels

A Source System may expose multiple Channels (technical interfaces). A report is a delivered artifact; a dataset is a logical section within it. These are not interchangeable with Source System or Channel.

Examples for the Swiss NMVS include:

| Channel | Report/access pattern |
| --- | --- |
| Reporting API | Daily Snapshot: retrieval of a pre-generated report; other report flows may use request, processing, polling and download |
| Exceptions API | Incremental API polling |
| Future Channels | Additional technical acquisition interfaces |

The Daily Snapshot combines EMVS-originated Product/Batch information held in NMVS for the national market with locally maintained SSR Local Organisation/Location context and technical datasets. NMVS is the delivering Source System, not necessarily the original Source Authority for each item.

Each Import Channel implements the acquisition logic appropriate for the underlying technical interface.

---

# 9. Traceability

Lineage denotes the traceable relationships below; Provenance records origin and acquisition circumstances. The framework shall maintain traceability between:

- Information Source
- Import Channel
- Import Job
- Raw Data (Acquired Artifact and Artifact Content)
- Transformation (including Processing Run and parsed Staging)
- Mapping
- Operational Information

Every mapped Business Entity shall be traceable back to its originating source information.

---

# 10. Error Handling

Errors shall be isolated to the processing stage in which they occur.

The framework shall:

- preserve Raw Data
- record processing errors
- support reprocessing
- prevent partial corruption of Operational Information

---

# 11. Extensibility

The architecture is designed to support future:

- Operational Information Sources
- Import Channels
- transformation rules
- mapping rules
- Business Entities
- analytical capabilities

without requiring architectural changes to the framework itself.

---

# 12. Traceability

| FRS               | Description                                   |
| ----------------- | --------------------------------------------- |
| FRS-IMPORT-001    | Operational Information Integration Framework |
| URS-010 – URS-017 | Operational Information Integration           |

---

# Related Documents

- ARCH-001 – Conceptual Reference Architecture
- ADR-005 – Operational Information Model
- ADR-006 – Operational Intelligence Model
- FRS-IMPORT-001 – Operational Information Integration Framework