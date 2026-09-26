# ADR-005: Operational Information Model

| Attribute          | Value                         |
| ------------------ | ----------------------------- |
| **Document ID**    | ADR-005                       |
| **Title**          | Operational Information Model |
| **Status**         | Draft                         |
| **Version**        | 0.9                           |
| **Classification** | Internal                      |
| **Owner**          | SMVS GmbH                     |
| **Author**         | Reinhold Sojer                |
| **Reviewers**      | TBD                           |
| **Approver**       | TBD                           |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.9     | 2026-06-26 | Reinhold Sojer | Initial draft |

---

# Context

SMVS Operations integrates information delivered by multiple Information Sources across the medicines verification ecosystem. Terminology follows [GLO-001](GLO-001%20Operational%20Investigation%20Glossary.md): Source System identifies delivery, while Source Authority identifies responsibility for originating or maintaining particular information. This terminology alignment does not approve this draft model or its identity rules.

Current and planned Information Sources include, but are not limited to:

- Swiss NMVS
- EMVS AMS Hub
- Swissmedic
- VerifyIt
- Future operational information sources

Each Information Source has its own information model, terminology, identifiers and operational purpose. Furthermore, the completeness and granularity of the available information differ considerably between sources.

The Daily Snapshot delivers EMVS-originated Product and Batch/Lot information held in NMVS for the national market, alongside locally maintained SSR Local Organisation and Location context. Delivery through NMVS does not make these one authority domain. NMVS holds individual Serial Numbers, but the Daily Snapshot does not expose them or individual Pack records.

Without a common information model, every analytical capability would need to interpret each Information Source individually, leading to duplicated integration logic, inconsistent interpretation and reduced maintainability.

A common conceptual representation of the operational domain is therefore required before analytical processing can take place.

The platform does not own operational information. It maintains an integrated operational representation of information delivered by Operational Information Sources, preserving the distinction between delivery and original authority.

---

# Decision

**SMVS Operations shall maintain a source-independent Operational Information Model based on common business entities and contextual investigation concepts.**



SMVS Operations shall establish a unified **Operational Information Model**.

The Operational Information Model provides the common conceptual representation of the medicines verification ecosystem independently of individual Information Sources.

The model distinguishes between:

- persistent Business Entities representing stable operational concepts;
- contextual investigation entities established from operational events and available evidence.

Information obtained from Operational Information Sources shall first be transformed into the Operational Information Model before becoming available to Operational Intelligence.

Business Entities shall be defined independently of implementation details, source-specific schemas and physical database structures.

The Operational Information Model shall provide the common information foundation for all Intelligence Domains and Decision Support capabilities.

---

# Rationale

The Operational Information Model establishes a stable conceptual foundation for the platform.

Rather than modelling individual operational systems, the platform models the business entities and investigation concepts required to support operational investigations.

This architectural approach separates information integration from analytical interpretation and enables all Intelligence Domains to operate on a common representation of the operational environment.

## Independence from Information Sources

Business Entities remain conceptually stable even when new Information Sources are introduced.

The introduction of additional operational systems therefore primarily affects the Information Integration Layer while preserving the Information Model and the Intelligence Domains built upon it.

---

## Separation of Integration and Intelligence

Information integration and operational analysis represent distinct architectural concerns.

The Information Integration Layer is responsible for acquiring, validating, transforming and correlating information delivered by multiple Information Sources.

Operational Intelligence operates exclusively on the consolidated Operational Information Model and remains independent of source-specific implementation details.

---

## Support for Contextual Investigations

Not all operational information is available at the same level of granularity.

For example, Products and Batches are persistent Business Entities, whereas Pack Context is typically established only when sufficient identifiers are available through operational events such as Alerts, Exceptions or Audit Trail records.

The Operational Information Model therefore supports both persistent Business Entities and contextual investigation entities without requiring complete pack-level information for every operational investigation.

---

## Extensibility

The Operational Information Model provides a stable conceptual foundation for future evolution.

Additional Information Sources, Business Entities and analytical capabilities can be incorporated without fundamentally changing the architecture or the existing Intelligence Domains.

## Separation of Conceptional and Physical Models

The Operational Information Model is a conceptual model. It does not prescribe the physical analytical data model used for implementation.

The implementation may use an analytical schema, such as a star schema with fact tables and dimensions, to support reporting, analytics and investigation queries. Such implementation-specific data modelling decisions shall be documented in the Software Design Specification.

# Business Entities and Investigation Concepts

The Operational Information Model distinguishes between persistent Business Entities and contextual investigation concepts.

Persistent Business Entities represent stable operational concepts that may exist independently of a specific investigation.

Contextual investigation concepts are established from operational events and available evidence. They may depend on the completeness and granularity of the information available in a specific investigation.

---

## Persistent Operational Entities

| Entity           | Description                                                  | Typical Identifier |
| ---------------- | ------------------------------------------------------------ | ------------------ |
| **Product**      | Source Product concept represented by EMVS/NMVS information; preserve Product Code Scheme and Product Code. It is not automatically a regulatory preparation or Swissmedic authorisation. | Source Product Code Scheme + Code               |
| **Batch**        | A production Batch (Lot) associated with a Product; Batch Id alone is not a global identity. | Source Product identifier + Batch Id    |
| **Organisation** | Generic legal or operational participant; broader than SSR Local Organisation. MAH, OBP and manufacturer roles do not establish identity with Local Organisation. | Source-qualified identifier    |
| **Location**     | SSR instance of an actor entitled/required to verify medicinal packs, owned by a Local Organisation; not necessarily a postal address. | Source-qualified Location Id        |

---

## Contextual Investigation Concepts

| Concept                   | Description                                                  | Typical Identifier                                           |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Pack Context**          | Context relating to an individual pack. Pack Context is established only when sufficient identifiers are available. Pack Context represents an investigation concept rather than a persistent business entity. | Source Product identifier + Serial Number, with Batch Id and Expiry Date where available |
| **Event**                 | An Event represents an operational occurrence observed within the medicines verification ecosystem.Examples include:- Alerts- Exceptions- Transaction Events- Audit Trail Events- Future Field Intelligence Events | Source-specific identifier, Transaction ID or Event ID       |
| **Evidence**              | Evidence consists of objective information collected during an investigation.Evidence remains distinguishable from Intelligence, Risk Assessment and Decision Support. | Platform-generated identifier                                |
| **Investigation Context** | Contextual representation of an operational investigation established in accordance with ADR-004. | Platform-generated identifierPlatform-generated identifier   |

Pack-level information is not generally available from all Information Sources.

The Daily Snapshot exposes no individual Serial Numbers or Pack records. Its `Number Of Packs` and `Number Of Active Packs` values are aggregates and cannot reconstruct Pack Context. This report limitation does not imply that NMVS lacks serial-number holdings. Other information would be needed for conditional Pack Context; no source or implementation is approved here.

A Snapshot Observation can describe state, context, relationships or measures without being an Event. Differences between Observations do not by themselves establish a causal Event, its time or actor.

The model therefore treats Pack Context as conditional. It can enrich an investigation where sufficient identifiers are available, but it is not required for all operational analyses.

---

# Conceptual Information Model

The following diagram illustrates the conceptual relationship between persistent Business Entities and contextual investigation concepts.

It does not represent a physical database model.

```mermaid
flowchart LR

    Product["Product(source code scheme/code)"]
    Batch["Batch(Product + Batch Id)"]
    Pack["Pack(Context, where identifiable)"]

    Organisation["Organisation"]
    Location["Location"]

    Event["Operational Event"]
    Evidence["Evidence"]
    Investigation["Investigation Context"]

    Product --> Batch
    Batch -.-> Pack

    Organisation --> Location

    Event --> Product
    Event --> Batch
    Event -.-> Pack
    Event --> Organisation
    Event --> Location

    Event --> Evidence

    Investigation --> Evidence
    Investigation --> Product
    Investigation --> Batch
    Investigation -.-> Pack
    Investigation --> Organisation
    Investigation --> Location
```

Dashed relationships indicate conditional relationships that depend on the availability of sufficient identifiers.

---

# Entity Identification

The Operational Information Model uses stable business identifiers wherever possible.

| Entity or Concept | Source identifier context                                           |
| ----------------- | ------------------------------------------------------------ |
| **Product**       | Source Product Code Scheme + Code                                                         |
| **Batch**         | Source Product identifier + Batch Id                                              |
| **Organisation**  | Source-qualified identifier                                              |
| **Location**      | Source-qualified Location Id                                                  |
| **Pack Context**  | Source Product identifier + Serial Number, with Batch Id and Expiry Date where available |
| **Event**         | Source-specific identifier, Transaction ID or Event ID       |
| **Evidence**      | Platform-generated identifier                                |
| **Investigation** | Platform-generated identifier                                |

These source identifier descriptions are conceptual, not approved canonical identity rules or database keys. `Organisation Id`, `EMVS MAH Id`, `OBP Id` and manufacturer names are separate namespaces; names alone do not resolve identity. EMVS MAH is not automatically Swiss regulatory MAH. Product Version is a source attribute, not a Mapping Version or Snapshot Revision.

Where source systems provide different identifiers or incomplete information, the Information Integration Layer is responsible for mapping and correlating the available information into the Operational Information Model.

# Consequences

## Positive

- Provides a common conceptual information model across all Information Sources.
- Establishes a stable foundation for all Intelligence Domains.
- Separates source-specific integration from analytical interpretation.
- Supports Product-, Batch-, Organisation-, Location- and Event-based investigations.
- Enables Pack-level investigations where sufficient identifiers are available.
- Reduces duplication of mapping and interpretation logic.
- Improves consistency of terminology throughout the platform.
- Supports future integration of additional Information Sources.
- Supports future evolution of the Investigation Context and Decision Support capabilities.

---

## Negative

- Information from different sources must be mapped and correlated before it can be used consistently.
- Source-specific semantics may require additional transformation logic.
- Entity resolution may become complex where identifiers are incomplete, inconsistent or source-specific.
- Some investigations may remain limited by incomplete information.
- Pack-level context cannot be assumed for all investigations.

---

# Related Documents

This Architecture Decision Record is based on the conceptual principles defined in:

- ARCH-001 Conceptual Reference Architecture

It provides the conceptual basis for:

- ADR-006 Operational Intelligence Layer
- ADR-007 Operational Risk Intelligence
- ADR-008 AI-assisted Decision Support
- URS-001 User Requirements Specification
- Functional Requirements Specifications
- Software Design Specifications
- Validation documentation

---

# Future Evolution

The Operational Information Model is expected to evolve as additional Information Sources, Intelligence Domains and operational use cases are introduced.

Future extensions may include:

- additional business entities
- additional contextual investigation concepts
- additional relationships between existing entities
- improved entity resolution
- enhanced correlation across Information Sources
- additional pack-level investigation capabilities where sufficient identifiers are available
- additional Operational Information categories

Such extensions shall preserve the distinction between persistent Business Entities and contextual investigation concepts.

The conceptual principles established by this ADR shall remain unchanged unless the underlying operational investigation model changes fundamentally.

