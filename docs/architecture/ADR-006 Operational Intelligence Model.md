# ADR-006: Operational Intelligence Model

| Attribute          | Value                                          |
| ------------------ | ---------------------------------------------- |
| **Document ID**    | ADR-006                                        |
| **Title**          | Operational Intelligence and Correlation Model |
| **Status**         | Draft                                          |
| **Version**        | 0.10                                            |
| **Classification** | Internal                                       |
| **Owner**          | SMVS GmbH                                      |
| **Author**         | Reinhold Sojer                                 |
| **Reviewers**      | TBD                                            |
| **Approver**       | TBD                                            |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.9     | 2026-06-26 | Reinhold Sojer | Initial draft |

---

# Context

The Operational Information Model defined in ADR-005 provides a consolidated and source-independent representation of the medicines verification ecosystem.

However, consolidated information alone does not provide operational understanding.

Operational investigations require information originating from multiple Business Entities, Information Sources and operational events to be analysed together in order to establish an Investigation Context.

Examples include:

- correlating Product information with regulatory reference data
- relating Batch information to operational events
- identifying operational relationships between Organisations and Locations
- recognising behavioural patterns across multiple Events
- combining operational evidence with organisational knowledge

Operational Intelligence therefore requires more than information retrieval. It requires systematic correlation of information originating from multiple sources and analytical perspectives.

---

# Decision

SMVS Operations shall establish an **Operational Intelligence and Correlation Model**.

Operational Intelligence shall be generated through the correlation of information, evidence and organisational knowledge rather than through isolated analysis of individual operational events.

Correlation is the primary mechanism for establishing relationships between Operational Information. 

Operational Intelligence emerges through the interpretation of correlated Operational Information within its operational context.

Operational Intelligence shall support investigators by establishing contextual operational hypotheses that can subsequently be evaluated through Risk Assessment and presented through Decision Support capabilities.

```mermaid
flowchart TD

    subgraph INFO["Information"]
        ENTITIES["Business Entities"]
        EVENTS["Events"]
        EVIDENCE["Evidence"]
        KNOWLEDGE["Knowledge"]
    end

    CORR["Correlation"]

    HYP["Operational Hypotheses"]

    RISK["Risk Assessment"]

    DECISION["Decision Support"]

    INFO --> CORR

    CORR --> HYP

    HYP --> RISK

    RISK --> DECISION
```

Operational Intelligence shall remain transparent, explainable and traceable to the underlying operational evidence.

---

## Rationale

The primary objective of the platform is not to collect operational information but to generate meaningful operational understanding.

Individual operational events rarely provide sufficient evidence to support operational decision making.

Instead, operational understanding emerges through the correlation of information originating from multiple Business Entities, Information Sources and Intelligence Domains.

This approach reflects the actual investigative workflow of an NMVO, where operational conclusions are established by progressively combining available evidence rather than evaluating isolated alerts or exceptions.

---

## Correlation as the Primary Analytical Principle

Correlation represents the central analytical capability of the platform.

Rather than analysing Alerts, Exceptions or operational transactions independently, the platform continuously establishes relationships between:

- Business Entities
- Operational Events
- Information Sources
- Investigation Context
- Organisational Knowledge

Operational Intelligence is therefore an emergent property resulting from the correlation of operational information.

---

## Operational Hypotheses

Operational Intelligence may establish one or more Operational Hypotheses where multiple plausible explanations exist.

Typical hypotheses may include:

- operational process deviation
- technical integration issue
- data quality issue
- synchronisation problem
- suspicious operational behaviour
- increased counterfeit risk

Operational hypotheses provide structured analytical support for investigators while preserving human responsibility for operational decisions.

# Correlation Principles

The Operational Intelligence and Correlation Model is based on the principle that operational understanding emerges through the correlation of multiple independent observations rather than isolated operational events.

Each correlation contributes additional context to an Investigation. Correlations are cumulative and may strengthen, weaken or refine one or more operational hypotheses. The architecture intentionally does not prescribe specific correlation algorithms or analytical techniques.

```mermaid
flowchart TB

    subgraph INPUT["Inputs to Correlation"]
        BE["Business Entities"]
        EV["Events"]
        EVID["Evidence"]
        KNOW["Knowledge"]
        SRC["Information Sources"]
    end

    subgraph CORR["Correlation Types"]
        ENTITY["Entity Correlation"]
        EVENT["Event Correlation"]
        BEHAVIOUR["Behaviour Correlation"]
        SOURCE["Information Source Correlation"]
        KNOWCORR["Knowledge Correlation"]
    end

    HYP["Operational Hypotheses"]

    BE --> ENTITY
    EV --> EVENT
    EV --> BEHAVIOUR
    EVID --> ENTITY
    SRC --> SOURCE
    KNOW --> KNOWCORR

    ENTITY --> HYP
    EVENT --> HYP
    BEHAVIOUR --> HYP
    SOURCE --> HYP
    KNOWCORR --> HYP
```



---

## Entity Correlation

Entity Correlation establishes relationships between Business Entities.

Examples include:

- Product ↔ Regulatory Reference Information → Product master data inconsistency
- Batch ↔ Multiple operational events across different organisations → Potential batch-related quality issue
- Organisation ↔ Historical operational behaviour → Recurring operational process deviation
- Similar operational patterns observed across multiple Products, Organisations or Locations → Common underlying operational cause
- Operational evidence ↔ Organisational Knowledge → Previously known operational scenario with established investigation guidance

Entity Correlation establishes the structural context of an investigation.

---

## Event Correlation

Event Correlation analyses relationships between operational events.

Examples include:

- repeated Exceptions
- recurring Alerts
- transaction history
- operational sequences
- Audit Trail relationships

Event Correlation establishes the temporal context of an investigation.

---

## Behaviour Correlation

Behaviour Correlation analyses operational behaviour across multiple events.

Examples include:

- repeated operational patterns
- unusual verification behaviour
- geographical patterns
- temporal patterns
- recurring operational scenarios

Behaviour Correlation supports operational risk assessment by identifying deviations from expected operational behaviour.

---

## Information Source Correlation

Information Source Correlation combines information originating from different authoritative Information Sources.

Examples include:

- Product information ↔ Swissmedic
- Product ↔ AMS Hub
- Product ↔ VerifyIt
- Batch ↔ operational events

Information Source Correlation increases confidence and completeness of the Investigation Context.

---

## Knowledge Correlation

Knowledge Correlation combines operational evidence with organisational knowledge.

Examples include:

- known operational scenarios
- investigation guidelines
- lessons learned
- product-specific experience
- historical investigations

Knowledge Correlation supports consistent operational investigations across different investigators.

---

# Operational Intelligence

Operational Intelligence emerges through the cumulative correlation of information originating from multiple analytical perspectives.

No individual correlation is expected to establish a complete operational understanding.

Instead, each correlation contributes additional evidence supporting or challenging one or more operational hypotheses.

Operational Intelligence therefore represents a continuously evolving analytical view of the Investigation Context.

---

# Correlation Characteristics

The Operational Intelligence and Correlation Model follows the principles below.

## Incremental

Operational Intelligence evolves as additional information becomes available.

---

## Context-driven

Each additional correlation contributes contextual understanding rather than replacing previous observations.

---

## Explainable

Every analytical conclusion shall remain traceable to the underlying operational evidence and contributing correlations.

---

## Technology-independent

Correlation mechanisms may be implemented using deterministic rules, statistical methods, artificial intelligence or future analytical techniques.

The conceptual architecture remains independent of the underlying implementation.

---

## Continuous Learning

Operational Intelligence shall continuously improve through:

- investigation outcomes
- newly available Information Sources
- organisational knowledge
- emerging operational patterns
- analytical improvements

Continuous Learning strengthens future investigations while preserving traceability and explainability.

## Evidence-based investigation assistant — refinement, 2026-11-17

**Status: proposed; AI assessment and execution are not implemented by this change.**
The existing evidence tabs provide complementary source views. Operational
Intelligence should assemble these into an alert-specific assessment rather than
ask investigators to reconcile each tab manually. The initial scope is a single
Alert; Case-level recommendations must retain every constituent Alert and exception.

### Evidence package

Build an explicit package from authorised, already retrieved evidence. Opening a
page must not trigger an unbounded fetch of all source reports. Identify every
source record, retrieval time, event time, relevant period, coverage, completeness
and immutable observation/version reference. Missing, failed, stale and not-yet-
requested evidence are distinct states. Sources include:

| Source | Contribution | Interpretation limit |
| --- | --- | --- |
| Exception & context | Reported identifiers, operation, error and participants | Supplied values can be incorrect; preserve supplied versus stored values |
| Upload history | Product/batch upload events, distribution outcomes and markets | Batch upload does not prove inclusion of this serial number or successful delivery to every market |
| Pack audit trail | Same-pack operations, location, market and sequence | Missing events or time windows do not establish that an operation never occurred |
| AMS Hub | Overall status, party findings, actor, closure reason and messages | Hub closure is a source fact; it does not by itself establish the local root cause or closure authority |
| Catalogue / SAI / snapshots | Product identity, MAH, batch references and matching | Today's snapshot is not necessarily the state at the Alert time |
| RCA / participant findings / local audit | Existing assessment, provenance and later changes | Recorded opinions remain attributable opinions; a previous conclusion is not independent proof |

Correlate exact Product Code/Scheme and serial, supplied/stored batch, operation,
UTC time sequence, organisation/location and market. Represent uncertain matches
explicitly. Similar batch or error code is insufficient to transfer a pack-level
conclusion. Do not count multiple copies of one source event as corroboration.

### User-facing proposal

Add an **Operations Intelligence** summary to Root cause analysis, retaining all
source tabs as evidence views. A compact summary can be visible in context.
Show the following, with direct links to individual observations or history events:

1. **Suggested explanation**: a short, provisional explanation, or “Insufficient
   evidence to suggest a cause”. Distinguish deterministic checks from AI inference.
2. **Supporting evidence**: the specific observations supporting each claim.
3. **Conflicting or missing evidence**: alternative explanations, coverage gaps,
   stale sources and material uncertainty. Avoid invented numerical confidence.
4. **Recommended next step**: the smallest useful investigation action, its purpose
   and the relevant evidence link. Draft participant questions where useful.
5. **Proposal provenance**: generation time, evidence version, model and instruction
   version. Mark the proposal stale when contributing evidence changes.

For example, successful batch upload followed by A2 does not justify “upload was
missing”. A distribution failure for the requesting market can instead support a
hypothesis requiring a market-specific check. A Hub Closed event with an actor and
reason can support a local closure recommendation while displaying the exact source
reason and any contradictory local evidence. Clearly label both examples as
hypotheses until supported by the actual package.

### Decision and control boundary

The investigator may accept, edit or reject a proposal. Retain the original proposal,
its evidence references and the human disposition in the audit trail. Proposals do
not overwrite participant findings, change Hub status, send communications or close
Cases. Configured automatic closure remains a separate, deterministic policy with
its own audit entry; AI must neither enable nor bypass that policy. A newly detected
Hub reopening invalidates an older closure proposal and follows the agreed review
or reopening policy.

Source messages are untrusted evidence, never instructions to the assistant.
Only authorised evidence may enter a proposal; minimise personal information and
free text before sending anything to an approved external model. Decide provider,
retention, processing location and access rules before a live AI integration.
Use deterministic identity, chronology and coverage checks before AI interpretation.
Store enough source provenance to reproduce the evidence package without relying
on a live Hub response. Reuse proposals only for the same evidence and instruction
versions; retain superseded proposals as historical assessments.

### Delivery and validation

First define and display evidence availability and provenance; then pilot a
read-only, explicitly requested proposal using controlled examples. Validate same-
pack matching, wrong batch/serial, missing and conflicting sources, partial audit
trails, duplicate events, late uploads, successful upload with failed distribution,
Hub closure/reopening, stale proposals and malicious source messages. Assess factual
accuracy, useful next actions and correct uncertainty, rather than fluency alone.
Trace this future change through URS/FRS, risk assessment and acceptance evidence
before release. No validation claim follows from this concept refinement.
