# SDS-002: Operational Information Data Model — Conceptual Analysis

| Attribute | Value |
| --- | --- |
| Document ID | SDS-002 |
| Status | Draft for review; not a physical design or implementation approval |
| Version | 0.3 |
| Classification | Internal |
| Owner | SMVS GmbH |
| Assessment date | 2026-11-04 |
| Baseline | Repository commit a510412 and current Daily Snapshot import contract |

## Revision history

| Version | Date | Description |
| --- | --- | --- |
| 0.1 | 2026-09-25 | Initial legacy database assessment |
| 0.2 | 2026-09-25 | Daily Snapshot acquisition and source-fidelity analysis |
| 0.3 | 2026-11-04 | Purpose-driven conceptual model; retention and authority boundaries; candidate NAMS extension |

## 1. Purpose and authority

Define the conceptual responsibilities needed to turn acquired information into operational context, Relevant Changes, investigations and retained outcomes. This revision does not prescribe tables, a star schema, APIs or migrations.

The baseline is GLO-001, ARCH-001, ADR-005, URS-001 and FRS-IMPORT-001. The NAMS extension in section 11 is a proposal prompted by the possible replacement of NMVS Alerts. It does not silently amend the existing internal-only/observational system charter or authorise external operational writes.

The complete original v0.2 assessment is preserved in [the historical evidence appendix](archive/SDS-002-v0.2-historical.md). Its counts, joins and source findings are dated evidence, not revalidated facts or target requirements. Its references to the legacy `smvs` database do not authorise access to it. The application database remains exclusively `smvs_operations`.

## 2. Implemented foundation and remaining boundary

The [Daily Snapshot contract](../integration/daily-snapshot.md) describes the implemented acquisition, immutable content retention, processing attempts, strict CSV parsing, file metadata, dynamic datasets and source-faithful staging. Acquisitions and reprocessing attempts have distinct provenance. Authenticated report destinations are constrained. Migration application and current database contents were not checked for this revision.

Mapping, accepted publication, business identities, current operational projections and relevance detection remain subsequent capabilities. Snapshot staging is not a Product/Batch domain model. The repository contains the Daily Snapshot integration and tests; this revision does not claim an implemented Exceptions importer, NAMS API or AMS-Hub connector.

## 3. Sources, authorities and confidence

| Information | Supplying system / channel | Authority distinction |
| --- | --- | --- |
| Product, Product Version and Batch context | Swiss NMVS Reporting API / Daily Snapshot | EMVS-originated information for the national market; not Swiss regulatory preparation identity |
| Local Organisation and Location | Swiss SSR NMVS / Daily Snapshot | Local participant context; not every legal entity, MAH or physical end-user identity |
| Exception/Alert context | NMVS Exceptions API, future integration | Source assertion; identity, repeated-delivery and timestamp semantics need confirmation |
| Contractual/financing information | SMVS/NMVO records; delivery to be established | Internal contractual authority, distinct from NMVS party labels |
| Establishment/authorisation information | Appropriate external authority, source to be agreed | Coverage and identifier equivalence must be evidenced; Swiss GMDP is a historical source example only |
| Investigation submissions and outcomes | Authorised participant or SMVS workflow | Attribute assertions to the submitting actor; distinguish reported cause from verified conclusion |
| Shared alert collaboration | AMS Hub, proposed connector | Shared state/message semantics depend on its verified interface contract |

Confidence must distinguish source-stated facts, observed correlations, derived interpretations and reviewed conclusions. Multiple authorities may contribute to one outcome; disagreement and unresolved identity remain visible.

## 4. Representative operational scenarios

| Scenario | Context and observation | Assessment / outcome |
| --- | --- | --- |
| Alert investigation | Exception, conditional Product/Batch/Pack context and source/last-update Location roles | Record findings, uncertainty, responsibility, evidence, decision, follow-up and closure; one Alert need not equal one internal case |
| MAH / contractual oversight | First-observed Product/version or MAH/OBP association; independent contract evidence | Distinguish contract present, apparently absent and unresolved; a potential transfer/mismatch requires verification |
| Participant eligibility | Local Organisation/Location and appropriately matched authorisation assertion | Record confirmed match, mismatch, insufficient coverage or unresolved identity; missing match does not imply ineligibility |

Each scenario supports no-action, insufficient-evidence and further-review outcomes. Source difference alone does not establish cause, responsibility or legal status.

## 5. Current context and identities

Current Operational Information includes selected Product/version, Batch, participant and relevant Exception context plus SMVS-created workflow state. Retain only attributes justified by a scenario; contacts and technical telemetry require a specific purpose.

| Concept | Identity boundary / unresolved contract |
| --- | --- |
| Product | Source namespace + Product Code Scheme/Code; no universal GTIN assumption |
| Product Version | Source-reported version within Product context; not a mapping version, snapshot revision or proof of transfer |
| Batch | Product-dependent source identity; reuse, case sensitivity and expiry semantics require evidence |
| Local Organisation / Location | Preserve source/environment scope; Location ownership and identifier uniqueness require confirmation |
| MAH / OBP / external establishment | Separate namespaces and roles; names do not establish equivalence |
| Alert / Exception | Distinguish source Alert ID, transaction ID, delivery row and internal identity |
| Investigation / assessment / action | Platform-owned identities with explicit links to external references |
| Pack Context | Conditional source-supported Product/serial context; aggregate counts never identify individual Packs |

Keep identifiers as strings. Do not silently fold case, strip zeros or apply legacy collation rules. Physical end-users are not defined as Organisation plus Location. Cross-source matches retain method, evidence, confidence and applicable time.

## 6. Time, observations and Relevant Changes

Distinguish requested day, source report time, acquisition time, Observation Time, processing/publication time and supported Effective Time. First observation does not prove creation, market entry, upload or transfer time.

A comparison may identify a changed association or state. Retain it as a Relevant Change only under an explicit, versioned relevance rule. Record what changed, involved objects, observation times, contributing evidence, relevance reason and resulting operational work. Source effective time, actor and cause remain unknown unless supported.

Absence means not observed within a particular delivery scope. It does not automatically mean deletion, withdrawal, inactivity or loss of entitlement. Distinguish absent dataset, empty dataset, incomplete delivery and absent entity.

Current-state selection requires an accepted publication policy for scope, completeness, corrections, staleness and precedence. A replay or changed mapping must not create another active copy of the same result. Acquisitions, content, processing attempts, source snapshot/revision, mapping interpretation and business identity remain distinct. A checksum or calendar day alone does not establish snapshot identity.

## 7. Operational work and provenance

Keep source assertions, derived observations, assessments, decisions and actions distinct. A case can involve multiple Alerts, actors and evidence sources. Support assignment, review, findings, follow-up, closure and justified reopening without inferring a particular workflow implementation.

The implemented integration lineage owns job/acquisition, retained content, processing attempt, parsed metadata, dataset and row provenance. Operational provenance references that foundation and adds the contributing authorities, interpretation/relevance rule versions, selected values/evidence, actor, reason and assessment/action links.

Retain enough selected evidence to explain an outcome after source expiry. Required SMVS-created records may exist nowhere else. A source URI or checksum alone cannot preserve the reasoning. Historical source retrieval is conditional on the actual source capability.

## 8. Analytics

Separate selected system-wide metric series from operational case history and longitudinal analysis. Define each metric's scope, grain, completeness, time basis and aggregation rules. Product and Batch pack aggregates must not be summed without proving non-overlap; snapshot differences are not upload/dispense counts.

For “A7 Alerts by Location over one year”, establish unique-Alert counting, relevant Location role, temporal attribution, updates/corrections and unmatched coverage. Then choose the minimum derived representation. Do not default to retaining a year of complete Exception payloads or every per-entity state.

## 9. Retention responsibilities

| Category | Conceptual responsibility |
| --- | --- |
| Transient / processing | Bounded source artifact and staging retention; replay only while supporting inputs remain |
| Current operational context | Selected working context, without mandatory complete history |
| Exception working details | Configurable purpose-bounded policy; approximately three months is an assumption, not approved duration |
| Relevant Changes | Selected operationally meaningful changes with evidence and provenance |
| Case / decision / action | Independent required history/evidence, surviving source-detail expiry |
| Audit / accountability | At least five years from the activity; record actor, change, reason/context and automated rule/version |
| System-wide metrics | Selected small time series with defined analytical purpose |
| Longitudinal analytical information | Minimum derived information supporting approved questions independently of source-detail expiry |

Do not invent other numeric durations. Case evidence and shared content dependencies must be considered before disposal. This model does not implement deletion, retention schedules or source re-retrieval guarantees.

## 10. Disposition of v0.2 proposals

| Retain | Refine / supersede |
| --- | --- |
| Dated source inventory, empirical joins and identity limitations | Label all legacy findings as historical evidence |
| Conditional Alert/Batch/Location and Pack Audit Trail evidence | Do not turn observed join coverage into universal source contracts |
| Source fidelity, dynamic datasets and technical lineage | Reference the implemented integration rather than proposing it again |
| State/event distinction and temporal uncertainty | Organise current context + Relevant Changes + operational work, rather than repeated source-state facts |
| SAI and Swiss MAH evidence | Keep authority boundaries; no automatic name-prefix matching or mandatory SAI integration |

A mandatory star schema, blanket SCD2/entity histories, permanent retention of every snapshot and Alert-centred modelling of every operational domain are superseded as target rules. Product Version is not an additive measure. Technology choices require demonstrated use cases.

## 11. Candidate NAMS extension

See [NAMS architecture proposal](../architecture/NAMS-Architecture-Proposal.md). The candidate design places national alert workflow responsibilities in a bounded SMVS Operations module with an application API. A later End-user Portal uses this API; AMS-Hub interoperability is a separate adapter. Shared investigation context, provenance and audit should be reused.

This is a possible replacement for NMVS Alerts, not for NMVS verification or AMS Hub. Participant assertions and externally shared messages/status must be distinguished from internal assessments and confidential notes. A participant-facing API must not expose generic staging or unrestricted internal investigation access.

Hub-visible Alert status, participant investigation status and internal case status need separate concepts until approved mappings exist. External effects need durable delivery identity, retries, acknowledgement, reconciliation and protection against duplicate actions/echoes. A local accepted action is not automatically Hub-confirmed.

The proposal extends the current internal-only/observational charter. Existing read-only NMVS guards remain. Hub writes require explicit workflow/interface scope; no such connector is implemented by this revision.

## 12. Open decisions and delivery order

1. Agree the NAMS boundary and charter implications separately from the existing operational baseline.
2. Specify one representative Product/Batch scenario and minimum fields; establish identity, scope, completeness, time and correction contracts with bounded source profiling when authorised.
3. Define mapping, provenance and idempotent publication together, then implement a Product/Batch slice and relevant-change detection. Add Organisation/Location context where justified.
4. Define the Alert investigation and End-user root-cause scenario alongside the actual Exceptions and AMS-Hub contracts. Existing case concepts must accommodate participant contributions without copying the Hub workflow blindly.
5. Implement required Alert acquisition and internal case handling, then the tested Hub adapter and application API. Sequence API exposure against authentication, organisation/location authorisation and message-visibility rules.
6. Add the End-user Portal and pilot replacement migration only after reconciliation, workflow coverage and operational support are demonstrated. No cutover date or full replacement is approved here.

Source questions still include Product Version meaning, Batch reuse, report completeness/disappearance, Delta Snapshot coverage, repeated Exception delivery semantics, historical retrieval and party identifier namespaces. Analytical horizons, evidence selection and retention durations also remain open.

## 13. Traceability and conceptual acceptance

| Baseline | Coverage |
| --- | --- |
| URS-010, 018, 019, 037 | Multi-authority context, non-replication and three operational domains |
| URS-013, 024–027, 098 | Current context, contractual review and Relevant Changes |
| URS-050–058, 100 | Investigation lifecycle and independently retained internal work |
| URS-074, 076, 099 | Purpose-driven metrics and longitudinal analytical capability |
| URS-094–097; FRS-IMP-021–026 | Explainability, independent retention and provenance |

Before physical design, demonstrate for each scenario: which authority supplies each assertion; how identity/time uncertainty is represented; which observation is published after replay/correction; why a change matters; which outcome is retained; and how it remains explainable after source expiry. NAMS requirements remain proposed until incorporated into the charter/URS/FRS with agreed scope.
