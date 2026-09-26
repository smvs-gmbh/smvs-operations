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

GLO-001 is the single canonical terminology document for SMVS Operations. Its retained filename, `GLO-001 Operational Investigation Glossary.md`, and internal title, **Operational Intelligence Vocabulary**, refer to this same document.

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

Existing detailed entries use the following attributes. Concise entries in §§9–11 use term/definition tables with category and authority supplied by their section.

| Attribute             | Description                                                  |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | The normative definition of the concept.                     |
| **Purpose**           | The reason why the concept exists within the architecture.   |
| **Related Concepts**  | Closely related concepts defined within this vocabulary.     |
| **Primary Reference** | The architecture document where the concept is primarily introduced. |

This structure promotes consistent interpretation while supporting traceability across architecture, requirements and validation documentation.

## Terminology authority and categories

**A — External EMVS / SSR terminology** follows the supplied Solidsoft Reply ITE Developer Portal glossary and EMVS introduction. Entries in §9 and the external definitions of Location, OBP, NCA and EMVO use that authority; project uses of those concepts remain separate.

**B — Technical integration terminology** (§10) describes the implemented acquisition, content, processing and staging foundation. **C — Operational Information conceptual terminology** (§11 and the existing foundational/domain concepts) describes project concepts, not official EMVS terminology or implemented domain tables.

This alignment preserves all draft and approval statuses. It does not approve domain schemas, Product/Batch or Snapshot identity rules, entity resolution or Pack Context implementation.

# 5. Foundational Concepts

The concepts defined in this section establish the conceptual foundation of the SMVS Operations architecture.

These concepts describe how operational observations become meaningful information that supports operational investigations.

---

## 5.1 Observation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Observation** is a source-supported assertion about state, context, a measure, a relationship or evidence of an occurrence. It is not necessarily an Event, assessment or conclusion. |
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
- Product State, Batch State, Number Of Active Packs or Local Organisation status reported in a Daily Snapshot

A difference between Observations does not by itself establish the Event that caused it, its time, actor or cause. A report is a container of source information, not one indivisible Observation.

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

Additional Operational Information Sources may be integrated without changing the conceptual model. A providing Source System is distinct from the Source Authority responsible for particular information (§10).

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
| **Definition**        | A **Product** refers here to the source Product concept represented by EMVS/NMVS Product information, retaining its Product Code Scheme and Product Code. |
| **Purpose**           | Product provides the primary business anchor for many operational investigations. |
| **Related Concepts**  | Batch, Pack Context, MAH, OBP                                |
| **Primary Reference** | ADR-005                                                      |

GTIN is used where the source code scheme establishes it. A Product is not automatically a regulatory medicinal preparation, Swissmedic authorisation, Product family or another external Product identity. Cross-source identity rules remain a design question.

Product-related information is delivered through multiple Source Systems. The Daily Snapshot exposes EMVS-originated Product information held in the NMVS for the applicable national market; delivery through NMVS does not establish original authority.

**Product Version** means the source-reported Product Version, not a parser version, Mapping Version, Snapshot Revision or Processing Run version.

---

## 6.3 Batch

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **Batch** (also **Lot**) is a production batch associated with a Product. |
| **Purpose**           | Batch information supports operational investigations involving uploaded or missing batch data. |
| **Related Concepts**  | Product, Pack Context, OBP                                   |
| **Primary Reference** | ADR-005                                                      |

A Batch cannot exist independently of a Product.

Retain the associated Product Code Scheme/Code and Batch Id in their source context. Batch Id alone is not established as a global identity. Batch information and aggregate pack counts do not establish individual Pack identities.

---

## 6.4 Organisation

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | An **Organisation** is a legal or operational entity participating in the medicines verification ecosystem. |
| **Purpose**           | Organisation provides the structural context for roles, responsibilities and operational activity. |
| **Related Concepts**  | Location, Business Role, Operational Role                    |
| **Primary Reference** | ADR-005                                                      |

An Organisation may assume one or more Business Roles, such as MAH, OBP, wholesaler, pharmacy, hospital or NCA. This generic project concept is broader than SSR **Local Organisation** (§9). `Organisation Id`, `EMVS MAH Id`, `OBP Id` and manufacturer names do not share an identity namespace; relationships require explicit identity resolution.

---

## 6.5 Location

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | In SSR NMVS, a **Location** is an instance of a pharmacy, hospital, wholesaler or another actor entitled or required to verify medicinal packs. It is not necessarily a physical postal address. |
| **Purpose**           | Location provides the operational context in which activities such as verification or decommissioning occur. |
| **Related Concepts**  | Organisation, Event, Evidence                                |
| **Primary Reference** | ADR-005                                                      |

An SSR Local Organisation owns one or more Locations. Swiss/Liechtenstein SSR Local Organisations and Locations are locally maintained end-user context, distinct from EMVS-originated Product/Batch information.

Operational activity is usually associated with a specific Location.

---

## 6.6 Pack Context

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **Pack Context** represents information relating to an individual serialised medicine pack where sufficient identifiers are available. |
| **Purpose**           | Pack Context supports pack-level investigations when operational observations refer to an individual pack. |
| **Related Concepts**  | Product, Batch, Event, Evidence, Investigation Context       |
| **Primary Reference** | ADR-005                                                      |

Pack Context depends on sufficient source-supported identifiers, including the Product identifier context and Serial Number, with Batch Id and Expiry Date where available. This does not establish a new identity rule.

The NMVS holds individual pack/serial-number data required for verification, but individual Serial Numbers are not exposed by the Daily Snapshot. Pack-related values such as `Number Of Packs` and `Number Of Active Packs` are aggregate measures, not individual Pack records. Pack Context cannot be reconstructed from those counts. Future Pack Context requires other source information; this terminology does not approve a source or implementation.

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

Within the conceptual vocabulary, MAH is a role/source assertion associated with Product information. An EMVS MAH identifier or name does not establish identity with an SSR Local Organisation or with the Swiss regulatory MAH.

---

## 7.2 OBP

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | **OBPs** are service providers for manufacturers and parallel distributors providing connectivity to the EMVS via the EU Hub. OBP is also often used generically for a manufacturer or parallel distributor itself. |
| **Purpose**           | OBP information supports Product Intelligence, Batch Intelligence and upload-related investigations. |
| **Related Concepts**  | Organisation, Product, Batch, Business Role                  |
| **Primary Reference** | ADR-005                                                      |

The repository expansion “Onboarding Partner” is unverified against the supplied authority and is not asserted as canonical here. OBP is a role, not an identity crosswalk: `OBP Id` is not an SSR `Organisation Id`, and matching names do not establish identity.

**Manufacturer** denotes source-provided manufacturer information/role. A manufacturer name is not an identity key. This term does not introduce a Manufacturer business entity.

---

## 7.3 National Competent Authority (NCA)

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | A **National Competent Authority (NCA)** provides regulatory oversight within its country. |
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

Examples include community pharmacies, hospital pharmacies, hospitals and wholesalers. **End-User Organisation** is an organisational role label, not the physical **end-user** (§9), nor a substitute for the specific SSR Local Organisation/Location concepts.



## 7.5 European Medicines Verification Organisation (EMVO)

| Attribute             | Value                                                        |
| --------------------- | ------------------------------------------------------------ |
| **Definition**        | The **European Medicines Verification Organisation (EMVO)** is the organisation accountable for operation of the European Hub. |
| **Purpose**           | EMVO identifies EU Hub operational accountability; this definition does not extend that accountability to every EMVS component. |
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

# 9. External EMVS / SSR terminology (A)

These definitions use the supplied ITE glossary; existing aligned role entries are in §7 and Location is in §6.5. Use **EU Hub** in prose (`EU HUB` is the source spelling). The EU Hub is distinct from the **EMVS AMS Hub**.

| Term | Definition |
| --- | --- |
| EMVS | European Medicines Verification System: the overall ecosystem for verification of medicines in Europe. |
| EU Hub | European Hub: centralised connectivity between manufacturers/parallel distributors and National Systems. It holds Product and Batch/Lot data, but not serial numbers. |
| NMVS | National Medicines Verification System: a National System connected to the EU Hub, providing connectivity to pharmacies and wholesalers. It holds Product, Batch/Lot and serial-number data for medicines intended for its applicable national market. |
| SSR NMVS | Solidsoft Reply National Medicines Verification System: Solidsoft Reply's implementation of the National System. Aliases: Solidsoft Reply National Blueprint System, National Blueprint System, NBS. Use NMVS generically and SSR NMVS for implementation-specific semantics. |
| NMVO | National Medicines Verification Organisation: accountable for commissioning and operation of a National System. |
| Local Organisation | Owning organisation of one or more Locations in SSR NMVS. |
| Client System | Software used by a pharmacist, wholesaler, dispensing doctor or similar actor to verify medicinal packs; connects to the NMVS for its country. |
| end-user | Physical user of a Client System. Never a synonym for Local Organisation, Location, Client System, IT supplier or Connector. |
| IT supplier | IT software provider for Client Systems. |
| Connector | From an NMVS perspective, a gateway connecting many Locations, typically between Client Systems and NMVS. A multitenant Client System may itself act as a Connector. |
| NHRN | National Healthcare Reimbursement Number, also National Product Code: national identifier for a Product type, typically used for national processes such as reimbursement outside EMVS scope. |
| IMT | Intermarket Transaction: verification where pack data is absent from the originating end-user market's NMVS. The originating NMVS escalates via the EU Hub, which routes using Batch/Lot knowledge to a fulfilling NMVS holding the relevant Batch data. That system processes the transaction and returns the result via the Hub and originating NMVS to the Client System. |
| UPRC / Alert ID | Unique Pack Return Code: unique identifier for a potential-falsification notification raised by an end-user transaction. Its first two letters identify the ISO country of the fulfilling system that raised the alert. |
| Pack | Individual medicinal sales package represented within EMVS by its unique identifier and serialisation information. |
| Serial Number | Serial component identifying an individual Pack within the applicable Product/identifier context; not a synonym for Pack. |

Product master data and Batch/Lot and associated pack information are uploaded by OBPs/manufacturers/parallel distributors via the EU Hub. Relevant Product/Batch information is distributed to National Systems by target market. Upload **via** the Hub does not imply serial-number persistence there. NMVS holds the national-market information used for verification through Client Systems, Locations and physical end-users; Daily Snapshot is a selected report exposed to this project, not a complete extract of those holdings.

# 10. Technical integration terminology (B)

| Term | Definition |
| --- | --- |
| Source System | System through which information is supplied to SMVS Operations; a delivery concept, not necessarily the author or maintainer of every item delivered. |
| Source Authority | System, organisation or actor responsible for originating or maintaining a particular information domain or attribute. One report can contain multiple authority domains. |
| Channel | Technical interface used to access a Source System, such as NMVS Reporting API; not itself necessarily a Source System or Source Authority. |
| Acquisition | One retrieval occurrence through a Channel, together with its provenance. Repeated retrievals remain separate even when bytes are identical. |
| Acquired Artifact | Retained delivery instance representing an Acquisition and linking its provenance to Artifact Content. Use this qualified term when “artifact” would be ambiguous. |
| Artifact Content | Exact retained byte sequence; may be deduplicated independently of Acquisition identity. Two Acquisitions may reference the same content. |
| Processing Run | One durable attempt to interpret/process an existing Acquired Artifact, with its own outcome, metadata and version context; not an Acquisition or Snapshot. |
| Replay | New Processing Run over retained acquired content without reacquisition. It does not itself establish a new business Snapshot or Observation. |
| Staging Dataset | Source-faithful parsed representation of one report dataset/section for a Processing Run; not an Operational Information business entity. |
| Staging Row | Source-faithful parsed record within a Staging Dataset; not automatically a business Observation. |
| File Metadata | Metadata parsed from report bytes, distinct from API Response Metadata. |
| API Response Metadata | Metadata supplied by the API about a report/acquisition rather than parsed from file contents. |
| Provenance | Recorded origin and circumstances of acquisition of information/artifacts. |
| Lineage | Traceable relationships linking Source System/Channel, Acquisition and retained Artifact Content, Processing Run and Staging, and eventually mapping/publication. The final mapping/publication layer is not implemented. |

## Daily Snapshot

A **Daily Snapshot** is a pre-generated, multi-dataset report delivered by the SSR NMVS Reporting API and retained as a report artifact. Its datasets describe source-reported state or context, including EMVS-originated Product/Batch information held for the national market, locally maintained Local Organisation/Location information, and technical monitoring information where supplied.

It is not a Pack-level or Serial-Number-level extract. Individual Serial Numbers and individual Pack records are not included; Product/Batch pack-related values are aggregate measures.

The lookup/request range, report/file metadata time, acquisition time, processing time and Effective Time are distinct. `Date Requested (UTC)` does not establish the Effective Time of every contained record. Daily Snapshot names a report type, not an Acquisition, Processing Run or established Source Snapshot identity rule.

# 11. Snapshot and mapping concepts (C — conceptual)

These terms support future Operational Information design. Their physical implementation and identity rules are not approved by this vocabulary; they do not denote existing domain tables or publication mechanisms.

| Term | Definition |
| --- | --- |
| Source Snapshot | Logically identified collection of source-reported state/context for a defined scope. Not synonymous with Acquisition, Artifact Content or Processing Run; exact identity rules remain a design question. |
| Snapshot Revision | Explicitly distinguished revision of the same logical Source Snapshot, established by source semantics. Another Acquisition, Processing Run or checksum does not automatically establish a revision. |
| Snapshot Observation | Source-supported assertion about entity/context state, relationship, measure or other context within a Source Snapshot; not automatically an Event or synonymous with a Staging Row. |
| Historical Observation | Retained Observation from an earlier Snapshot/time context; does not automatically establish an exact validity interval. |
| Current State | Selected current representation based on explicit source, temporal and publication rules; not simply the latest imported row. |
| Effective Time | Time at which information is asserted to apply; must remain unknown where source semantics do not establish it. |
| Mapping | Defined interpretation from source structures into Operational Information concepts. |
| Mapping Version | Identifier for mapping rules used; distinct from Product Version, parser version and Snapshot Revision. |
| Publication | Explicit acceptance of mapped information for operational use, separate from acquisition, parsing or staging success. |
