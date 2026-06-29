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

The framework provides the technical foundation for acquiring, integrating and transforming Operational Information originating from multiple authoritative Operational Information Sources.

The design is independent of individual source systems and provides a reusable integration architecture for future Information Sources.

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

The Acquisition Layer communicates with external Operational Information Sources.

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

Raw source data shall be preserved in its original form.

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

Transformation converts source-specific structures into internal integration objects.

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

Mapping is responsible for resolving source-specific semantics.

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
| Information Source                 | Represents an authoritative operational information source |
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

Initial implementations include:

- Swiss NMVS
- SAI
- VerifyIt

Future Information Sources can be added without modifying the integration pipeline.

---

# 8. Import Channels

An Information Source may expose multiple Import Channels.

Examples for the Swiss NMVS include:

| Import Channel  | Typical Behaviour                            |
| --------------- | -------------------------------------------- |
| Snapshot        | Immediate download of pre-generated datasets |
| Report          | Request → Processing → Polling → Download    |
| Exceptions API  | Incremental API polling                      |
| Future Channels | Additional acquisition mechanisms            |

Each Import Channel implements the acquisition logic appropriate for the underlying technical interface.

---

# 9. Traceability

The framework shall maintain traceability between:

- Information Source
- Import Channel
- Import Job
- Raw Data
- Transformation
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