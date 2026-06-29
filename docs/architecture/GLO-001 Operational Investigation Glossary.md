# GLO-001: Operational Intelligence Vocabulary

| Attribute          | Value                               |
| ------------------ | ----------------------------------- |
| **Document ID**    | GLO-001                             |
| **Title**          | Operational Intelligence Vocabulary |
| **Status**         | Draft                               |
| **Version**        | 0.9                                 |
| **Classification** | Internal                            |
| **Owner**          | SMVS GmbH                           |
| **Author**         | Reinhold Sojer                      |
| **Reviewers**      | TBD                                 |
| **Approver**       | TBD                                 |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.9     | 2026-06-26 | Reinhold Sojer | Initial draft |

---

# 1. Purpose

The purpose of this document is to establish the controlled conceptual vocabulary used throughout the SMVS Operations platform.

The vocabulary provides a common and authoritative terminology for architecture, requirements, design, validation and operational documentation.

The document ensures that conceptual terms are used consistently across all project artefacts and establishes a common language for all stakeholders involved in the development, operation and evolution of the platform.

---

# 2. Scope

This document applies to all controlled documentation related to the SMVS Operations platform.

The vocabulary shall be used consistently in, but is not limited to, the following document types:

- System Charter
- Conceptual Reference Architecture
- Architecture Decision Records (ADRs)
- User Requirements Specifications (URS)
- Functional Requirements Specifications (FRS)
- Software Design Specifications (SDS)
- Validation documentation
- Operational documentation
- Training material

Where a defined term exists within this document, the definition provided herein shall take precedence unless explicitly stated otherwise.

---

# 3. Relationship to Other Documents

This document provides the conceptual foundation for the complete SMVS Operations documentation.

The following documents rely on the terminology defined in this vocabulary.

| Document                                                     | Relationship                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| DOC-001 – System Charter                                     | Defines the overall vision and scope using the controlled vocabulary. |
| ARCH-001 – Conceptual Reference Architecture                 | Describes the conceptual architecture using the controlled vocabulary. |
| ADR-004 – Operational Investigation Context                  | Defines Investigation Context concepts.                      |
| ADR-005 – Operational Information Model and Business Entities | Defines Business Entities and Operational Information concepts. |
| ADR-006 – Operational Intelligence and Correlation Model     | Defines Operational Intelligence concepts.                   |
| ADR-007 – Operational Assessment Model                       | Defines Operational Assessment concepts.                     |
| ADR-008 – Operational Decision Support Model                 | Defines Operational Decision Support concepts.               |
| URS-001 – User Requirements Specification                    | Specifies system requirements using the controlled vocabulary. |
| FRS Documents                                                | Specify functional behaviour using the controlled vocabulary. |

This document shall be considered the authoritative source for conceptual terminology used throughout the project.

---

# 4. Vocabulary Structure

For consistency, each vocabulary entry is structured using the following attributes.

| Attribute             | Description                                                  |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | The normative definition of the concept.                     |
| **Purpose**           | The reason why the concept exists within the architecture.   |
| **Related Concepts**  | Closely related concepts defined within this vocabulary.     |
| **Primary Reference** | The architecture document where the concept is primarily introduced. |

This structure promotes consistent interpretation while supporting traceability across architecture, requirements and validation documentation.

# 5. Foundational Concepts

The concepts defined in this section establish the conceptual foundation of the SMVS Operations architecture.

These concepts describe how operational observations become meaningful information that supports operational investigations.

---

## 5.1 Observation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Observation** is an individual operational occurrence originating from an Operational Information Source. Observations represent raw operational facts before interpretation. |
| **Purpose**           | Observations provide the initial input to the Operational Information Model. |
| **Related Concepts**  | Operational Information, Evidence, Operational Information Source |
| **Primary Reference** | ADR-005                                                      |

### Examples

Typical Observations include:

- NMVS Alerts
- NMVS Exceptions
- Audit Trail Events
- VerifyIt verification requests
- AMS Hub transactions
- Imported operational reports

Observations represent facts. They are neither assessments nor conclusions.

---

## 5.2 Operational Information

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **Operational Information** is structured information describing Business Entities, operational events or observations within the medicines verification ecosystem. |
| **Purpose**           | Operational Information provides the common information layer used throughout the platform. |
| **Related Concepts**  | Observation, Evidence, Business Entity, Investigation Context |
| **Primary Reference** | ADR-005                                                      |

Operational Information is obtained by integrating, structuring and contextualising one or more Observations.

Unlike Observations, Operational Information has meaning within the context of operational investigations.

---

## 5.3 Evidence

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **Evidence** is Operational Information considered relevant to a specific Investigation. |
| **Purpose**           | Evidence supports or challenges one or more Operational Hypotheses. |
| **Related Concepts**  | Operational Information, Investigation Context, Operational Hypothesis |
| **Primary Reference** | ADR-006                                                      |

Evidence is always investigation-specific.

The same Operational Information may represent Evidence in one Investigation while being irrelevant in another.

Evidence remains distinct from conclusions, assessments and recommendations.

---

## 5.4 Operational Information Source

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Operational Information Source** is a system, organisation or authorised actor providing Operational Information to the platform. |
| **Purpose**           | Information Sources provide the evidence base used by the Operational Information Model. |
| **Related Concepts**  | Observation, Operational Information, Business Entity        |
| **Primary Reference** | ARCH-001, ADR-005                                            |

Examples of Operational Information Sources include:

- Swiss NMVS
- EMVS AMS Hub
- Swissmedic
- VerifyIt
- Future operational data sources

The conceptual architecture intentionally remains independent of individual source systems.

Additional Operational Information Sources may be integrated without changing the conceptual model.

# 6. Domain Concepts

This section defines the core domain concepts used within the medicines verification ecosystem.

The vocabulary distinguishes between:

- **Business Entities**: persistent domain objects;
- **Business Roles**: roles assumed by organisations within the ecosystem;
- **Operational Roles**: roles assumed by authorised users or stakeholders when using or consuming the platform.

This distinction is important for information modelling, access control, investigations and future decision support capabilities.

---

## 6.1 Business Entity

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Business Entity** is a persistent domain object within the medicines verification ecosystem. |
| **Purpose**           | Business Entities provide the structural foundation of the Operational Information Model. |
| **Related Concepts**  | Product, Batch, Organisation, Location, Pack Context         |
| **Primary Reference** | ADR-005                                                      |

Business Entities exist independently of individual investigations.

Examples include Products, Batches, Organisations and Locations.

---

## 6.2 Product

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Product** is a medicinal product identified by its Global Trade Item Number (GTIN). |
| **Purpose**           | Product provides the primary business anchor for many operational investigations. |
| **Related Concepts**  | Batch, Pack Context, MAH, OBP                                |
| **Primary Reference** | ADR-005                                                      |

Within SMVS Operations, the GTIN is the primary identifier of a Product.

Product-related information may originate from multiple Information Sources, including the Swiss NMVS, Swissmedic and future reference sources.

---

## 6.3 Batch

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Batch** is a production batch associated with a Product. |
| **Purpose**           | Batch information supports operational investigations involving uploaded or missing batch data. |
| **Related Concepts**  | Product, Pack Context, OBP                                   |
| **Primary Reference** | ADR-005                                                      |

A Batch cannot exist independently of a Product.

Within the Operational Information Model, a Batch is typically identified by the combination of GTIN and Batch ID.

---

## 6.4 Organisation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Organisation** is a legal or operational entity participating in the medicines verification ecosystem. |
| **Purpose**           | Organisation provides the structural context for roles, responsibilities and operational activity. |
| **Related Concepts**  | Location, Business Role, Operational Role                    |
| **Primary Reference** | ADR-005                                                      |

An Organisation may assume one or more Business Roles, such as MAH, OBP, wholesaler, pharmacy, hospital or NCA.

---

## 6.5 Location

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Location** is a physical or logical site associated with an Organisation. |
| **Purpose**           | Location provides the operational context in which activities such as verification or decommissioning occur. |
| **Related Concepts**  | Organisation, Event, Evidence                                |
| **Primary Reference** | ADR-005                                                      |

An Organisation may operate one or more Locations.

Operational activity is usually associated with a specific Location.

---

## 6.6 Pack Context

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **Pack Context** represents information relating to an individual serialised medicine pack where sufficient identifiers are available. |
| **Purpose**           | Pack Context supports pack-level investigations when operational observations refer to an individual pack. |
| **Related Concepts**  | Product, Batch, Event, Evidence, Investigation Context       |
| **Primary Reference** | ADR-005                                                      |

Pack Context is established using identifiers such as GTIN, Serial Number, Batch ID and Expiry Date.

Pack Context is not generally available from NMVS reference information or snapshot-style operational extracts. It is typically established from operational observations such as Alerts, Exceptions, Audit Trail records or future field intelligence events.

Pack Context is therefore treated as a contextual investigation concept rather than a persistent Business Entity.

---

# 7. Business Roles

Business Roles describe functions assumed by Organisations within the medicines verification ecosystem.

A Business Role is not a separate Business Entity. It represents the role an Organisation performs in a specific operational, regulatory or supply chain context.

---

## 7.1 Marketing Authorisation Holder (MAH)

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Marketing Authorisation Holder (MAH)** is the organisation holding the marketing authorisation for a medicinal product. |
| **Purpose**           | MAH information supports Product Intelligence, contractual analysis and operational investigations. |
| **Related Concepts**  | Organisation, Product, Business Role                         |
| **Primary Reference** | ADR-005                                                      |

Within the platform, MAH is modelled as a Business Role associated with an Organisation and one or more Products.

---

## 7.2 Onboarding Partner (OBP)

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Onboarding Partner (OBP)** is an organisation responsible for uploading product and pack data to the EMVS on behalf of one or more MAHs. |
| **Purpose**           | OBP information supports Product Intelligence, Batch Intelligence and upload-related investigations. |
| **Related Concepts**  | Organisation, Product, Batch, Business Role                  |
| **Primary Reference** | ADR-005                                                      |

OBPs are often manufacturers or service providers involved in serialisation and data upload processes.

Within the platform, OBP is modelled as a Business Role associated with an Organisation.

---

## 7.3 National Competent Authority (NCA)

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **National Competent Authority (NCA)** is a national regulatory authority responsible for medicines supervision and enforcement within its jurisdiction. |
| **Purpose**           | NCA information supports regulatory escalation, investigation coordination and authorised intelligence consumption. |
| **Related Concepts**  | Organisation, Business Role, Operational Intelligence Consumer |
| **Primary Reference** | ADR-008                                                      |

An NCA may act both as a Business Role within the medicines verification ecosystem and as an authorised consumer of Operational Intelligence Products.

Examples include Swissmedic for Switzerland.

---

## 7.4 End-User Organisation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **End-User Organisation** is an organisation performing verification or decommissioning activities within the medicines verification ecosystem. |
| **Purpose**           | End-User Organisation information supports Organisation Intelligence, Behaviour Intelligence and operational investigations. |
| **Related Concepts**  | Organisation, Location, Event                                |
| **Primary Reference** | ADR-005                                                      |

Examples include community pharmacies, hospital pharmacies, hospitals and wholesalers.



## 7.5 European Medicines Verification Organisation (EMVO)

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | The **European Medicines Verification Organisation (EMVO)** is the organisation responsible for governing and operating the European Medicines Verification System (EMVS), including the EU Hub and the overall system framework. |
| **Purpose**           | EMVO provides governance, coordination, operational oversight and central services supporting the medicines verification ecosystem. |
| **Related Concepts**  | Organisation, Business Role, Operational Intelligence Consumer |
| **Primary Reference** | ADR-008                                                      |

Within SMVS Operations, EMVO may act as an authorised consumer of Operational Intelligence Products where permitted by governance, contractual agreements and applicable regulations.

---

## 7.6 Blueprint Provider

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Blueprint Provider** is an organisation responsible for developing, operating and supporting an NMVS implementation based on an approved EMVS blueprint. |
| **Purpose**           | Blueprint Providers support system operation, incident analysis, software maintenance and technical investigations. |
| **Related Concepts**  | Organisation, Technical Context, Operational Intelligence Consumer |
| **Primary Reference** | ADR-007, ADR-008                                             |

Blueprint Providers may participate in operational investigations involving software defects, operational incidents or technical analysis.

The conceptual architecture intentionally remains independent of specific Blueprint Providers.

Examples include the currently approved EMVS Blueprint Providers.

# 8. Investigation Concepts

This section defines the concepts used to establish, analyse and understand operational investigations.

---

## 8.1 Investigation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Investigation** is the structured process of analysing an operational situation using available Operational Information, Evidence and Operational Intelligence. |
| **Purpose**           | Investigations support the identification, assessment and resolution of operational situations within the medicines verification ecosystem. |
| **Related Concepts**  | Investigation Context, Evidence, Operational Intelligence, Operational Assessment |
| **Primary Reference** | ADR-004                                                      |

An Investigation may be initiated by one or more Operational Events or by other operational observations.

Investigations evolve as additional information and evidence become available.

---

## 8.2 Investigation Context

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | The **Investigation Context** represents the complete operational situation assembled for a specific Investigation. |
| **Purpose**           | Investigation Context provides the foundation for Operational Intelligence and Operational Assessment. |
| **Related Concepts**  | Investigation, Evidence, Operational Intelligence            |
| **Primary Reference** | ADR-004                                                      |

The Investigation Context continuously evolves throughout the lifecycle of an Investigation.

---

## 8.3 Operational Event

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Operational Event** is an event occurring within the medicines verification ecosystem that may contribute to an Investigation. |
| **Purpose**           | Operational Events provide operational observations that may trigger or support investigations. |
| **Related Concepts**  | Observation, Evidence, Investigation                         |
| **Primary Reference** | ADR-005                                                      |

Examples include:

- Alerts
- Exceptions
- Verification events
- Decommissioning events
- VerifyIt requests
- Audit Trail events

The conceptual architecture intentionally does not define individual Operational Event types, which are specified by the applicable NMVS Functional Specification.

---

## 8.4 Correlation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **Correlation** is the analytical process of establishing meaningful relationships between Operational Information, Evidence and Operational Knowledge. |
| **Purpose**           | Correlation transforms Operational Information into Operational Intelligence. |
| **Related Concepts**  | Operational Intelligence, Operational Hypothesis, Evidence   |
| **Primary Reference** | ADR-006                                                      |

Correlation may consider relationships between Business Entities, Operational Events, Information Sources, behaviours and organisational knowledge.

---

## 8.5 Operational Intelligence

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **Operational Intelligence** represents the analytical understanding established through the correlation of Operational Information, Evidence and Operational Knowledge. |
| **Purpose**           | Operational Intelligence supports the generation of Operational Hypotheses. |
| **Related Concepts**  | Correlation, Operational Hypothesis, Operational Assessment  |
| **Primary Reference** | ADR-006                                                      |

Operational Intelligence represents analytical understanding rather than operational decisions.

---

## 8.6 Operational Hypothesis

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Operational Hypothesis** is a plausible explanation for an observed operational situation based on the available Operational Intelligence. |
| **Purpose**           | Operational Hypotheses provide the basis for Operational Assessment. |
| **Related Concepts**  | Operational Intelligence, Operational Assessment             |
| **Primary Reference** | ADR-006                                                      |

Multiple Operational Hypotheses may coexist until sufficient evidence becomes available.