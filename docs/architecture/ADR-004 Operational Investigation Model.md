# ADR-004: Operational Investigation Model

| Attribute      | Value          |
| -------------- | -------------- |
| Status         | Accepted (RC2) |
| Date           | 2026-06-27     |
| Decision Owner | SMVS           |
| Supersedes     | RC1            |

# 1. Context

SMVS Operations is designed as the Operational Intelligence Platform supporting evidence-based operational investigations for the Swiss National Medicines Verification System (NMVS).

Operational investigations are performed to understand operational situations rather than isolated operational events. While an investigation is often initiated by an Alert, Exception, notification or other operational observation, these initiating events rarely provide sufficient information to determine the operational significance or underlying cause.

Effective investigations require the integration and correlation of Operational Information originating from multiple authoritative Operational Information Sources. Relevant information may include Product, Batch, Organisation, Location and operational reference information, together with Evidence collected during the investigation and Operational Knowledge derived from previous investigations and established organisational practices.

Operational investigations evolve iteratively as additional Operational Information, Evidence and stakeholder feedback become available. The platform therefore requires a conceptual model that supports the continuous enrichment of an investigation while preserving complete traceability to the originating Operational Information.

This architecture establishes the **Operational Investigation Model** as the common conceptual foundation for operational investigations. It provides a unified Investigation Context supporting Operational Assessment, Decision Support, Investigation Management and Continuous Learning across the medicines verification ecosystem.

---

# 2. Decision

SMVS Operations shall represent every operational investigation as an **Operational Investigation Model**.

The Operational Investigation Model provides a structured representation of all information relevant to an operational investigation and serves as the common conceptual foundation for Operational Assessment, Decision Support and Investigation Management.

At its core, the model establishes an **Investigation Context** that is assembled dynamically from Operational Information originating from one or more authoritative Operational Information Sources.

Operational Information may originate from:

- Alerts
- Exceptions
- Notifications
- Import findings
- User observations
- Future operational event types
- Future operational information sources

The Investigation Context shall continuously evolve throughout the investigation lifecycle as additional Operational Information, Evidence and Operational Knowledge become available.

Operational Information may include:

- Products
- Batches
- Packs (where identifiable)
- Marketing Authorisation Holders (MAHs)
- Onboarding Partners (OBPs)
- Organisations
- Locations
- Regulatory Reference Information
- Operational Audit Trail information
- Future operational information sources

Operational Information shall be correlated through one or more Investigation Objects relevant to the operational situation under investigation.

Investigation Objects may include Products, Batches, Packs, Organisations, Locations, operational events, behavioural patterns or other operational entities depending on the nature of the investigation.

Where applicable, Pack-level information shall be incorporated whenever sufficient identifiers (e.g. GTIN, Serial Number, Batch Number and Expiry Date) are available.

The Operational Investigation Model shall preserve complete traceability from Operational Assessments and Decision Support back to the originating Operational Information and Evidence.

Investigation Management shall support the structured documentation, coordination and follow-up of investigations while remaining conceptually independent from Operational Intelligence and Operational Assessment.

Future analytical capabilities, including AI-assisted Decision Support and Continuous Learning, shall operate on the Operational Investigation Model rather than on individual operational events.

# 3. Rationale

## 3.1 Investigation Rather Than Event Management

Operational investigations are driven by operational questions rather than individual technical events.

An Alert, Exception, notification or other operational observation represents only a possible starting point of an investigation. Decisions require additional Operational Information, Evidence and Operational Knowledge to understand the complete situation.

The Operational Investigation Model therefore focuses on the operational situation under investigation rather than on the initiating event.

## 3.2 Context-Driven Analysis

Operational decisions should be based on contextualised Operational Information and Evidence rather than isolated events.

The Investigation Context enables investigators to analyse the relevant operational situation as a single logical context, combining available Operational Information, Evidence, Operational Intelligence and Operational Knowledge.

## 3.3 Investigation Objects

Operational investigations may be centred around different Investigation Objects depending on the operational situation.

Investigation Objects may include Products, Batches, Packs, Organisations, Locations, operational events, behavioural patterns or other operational entities relevant to the investigation.

This allows the model to support product-related, batch-related, organisation-related, behaviour-related and pattern-based investigations without assuming that every investigation is centred on a single Product or Pack.

## 3.4 Investigation Lifecycle

Operational investigations evolve iteratively as additional Operational Information, Evidence and stakeholder feedback become available.

The Operational Investigation Model therefore represents a living conceptual model that evolves throughout the lifecycle of an investigation rather than a static collection of investigation data.

This supports the gradual refinement of the Investigation Context, Operational Hypotheses, Operational Assessment and Decision Support as the investigation progresses.

## 3.5 Extensibility

The architecture is independent of individual data sources, operational event types and analytical methods.

Future Operational Information Sources, Investigation Objects, analytical capabilities and investigation services can be incorporated without changing the overall investigation model.

## 3.6 Foundation for Operational Assessment and Decision Support

The Operational Investigation Model provides the common conceptual foundation for:

- Operational Assessment
- Decision Support
- Investigation Management
- Reporting and Analytics
- AI-assisted investigation support
- Continuous Learning

This separation allows new analytical and investigation capabilities to evolve independently while sharing a common operational investigation model.

### Separation of Evidence, Assessment and Decisions

Operational Information, Evidence, Operational Intelligence, Operational Assessments, AI-generated recommendations and human decisions shall remain clearly distinguishable.

This supports transparency, explainability, traceability and validation activities.

---

# 4. Consequences

### Positive

- Establishes a common conceptual model for operational investigations.
- Supports evidence-based investigations across multiple operational domains.
- Decouples investigations from individual operational events and information sources.
- Supports investigations centred on different Investigation Objects.
- Enables contextual Operational Assessment and explainable Decision Support.
- Supports structured Investigation Management throughout the investigation lifecycle.
- Preserves complete traceability from decisions back to originating Operational Information and Evidence.
- Simplifies the integration of additional Operational Information Sources and analytical capabilities.
- Provides a common foundation for AI-assisted investigation support.
- Enables Continuous Learning from completed investigations.
- Improves long-term architectural consistency.

### Negative

- Correlation across multiple Investigation Objects and Operational Information Sources increases implementation complexity.
- Some investigations may remain limited by incomplete or unavailable Operational Information.
- Maintaining traceability and contextual consistency across evolving Investigation Contexts requires additional architectural discipline.
- Investigation Management introduces additional requirements for lifecycle management, auditability and governance.

---

# 5. Related Documents

- GLO-001 Operational Intelligence Vocabulary
- DOC-001 System Charter
- ARCH-001 Conceptual Reference Architecture
- URS-001 User Requirements Specification
- VP-001 Validation Plan

Related Architecture Decision Records:

- ADR-005 Operational Information Model
- ADR-006 Operational Intelligence and Correlation Model
- ADR-007 Operational Assessment Model
- ADR-008 Operational Decision Support Model

Related Functional Requirements Specifications:

- FRS-IMPORT-001
- FRS-PRODUCT-001
- FRS-EXCEPTION-001
- FRS-INVESTIGATION-001 (planned)
